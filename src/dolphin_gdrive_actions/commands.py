from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dolphin_gdrive_actions.browser import open_url, open_url_app
from dolphin_gdrive_actions.clipboard import copy_text_to_clipboard
from dolphin_gdrive_actions.config import default_config_path, load_config, set_mount_google_authuser
from dolphin_gdrive_actions.drive_account import get_drive_account_email
from dolphin_gdrive_actions.drive_metadata import (
    DriveItemMetadata,
    build_drive_folder_url,
    build_drive_share_url,
    build_drive_url,
    build_my_drive_url,
    build_workspace_create_url,
    is_google_workspace_file,
    split_remote_path,
)
from dolphin_gdrive_actions.errors import ConfigError, DgaError, RcloneMetadataError
from dolphin_gdrive_actions.remote_resolve import rewrite_if_combine
from dolphin_gdrive_actions.notify import notify_error, notify_success
from dolphin_gdrive_actions.paths import (
    find_mount_for_path,
    local_to_remote_path,
    resolve_target_folder_remote_path,
)
from dolphin_gdrive_actions.rclone import stat_item_with_combine_fallback

def cmd_copy_link(args: argparse.Namespace) -> int:
    try:
        url = _resolve_drive_copy_url(args)
        print(url)

        if args.clipboard and not copy_text_to_clipboard(url):
            _report_clipboard_failure()

        return 0
    except DgaError as exc:
        _report_error(exc.message, exc.exit_code, title="Google Drive link failed")
        return exc.exit_code


def cmd_open(args: argparse.Namespace) -> int:
    try:
        url = _resolve_drive_open_url(args)
        open_url_app(url)

        if sys.stdout.isatty():
            print(f"Opened: {url}")

        return 0
    except DgaError as exc:
        _report_error(exc.message, exc.exit_code, title="Open with Google Drive failed")
        return exc.exit_code


def cmd_open_folder(args: argparse.Namespace) -> int:
    try:
        url = _resolve_drive_folder_url(args)
        open_url_app(url)

        if sys.stdout.isatty():
            print(f"Opened: {url}")

        return 0
    except DgaError as exc:
        _report_error(exc.message, exc.exit_code, title="Open Drive folder failed")
        return exc.exit_code


def cmd_config_set(args: argparse.Namespace) -> int:
    try:
        config_path = Path(args.config) if args.config else None
        path = config_path or default_config_path()
        if args.key != "google_authuser":
            raise ConfigError(
                f"Unsupported config key: {args.key}\n"
                "Supported keys: google_authuser"
            )
        if not args.value2:
            raise ConfigError(
                "Usage: dga config set google_authuser REMOTE INDEX_OR_EMAIL\n"
                "Example: dga config set google_authuser WorkDrive 1"
            )
        set_mount_google_authuser(args.value, args.value2, config_path)
        print(f"Set google_authuser for remote {args.value} in {path}")
        return 0
    except DgaError as exc:
        _report_error(exc.message, exc.exit_code, title="Config update failed")
        return exc.exit_code


def cmd_new(args: argparse.Namespace) -> int:
    try:
        url = _resolve_workspace_create_url(args)
        open_url(url)

        if sys.stdout.isatty():
            print(f"Opened: {url}")

        return 0
    except DgaError as exc:
        _report_error(exc.message, exc.exit_code, title="New Google Drive file failed")
        return exc.exit_code


def cmd_offline(args: argparse.Namespace) -> int:
    try:
        local_path = Path(args.local_path)
        remote_path = _resolve_remote_path(args)
        metadata = _lookup_drive_metadata(remote_path)

        if is_google_workspace_file(metadata.mime_type):
            url = build_drive_url(metadata.item_id, is_dir=metadata.is_dir)
            open_url(url)
            message = (
                "Opened this Google Workspace file in Drive.\n"
                "Use Drive's offline settings in the browser to make it available offline."
            )
            _report_success("Available offline", message, url=url)
            return 0

        _warm_local_cache(local_path)
        message = (
            "Read this item through the rclone mount to warm the local VFS cache.\n"
            "This is not the same as Google Drive for desktop offline sync."
        )
        _report_success("Available offline", message)
        return 0
    except DgaError as exc:
        _report_error(exc.message, exc.exit_code, title="Available offline failed")
        return exc.exit_code


def _resolve_drive_folder_url(args: argparse.Namespace) -> str:
    config_path = Path(args.config) if args.config else None
    config = load_config(config_path)
    local_path = Path(args.local_path)
    remote_folder_path = resolve_target_folder_remote_path(
        local_path,
        config.mounts,
    )
    metadata = _lookup_drive_metadata(remote_folder_path)
    if not metadata.is_dir:
        raise RcloneMetadataError(
            f"Target folder metadata is not a directory: {remote_folder_path}"
        )
    folder_id = metadata.item_id
    mount = find_mount_for_path(local_path.expanduser().resolve(), config.mounts)
    authuser = _resolve_google_authuser(mount, remote_folder_path)
    if not folder_id:
        return build_my_drive_url(authuser=authuser)
    return build_drive_folder_url(folder_id, authuser=authuser)


def _resolve_workspace_create_url(args: argparse.Namespace) -> str:
    config_path = Path(args.config) if args.config else None
    config = load_config(config_path)
    local_path = Path(args.local_path)
    remote_folder_path = resolve_target_folder_remote_path(
        local_path,
        config.mounts,
    )
    metadata = _lookup_drive_metadata(remote_folder_path)
    if not metadata.is_dir:
        raise RcloneMetadataError(
            f"Target folder metadata is not a directory: {remote_folder_path}"
        )
    folder_id = metadata.item_id or None
    mount = find_mount_for_path(local_path.expanduser().resolve(), config.mounts)
    authuser = _resolve_google_authuser(mount, remote_folder_path)
    return build_workspace_create_url(args.type, folder_id, authuser=authuser)


def _resolve_google_authuser(
    mount: object | None,
    remote_folder_path: str,
) -> str | None:
    google_authuser = getattr(mount, "google_authuser", None) if mount else None
    if google_authuser:
        return google_authuser
    lookup_path = rewrite_if_combine(remote_folder_path) or remote_folder_path
    remote_name, _relative = split_remote_path(lookup_path)
    return get_drive_account_email(remote_name)


def _resolve_drive_open_url(args: argparse.Namespace) -> str:
    remote_path = _resolve_remote_path(args)
    metadata = _lookup_drive_metadata(remote_path)
    return build_drive_url(metadata.item_id, is_dir=metadata.is_dir)


def _resolve_drive_copy_url(args: argparse.Namespace) -> str:
    remote_path = _resolve_remote_path(args)
    metadata = _lookup_drive_metadata(remote_path)
    return build_drive_share_url(metadata.item_id, is_dir=metadata.is_dir)


def _lookup_drive_metadata(remote_path: str) -> DriveItemMetadata:
    return stat_item_with_combine_fallback(remote_path)


def _resolve_remote_path(args: argparse.Namespace) -> str:
    config_path = Path(args.config) if args.config else None
    config = load_config(config_path)
    return local_to_remote_path(Path(args.local_path), config.mounts)


def _warm_local_cache(local_path: Path) -> None:
    resolved = local_path.expanduser().resolve()
    if resolved.is_dir():
        for _ in resolved.iterdir():
            break
        return

    with resolved.open("rb") as handle:
        handle.read(65536)


_CLIPBOARD_FAILURE_MESSAGE = (
    "The link was resolved but could not be copied to the clipboard.\n"
    "Ensure Klipper is running or install a clipboard tool such as wl-clipboard."
)


def _report_clipboard_failure() -> None:
    if sys.stderr.isatty():
        print("Could not copy link to clipboard.", file=sys.stderr)
    else:
        notify_error("Copy Google Drive link failed", _CLIPBOARD_FAILURE_MESSAGE)
        print(_CLIPBOARD_FAILURE_MESSAGE, file=sys.stderr)


def _report_error(message: str, exit_code: int, *, title: str) -> None:
    if sys.stderr.isatty():
        print(message, file=sys.stderr)
    else:
        notify_error(title, message)
        print(message, file=sys.stderr)


def _report_success(title: str, message: str, *, url: str | None = None) -> None:
    if sys.stdout.isatty():
        if url:
            print(f"Opened: {url}")
        print(message)
    else:
        notify_success(title, message)
