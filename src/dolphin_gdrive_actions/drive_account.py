from __future__ import annotations

import json
import shutil
import subprocess
import urllib.error
import urllib.request
from functools import lru_cache

from dolphin_gdrive_actions.remote_resolve import _load_rclone_config_dump


def resolve_drive_remote_name(remote_name: str) -> str:
    """Follow rclone alias remotes to the underlying drive remote name."""
    config = _load_rclone_config_dump()
    entry = config.get(remote_name)
    if not isinstance(entry, dict):
        return remote_name
    if entry.get("type") != "alias":
        return remote_name
    target = entry.get("remote")
    if not isinstance(target, str) or not target.strip():
        return remote_name
    base = target.split(",", 1)[0].strip()
    if not base:
        return remote_name
    return resolve_drive_remote_name(base)


@lru_cache(maxsize=32)
def get_drive_account_email(remote_name: str) -> str | None:
    """Return the Google account email for an rclone drive remote (via Drive about API)."""
    drive_remote = resolve_drive_remote_name(remote_name)
    rclone = shutil.which("rclone")
    if not rclone:
        return None

    try:
        subprocess.run(
            [rclone, "lsjson", f"{drive_remote}:", "--max-depth", "1", "--files-only"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    config = _load_rclone_config_dump()
    entry = config.get(drive_remote)
    if not isinstance(entry, dict):
        return None
    raw_token = entry.get("token")
    if not isinstance(raw_token, str) or not raw_token.strip():
        return None

    try:
        token = json.loads(raw_token)
    except json.JSONDecodeError:
        return None

    access_token = token.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        return None

    request = urllib.request.Request(
        "https://www.googleapis.com/drive/v3/about?fields=user",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
        return None

    user = payload.get("user")
    if not isinstance(user, dict):
        return None
    email = user.get("emailAddress")
    if isinstance(email, str) and email.strip():
        return email.strip()
    return None
