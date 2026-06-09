from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from importlib.resources import files
from pathlib import Path

from dolphin_gdrive_actions.config import MountMapping, default_config_path, load_config
from dolphin_gdrive_actions.config import read_config_data
from dolphin_gdrive_actions.errors import ConfigError, DgaError, SetupError
from dolphin_gdrive_actions.servicemenu_diag import diagnose_servicemenu
from dolphin_gdrive_actions.manifest import (
    InstalledFile,
    InstallManifest,
    load_manifest,
    manifest_exists,
    write_manifest,
)
from dolphin_gdrive_actions.mount_detect import detect_mounts, list_rclone_remotes
from dolphin_gdrive_actions.paths_util import (
    app_data_dir,
    config_dir,
    installed_icons_dir,
    manifest_path,
    servicemenu_dir,
)


def cmd_setup(args: argparse.Namespace) -> int:
    try:
        config_path = default_config_path()
        if config_path.exists() and not args.force:
            raise SetupError(
                f"Config already exists: {config_path}\n"
                "Run `dga uninstall` first, or pass --force to overwrite."
            )
        if manifest_exists() and not args.force:
            raise SetupError(
                f"Install manifest already exists: {manifest_path()}\n"
                "Run `dga uninstall` first, or pass --force to overwrite."
            )

        mounts = detect_mounts(mount_roots=args.mount_root, remotes=args.remote)
        dga_path = resolve_dga_path()
        _warn_unknown_remotes(mounts)

        config_dir().mkdir(parents=True, exist_ok=True)
        write_config_file(config_path, mounts)

        installed_icons, icon_paths = install_icons()
        installed_files = installed_icons + install_servicemenus(dga_path, icon_paths)
        write_manifest(dga_path=dga_path, files=installed_files)

        print(f"Installed integration using {dga_path}")
        print(f"Config: {config_path}")
        print(f"Icons: {installed_icons_dir()}")
        for installed in installed_files:
            if installed.kind == "servicemenu":
                print(f"Service menu: {installed.path}")
        return 0
    except DgaError as exc:
        print(exc.message, file=sys.stderr)
        return exc.exit_code


def cmd_uninstall(_args: argparse.Namespace) -> int:
    warnings: list[str] = []
    removed: list[str] = []

    if manifest_exists():
        manifest = load_manifest()
        for installed in manifest.files:
            result = _remove_installed_file(installed, manifest)
            if result == "removed":
                removed.append(str(installed.path))
            elif result == "missing":
                warnings.append(f"Already missing: {installed.path}")
            else:
                warnings.append(result)
    else:
        warnings.append(f"No install manifest found at {manifest_path()}")

    _remove_legacy_servicemenus(servicemenu_dir())

    for path in (default_config_path(), manifest_path()):
        if path.exists():
            path.unlink()
            removed.append(str(path))

    _remove_dir_if_empty(installed_icons_dir())
    _remove_dir_if_empty(app_data_dir())
    _remove_dir_if_empty(config_dir())

    if removed:
        print("Removed:")
        for item in removed:
            print(f"  {item}")
    if warnings:
        print("Warnings:", file=sys.stderr)
        for item in warnings:
            print(f"  {item}", file=sys.stderr)

    if not removed and warnings:
        return 1
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    dga_path = shutil.which("dga")
    print(f"dga on PATH: {dga_path or 'not found'}")

    if manifest_exists():
        manifest = load_manifest()
        print(f"Install manifest: {manifest_path()}")
        print(f"Recorded dga path: {manifest.dga_path}")
        print(f"Installed at: {manifest.installed_at}")
        for installed in manifest.files:
            state = _file_state(installed)
            print(f"  {installed.path}: {state}")
        if dga_path and Path(dga_path) != manifest.dga_path:
            print("Warning: dga on PATH differs from manifest; run `dga setup --force` to refresh.")
    else:
        print(f"Install manifest: missing ({manifest_path()})")

    config_path = default_config_path()
    if config_path.exists():
        print(f"Config: {config_path}")
        try:
            config = load_config(config_path)
            for mount in config.mounts:
                exists = mount.local_root.is_dir()
                print(f"  {mount.local_root} -> {mount.remote} ({'ok' if exists else 'missing'})")
        except DgaError as exc:
            print(f"  invalid: {exc.message}")
    else:
        print(f"Config: missing ({config_path})")

    try:
        detected = detect_mounts()
        print("Active rclone mounts:")
        for mount in detected:
            print(f"  {mount.local_root} -> {mount.remote}")
    except SetupError:
        print("Active rclone mounts: none detected")

    menu_path = servicemenu_dir() / "google-drive.desktop"
    diagnosis = diagnose_servicemenu(menu_path)
    if diagnosis.get("separator_tokens"):
        ready = diagnosis.get("separator_ready")
        print(
            f"Service menu separators ({menu_path.name}): "
            f"{'ready' if ready else 'misconfigured'}"
        )

    return 0


def resolve_dga_path() -> Path:
    discovered = shutil.which("dga")
    if discovered:
        return Path(discovered).resolve()
    return Path(sys.argv[0]).resolve()


def write_config_file(path: Path, mounts: tuple[MountMapping, ...]) -> None:
    preserved_authusers: dict[str, str] = {}
    if path.is_file():
        try:
            data = read_config_data(path)
            raw_mounts = data.get("mounts")
            if isinstance(raw_mounts, list):
                for entry in raw_mounts:
                    if not isinstance(entry, dict):
                        continue
                    local_root = entry.get("local_root")
                    authuser = entry.get("google_authuser")
                    if (
                        isinstance(local_root, str)
                        and isinstance(authuser, str)
                        and authuser.strip()
                    ):
                        preserved_authusers[str(Path(local_root).expanduser().resolve())] = (
                            authuser.strip()
                        )
        except ConfigError:
            pass

    lines = [
        "# Generated by dga setup. Re-run `dga setup --force` after mount changes.",
        "",
    ]
    for mount in mounts:
        lines.extend(
            [
                "[[mounts]]",
                f'local_root = "{_toml_escape(str(mount.local_root))}"',
                f'remote = "{_toml_escape(mount.remote)}"',
            ]
        )
        authuser = mount.google_authuser or preserved_authusers.get(str(mount.local_root))
        if authuser:
            lines.append(f'google_authuser = "{_toml_escape(authuser)}"')
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def install_icons() -> tuple[list[InstalledFile], dict[str, Path]]:
    target_dir = installed_icons_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    installed: list[InstalledFile] = []
    icon_paths: dict[str, Path] = {}
    icon_dir = files("dolphin_gdrive_actions.data") / "icons"
    for entry in sorted(icon_dir.iterdir(), key=lambda item: item.name):
        if not entry.name.endswith(".png"):
            continue
        destination = target_dir / entry.name
        shutil.copyfile(entry, destination)
        icon_paths[entry.name] = destination
        installed.append(
            InstalledFile(
                path=destination,
                kind="icon",
                source=entry.name,
                content=_file_sha256(destination),
            )
        )
    if not installed:
        raise SetupError("No icon PNGs found in package data.")
    return installed, icon_paths


def install_servicemenus(
    dga_path: Path,
    icon_paths: dict[str, Path] | None = None,
) -> list[InstalledFile]:
    target_dir = servicemenu_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    _remove_legacy_servicemenus(target_dir)

    installed: list[InstalledFile] = []
    menu_dir = files("dolphin_gdrive_actions.data") / "servicemenus"
    for entry in sorted(menu_dir.iterdir(), key=lambda item: item.name):
        if not entry.name.endswith(".desktop"):
            continue
        template = entry.read_text(encoding="utf-8")
        rendered = render_desktop_template(template, dga_path, icon_paths or {})
        destination = target_dir / entry.name
        destination.write_text(rendered, encoding="utf-8")
        os.chmod(destination, 0o755)
        installed.append(
            InstalledFile(
                path=destination,
                kind="servicemenu",
                source=entry.name,
                content=destination.read_text(encoding="utf-8"),
            )
        )
    if not installed:
        raise SetupError("No service menu templates found in package data.")
    return installed


_LEGACY_SERVICEMENUS = (
    "copy-google-drive-link.desktop",
    "open-with-google-drive.desktop",
    "google-drive-offline.desktop",
    "google-drive.desktop",
)


def _remove_legacy_servicemenus(target_dir: Path) -> None:
    for name in _LEGACY_SERVICEMENUS:
        stale = target_dir / name
        if stale.is_file():
            stale.unlink()
    for stale in target_dir.glob("gd-*.desktop"):
        stale.unlink()


def render_desktop_template(
    content: str,
    dga_path: Path,
    icon_paths: dict[str, Path] | None = None,
) -> str:
    rendered = content.replace("Exec=dga ", f"Exec={dga_path} ")
    for name, path in (icon_paths or {}).items():
        rendered = rendered.replace(f"Icon={name}", f"Icon={path}")
        rendered = rendered.replace(f"X-KDE-Submenu-Icon={name}", f"X-KDE-Submenu-Icon={path}")
    return rendered


def render_desktop_exec(content: str, dga_path: Path) -> str:
    return render_desktop_template(content, dga_path)


def _collect_top_level_action_keys(menu_dir: Path) -> list[str]:
    path = menu_dir / "google-drive.desktop"
    if not path.is_file():
        return []
    diagnosis = diagnose_servicemenu(path)
    action_keys = diagnosis.get("action_keys")
    if isinstance(action_keys, list):
        return [str(key) for key in action_keys]
    return []


def _warn_unknown_remotes(mounts: tuple[MountMapping, ...]) -> None:
    known = list_rclone_remotes()
    if not known:
        return
    for mount in mounts:
        if mount.remote not in known:
            print(
                f"Warning: remote {mount.remote!r} not listed by `rclone listremotes`, "
                "but the mount is active.",
                file=sys.stderr,
            )


def _remove_installed_file(installed: InstalledFile, manifest: InstallManifest) -> str:
    path = installed.path
    if not path.exists():
        return "missing"
    if installed.kind == "icon":
        if _file_sha256(path) != installed.content:
            return f"Skipped modified file: {path}"
        path.unlink()
        return "removed"
    current = path.read_text(encoding="utf-8")
    if not _is_safe_to_remove(current, installed, manifest):
        return f"Skipped modified file: {path}"
    path.unlink()
    return "removed"


def _normalize_desktop_content(content: str) -> str:
    return content.rstrip("\n")


def _is_safe_to_remove(current: str, installed: InstalledFile, manifest: InstallManifest) -> bool:
    if _normalize_desktop_content(current) == _normalize_desktop_content(installed.content):
        return True
    exec_line = _extract_exec_line(current)
    if exec_line is None:
        return False
    dga = str(manifest.dga_path)
    return (
        dga in exec_line
        or "dga open " in exec_line
        or "dga copy-link " in exec_line
        or "dga open-folder " in exec_line
        or "dga offline " in exec_line
        or "dga new " in exec_line
    )


def _extract_exec_line(content: str) -> str | None:
    for line in content.splitlines():
        if line.startswith("Exec="):
            return line
    return None


def _file_state(installed: InstalledFile) -> str:
    path = installed.path
    if not path.exists():
        return "missing"
    if installed.kind == "icon":
        if _file_sha256(path) == installed.content:
            return "installed"
        return "modified"
    current = path.read_text(encoding="utf-8")
    if _normalize_desktop_content(current) == _normalize_desktop_content(installed.content):
        return "installed"
    return "modified"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _remove_dir_if_empty(path: Path) -> None:
    if path.exists() and path.is_dir() and not any(path.iterdir()):
        path.rmdir()


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
