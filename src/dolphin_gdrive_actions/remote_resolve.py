from __future__ import annotations

import json
import re
import shutil
import subprocess
from functools import lru_cache

_UPSTREAM_ENTRY_RE = re.compile(r"^([^=]+)=(.+)$")


def rewrite_combine_remote_path(remote_path: str, upstreams: dict[str, str]) -> str | None:
    """Map a combine remote path to its upstream remote path, if possible."""
    _remote_name, _, relative = remote_path.partition(":")
    if not relative:
        return None

    top_dir, _, remainder = relative.partition("/")
    upstream = upstreams.get(top_dir)
    if upstream is None:
        return None

    upstream = upstream.strip()
    if not upstream or ":" not in upstream:
        return None

    up_remote, _, up_path = upstream.partition(":")
    up_path = up_path.strip("/")
    if remainder:
        new_rel = f"{up_path}/{remainder}" if up_path else remainder
    else:
        new_rel = up_path

    if new_rel:
        return f"{up_remote}:{new_rel}"
    return f"{up_remote}:"


def parse_combine_upstreams(raw: str) -> dict[str, str]:
    """Parse rclone combine ``upstreams`` config into dir → remote:path."""
    upstreams: dict[str, str] = {}
    for token in raw.split():
        token = token.strip().strip('"').strip("'")
        if not token:
            continue
        match = _UPSTREAM_ENTRY_RE.match(token)
        if match is None:
            continue
        dir_name = match.group(1).strip()
        target = match.group(2).strip()
        if dir_name and target:
            upstreams[dir_name] = target
    return upstreams


@lru_cache(maxsize=32)
def get_combine_upstreams(remote_name: str) -> dict[str, str] | None:
    """Return combine upstream map for ``remote_name``, or None if not combine."""
    config = _load_rclone_config_dump()
    entry = config.get(remote_name)
    if not isinstance(entry, dict):
        return None
    if entry.get("type") != "combine":
        return None
    raw_upstreams = entry.get("upstreams")
    if not isinstance(raw_upstreams, str) or not raw_upstreams.strip():
        return None
    parsed = parse_combine_upstreams(raw_upstreams)
    return parsed or None


def rewrite_if_combine(remote_path: str) -> str | None:
    """Return an upstream remote path when ``remote_path`` uses a combine remote."""
    remote_name, _, _relative = remote_path.partition(":")
    if not remote_name:
        return None
    upstreams = get_combine_upstreams(remote_name)
    if upstreams is None:
        return None
    return rewrite_combine_remote_path(remote_path, upstreams)


def _load_rclone_config_dump() -> dict[str, object]:
    rclone = shutil.which("rclone")
    if not rclone:
        return {}
    try:
        result = subprocess.run(
            [rclone, "config", "dump"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return {}
    if result.returncode != 0:
        return {}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload
