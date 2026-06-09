from __future__ import annotations

import shutil
import subprocess


def notify_error(title: str, message: str) -> None:
    """Show a desktop notification for errors when not running in a terminal."""
    _notify(title, message)


def notify_success(title: str, message: str) -> None:
    """Show a desktop notification for successful non-TTY actions."""
    _notify(title, message)


def _notify(title: str, message: str) -> None:
    if shutil.which("notify-send"):
        subprocess.run(
            ["notify-send", title, message],
            check=False,
        )
