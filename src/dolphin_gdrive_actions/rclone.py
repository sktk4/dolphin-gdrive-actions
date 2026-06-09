from __future__ import annotations

import json
import shutil
import subprocess

from dolphin_gdrive_actions.drive_metadata import DriveItemMetadata, parse_lsjson_stat, split_remote_path
from dolphin_gdrive_actions.errors import RcloneMetadataError, RcloneNotFoundError
from dolphin_gdrive_actions.remote_resolve import _load_rclone_config_dump, rewrite_if_combine


def ensure_rclone_available() -> str:
    rclone = shutil.which("rclone")
    if not rclone:
        raise RcloneNotFoundError(
            "rclone was not found on PATH.\n"
            "Install rclone and ensure your configured remote works before using dga."
        )
    return rclone


def stat_item(remote_path: str) -> DriveItemMetadata:
    """Fetch Drive item metadata via ``rclone lsjson --stat``.

    Read-only: does not change Drive sharing permissions.
    """
    return _resolve_item_metadata(remote_path)


def stat_item_with_combine_fallback(remote_path: str) -> DriveItemMetadata:
    """Like ``stat_item``, but retries via combine upstream rewrite on failure."""
    try:
        return _resolve_item_metadata(remote_path)
    except RcloneMetadataError as first_error:
        rewritten = rewrite_if_combine(remote_path)
        if rewritten is None or rewritten == remote_path:
            raise first_error from None
        try:
            return _resolve_item_metadata(rewritten)
        except RcloneMetadataError:
            raise first_error from None


def _resolve_item_metadata(remote_path: str) -> DriveItemMetadata:
    metadata = _stat_item_once(remote_path)
    if metadata.item_id:
        return metadata
    if not metadata.is_dir:
        raise RcloneMetadataError(
            f"Drive metadata lookup returned no ID for non-directory: {remote_path}"
        )
    folder_id = _resolve_directory_id(remote_path)
    return DriveItemMetadata(
        item_id=folder_id,
        mime_type=metadata.mime_type,
        is_dir=True,
    )


def _stat_item_once(remote_path: str) -> DriveItemMetadata:
    rclone = ensure_rclone_available()

    try:
        result = subprocess.run(
            [rclone, "lsjson", "--stat", remote_path],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RcloneMetadataError(f"Failed to run rclone lsjson --stat: {exc}") from exc

    if result.returncode != 0:
        detail = _format_stat_failure(result.stderr, result.stdout)
        raise RcloneMetadataError(detail)

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RcloneMetadataError(
            "rclone lsjson --stat succeeded but returned invalid JSON."
        ) from exc

    if not isinstance(payload, (dict, list)):
        raise RcloneMetadataError("rclone lsjson --stat returned unexpected JSON structure.")

    try:
        return parse_lsjson_stat(payload)
    except ValueError as exc:
        raise RcloneMetadataError(str(exc)) from exc


def _resolve_directory_id(remote_path: str) -> str:
    remote_name, relative = split_remote_path(remote_path)
    if not relative:
        root_id = _configured_root_folder_id(remote_name)
        if root_id is None:
            # My Drive root: create URLs work without folder=; callers treat "" as omit.
            return ""
        return root_id

    if "/" in relative:
        parent_relative, child_name = relative.rsplit("/", 1)
        parent_path = f"{remote_name}:{parent_relative}"
    else:
        parent_path = f"{remote_name}:"
        child_name = relative

    return _find_directory_id_in_parent(parent_path, child_name)


def _parse_remote_option_string(remote_field: str) -> tuple[str, dict[str, str]]:
    """Split an rclone alias ``remote`` field into base remote and comma options."""
    parts = remote_field.split(",")
    base = parts[0].strip()
    options: dict[str, str] = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            options[key] = value
    return base, options


def _is_usable_folder_id(value: str) -> bool:
    """Return whether a config folder/team-drive ID is non-empty and not a root placeholder."""
    return bool(value) and value != ":"


def _configured_root_folder_id(remote_name: str) -> str | None:
    """Resolve the Drive folder ID for a remote root (My Drive subtree or shared drive)."""
    config = _load_rclone_config_dump()
    team_drive: str | None = None
    root_folder_id: str | None = None

    current = remote_name
    seen: set[str] = set()

    while current and current not in seen:
        seen.add(current)
        entry = config.get(current)
        if not isinstance(entry, dict):
            break

        td = entry.get("team_drive")
        if isinstance(td, str) and _is_usable_folder_id(td.strip()) and team_drive is None:
            team_drive = td.strip()

        rfi = entry.get("root_folder_id")
        if (
            isinstance(rfi, str)
            and _is_usable_folder_id(rfi.strip())
            and root_folder_id is None
        ):
            root_folder_id = rfi.strip()

        if entry.get("type") == "alias":
            target = entry.get("remote")
            if isinstance(target, str) and target.strip():
                base, options = _parse_remote_option_string(target.strip())
                opt_td = options.get("team_drive", "")
                if _is_usable_folder_id(opt_td) and team_drive is None:
                    team_drive = opt_td
                opt_rfi = options.get("root_folder_id", "")
                if _is_usable_folder_id(opt_rfi) and root_folder_id is None:
                    root_folder_id = opt_rfi
                current = base
                continue
        break

    if team_drive:
        return team_drive
    if root_folder_id:
        return root_folder_id
    return None


def _find_directory_id_in_parent(parent_remote_path: str, child_name: str) -> str:
    rclone = ensure_rclone_available()
    try:
        result = subprocess.run(
            [rclone, "lsjson", parent_remote_path, "--dirs-only"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RcloneMetadataError(f"Failed to list parent directory: {exc}") from exc

    if result.returncode != 0:
        detail = _format_stat_failure(result.stderr, result.stdout)
        raise RcloneMetadataError(detail)

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RcloneMetadataError("Parent directory listing returned invalid JSON.") from exc

    if not isinstance(payload, list):
        raise RcloneMetadataError("Parent directory listing returned unexpected JSON structure.")

    for item in payload:
        if not isinstance(item, dict):
            continue
        if item.get("Name") != child_name or item.get("IsDir") is not True:
            continue
        item_id = item.get("ID")
        if isinstance(item_id, str) and item_id:
            return item_id

    raise RcloneMetadataError(
        f"Could not resolve Drive folder ID for {child_name!r} under {parent_remote_path}."
    )


def _format_stat_failure(stderr: str, stdout: str) -> str:
    combined = "\n".join(part.strip() for part in (stderr, stdout) if part and part.strip())
    if not combined:
        return "Drive metadata lookup failed with no error output."
    return f"Drive metadata lookup failed:\n{combined}"
