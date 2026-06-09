from __future__ import annotations

import shutil
import subprocess


def copy_text_to_clipboard(text: str) -> bool:
    """Copy text to the clipboard. Returns True on success, False if unavailable."""
    if _try_kde_klipper(text):
        return True

    if _try_command(["wl-copy"], text, stdin=True):
        return True

    if _try_command(["xclip", "-selection", "clipboard"], text, stdin=True):
        return True

    return False


def _try_kde_klipper(text: str) -> bool:
    for qdbus_cmd in ("qdbus6", "qdbus"):
        if _try_qdbus_klipper(qdbus_cmd, text):
            return True
    return False


def _try_qdbus_klipper(qdbus_cmd: str, text: str) -> bool:
    if not shutil.which(qdbus_cmd):
        return False

    try:
        result = subprocess.run(
            [
                qdbus_cmd,
                "org.kde.klipper",
                "/klipper",
                "setClipboardContents",
                text,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False

    return result.returncode == 0


def _try_command(command: list[str], text: str, *, stdin: bool) -> bool:
    if not shutil.which(command[0]):
        return False

    try:
        result = subprocess.run(
            command,
            input=text if stdin else None,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False

    return result.returncode == 0
