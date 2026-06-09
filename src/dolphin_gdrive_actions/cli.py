from __future__ import annotations

import argparse

from dolphin_gdrive_actions import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dga",
        description="Google Drive-style actions for rclone-mounted files in KDE Dolphin.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    copy_link = subparsers.add_parser(
        "copy-link",
        help="Resolve a Google Drive file-ID URL for a mounted path and print it.",
    )
    copy_link.add_argument(
        "local_path",
        help="Local filesystem path under a configured mount root",
    )
    copy_link.add_argument(
        "--config",
        help="Path to config file (default: $XDG_CONFIG_HOME/dolphin-gdrive-actions/config.toml)",
    )
    copy_link.add_argument(
        "--clipboard",
        action="store_true",
        help="Also copy the URL to the clipboard (best effort; failures are ignored).",
    )

    open_drive = subparsers.add_parser(
        "open",
        help="Open a Google Drive item in the default browser by file ID.",
    )
    open_drive.add_argument(
        "local_path",
        help="Local filesystem path under a configured mount root",
    )
    open_drive.add_argument(
        "--config",
        help="Path to config file (default: $XDG_CONFIG_HOME/dolphin-gdrive-actions/config.toml)",
    )

    open_folder = subparsers.add_parser(
        "open-folder",
        help="Open the containing Google Drive folder in the default browser.",
    )
    open_folder.add_argument(
        "local_path",
        help="Local filesystem path under a configured mount root (file or folder)",
    )
    open_folder.add_argument(
        "--config",
        help="Path to config file (default: $XDG_CONFIG_HOME/dolphin-gdrive-actions/config.toml)",
    )

    new = subparsers.add_parser(
        "new",
        help="Open a blank Google Workspace editor in the browser for a target folder.",
    )
    new.add_argument(
        "type",
        choices=["doc", "sheet", "slide", "drawing"],
        help="Google Workspace file type to create",
    )
    new.add_argument(
        "local_path",
        help="Local filesystem path under a configured mount root (file or folder)",
    )
    new.add_argument(
        "--config",
        help="Path to config file (default: $XDG_CONFIG_HOME/dolphin-gdrive-actions/config.toml)",
    )

    offline = subparsers.add_parser(
        "offline",
        help="Best-effort offline access for a mounted Drive item.",
    )
    offline.add_argument(
        "local_path",
        help="Local filesystem path under a configured mount root",
    )
    offline.add_argument(
        "--config",
        help="Path to config file (default: $XDG_CONFIG_HOME/dolphin-gdrive-actions/config.toml)",
    )

    config = subparsers.add_parser(
        "config",
        help="View or update dga configuration values.",
    )
    config_subparsers = config.add_subparsers(dest="config_command", required=True)
    config_set = config_subparsers.add_parser(
        "set",
        help="Set a configuration value.",
    )
    config_set.add_argument(
        "key",
        help="Configuration key (supported: google_authuser)",
    )
    config_set.add_argument(
        "value",
        help="Value to store, or remote name when key is google_authuser",
    )
    config_set.add_argument(
        "value2",
        nargs="?",
        default=None,
        help="Account index or email when key is google_authuser",
    )
    config_set.add_argument(
        "--config",
        help="Path to config file (default: $XDG_CONFIG_HOME/dolphin-gdrive-actions/config.toml)",
    )

    setup = subparsers.add_parser(
        "setup",
        help="Auto-detect rclone mounts, write config, and install Dolphin service menus.",
    )
    setup.add_argument(
        "--mount-root",
        action="append",
        help="Local mount root to configure (repeat with --remote for multiple mounts).",
    )
    setup.add_argument(
        "--remote",
        action="append",
        help="rclone remote name matching --mount-root.",
    )
    setup.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing config and install manifest.",
    )

    subparsers.add_parser(
        "uninstall",
        help="Remove installed service menus, config, and install manifest.",
    )

    subparsers.add_parser(
        "status",
        help="Show installed integration state.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "copy-link":
        from dolphin_gdrive_actions.commands import cmd_copy_link

        return cmd_copy_link(args)

    if args.command == "open":
        from dolphin_gdrive_actions.commands import cmd_open

        return cmd_open(args)

    if args.command == "open-folder":
        from dolphin_gdrive_actions.commands import cmd_open_folder

        return cmd_open_folder(args)

    if args.command == "config":
        if args.config_command == "set":
            from dolphin_gdrive_actions.commands import cmd_config_set

            return cmd_config_set(args)
        parser.error(f"Unknown config command: {args.config_command}")
        return 1

    if args.command == "new":
        from dolphin_gdrive_actions.commands import cmd_new

        return cmd_new(args)

    if args.command == "offline":
        from dolphin_gdrive_actions.commands import cmd_offline

        return cmd_offline(args)

    if args.command == "setup":
        from dolphin_gdrive_actions.integration import cmd_setup

        return cmd_setup(args)

    if args.command == "uninstall":
        from dolphin_gdrive_actions.integration import cmd_uninstall

        return cmd_uninstall(args)

    if args.command == "status":
        from dolphin_gdrive_actions.integration import cmd_status

        return cmd_status(args)

    parser.error(f"Unknown command: {args.command}")
    return 1
