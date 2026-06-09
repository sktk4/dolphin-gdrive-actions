from __future__ import annotations

from pathlib import Path

from dolphin_gdrive_actions.config import MountMapping
from dolphin_gdrive_actions.errors import PathMappingError


def local_to_remote_path(local_path: Path, mounts: tuple[MountMapping, ...]) -> str:
    """Translate a local mount path to an rclone remote path like remote:dir/file.txt."""
    if not mounts:
        raise PathMappingError("No mount mappings are configured.")

    try:
        resolved = local_path.expanduser().resolve()
    except OSError as exc:
        raise PathMappingError(f"Cannot resolve local path {local_path}: {exc}") from exc

    if not resolved.exists():
        raise PathMappingError(f"Local path does not exist: {resolved}")

    match = find_mount_for_path(resolved, mounts)
    if match is None:
        roots = ", ".join(str(m.local_root) for m in mounts)
        raise PathMappingError(
            f"Path is not under any configured mount root.\n"
            f"Path: {resolved}\n"
            f"Configured roots: {roots}"
        )

    relative = resolved.relative_to(match.local_root)
    if str(relative) == ".":
        raise PathMappingError(
            f"Path is the mount root itself, not a file or folder inside it: {resolved}"
        )

    remote_relative = relative.as_posix()
    return f"{match.remote}:{remote_relative}"


def find_mount_for_path(
    resolved_path: Path,
    mounts: tuple[MountMapping, ...],
) -> MountMapping | None:
    """Return the longest matching mount root for a resolved local path."""
    best: MountMapping | None = None
    best_len = -1

    for mount in mounts:
        root = mount.local_root
        if _is_under_root(resolved_path, root):
            root_len = len(root.parts)
            if root_len > best_len:
                best = mount
                best_len = root_len

    return best


def _is_under_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def resolve_target_folder_remote_path(
    local_path: Path,
    mounts: tuple[MountMapping, ...],
) -> str:
    """Map a local selection to the remote path of the folder where new files belong."""
    if not mounts:
        raise PathMappingError("No mount mappings are configured.")

    try:
        resolved = local_path.expanduser().resolve()
    except OSError as exc:
        raise PathMappingError(f"Cannot resolve local path {local_path}: {exc}") from exc

    if not resolved.exists():
        raise PathMappingError(f"Local path does not exist: {resolved}")

    match = find_mount_for_path(resolved, mounts)
    if match is None:
        roots = ", ".join(str(m.local_root) for m in mounts)
        raise PathMappingError(
            f"Path is not under any configured mount root.\n"
            f"Path: {resolved}\n"
            f"Configured roots: {roots}"
        )

    if resolved == match.local_root:
        folder_local = resolved
    elif resolved.is_dir():
        folder_local = resolved
    else:
        folder_local = resolved.parent

    if folder_local == match.local_root:
        return f"{match.remote}:"

    return local_to_remote_path(folder_local, mounts)
