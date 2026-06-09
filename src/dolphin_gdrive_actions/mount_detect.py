from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from dolphin_gdrive_actions.config import MountMapping
from dolphin_gdrive_actions.errors import SetupError


@dataclass(frozen=True)
class DetectedMount:
    local_root: Path
    remote: str


def detect_mounts(
    *,
    mount_roots: list[str] | None = None,
    remotes: list[str] | None = None,
) -> tuple[MountMapping, ...]:
    if mount_roots is not None or remotes is not None:
        return _mounts_from_flags(mount_roots or [], remotes or [])

    detected = _detect_active_rclone_mounts()
    if not detected:
        raise SetupError(
            "No active rclone FUSE mounts were found.\n"
            "Mount your Google Drive with rclone first, or pass explicit mappings:\n"
            "  dga setup --mount-root /path/to/mount --remote your-remote"
        )

    return tuple(
        MountMapping(local_root=item.local_root, remote=item.remote) for item in detected
    )


def _mounts_from_flags(mount_roots: list[str], remotes: list[str]) -> tuple[MountMapping, ...]:
    if not mount_roots and not remotes:
        return detect_mounts()
    if len(mount_roots) != len(remotes):
        raise SetupError(
            "When using --mount-root and --remote, provide the same number of each.\n"
            f"Got {len(mount_roots)} mount root(s) and {len(remotes)} remote(s)."
        )
    if not mount_roots:
        raise SetupError("Provide at least one --mount-root and --remote pair.")

    mounts: list[MountMapping] = []
    for raw_root, raw_remote in zip(mount_roots, remotes, strict=True):
        root = Path(raw_root).expanduser().resolve()
        if not root.is_dir():
            raise SetupError(f"Mount root does not exist or is not a directory: {root}")
        remote = raw_remote.strip().rstrip(":")
        if not remote:
            raise SetupError("Remote name cannot be empty.")
        mounts.append(MountMapping(local_root=root, remote=remote))
    return tuple(mounts)


def _detect_active_rclone_mounts() -> list[DetectedMount]:
    lines = _read_mount_lines()
    mounts: list[DetectedMount] = []
    for source, target in lines:
        remote = _normalize_remote_source(source)
        if remote is None:
            continue
        local_root = Path(target).resolve()
        if not local_root.is_dir():
            continue
        mounts.append(DetectedMount(local_root=local_root, remote=remote))
    return mounts


def _read_mount_lines() -> list[tuple[str, str]]:
    if shutil.which("findmnt"):
        return _parse_findmnt_output(_run_command(["findmnt", "-rn", "-t", "fuse.rclone", "-o", "SOURCE,TARGET"]))
    if Path("/proc/mounts").is_file():
        return _parse_proc_mounts(Path("/proc/mounts").read_text(encoding="utf-8"))
    if shutil.which("mount"):
        return _parse_mount_output(_run_command(["mount", "-t", "fuse.rclone"]))
    return []


def _run_command(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout


def _parse_findmnt_output(output: str) -> list[tuple[str, str]]:
    mounts: list[tuple[str, str]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        mounts.append((parts[0], parts[1]))
    return mounts


_PROC_MOUNT_RE = re.compile(r"^(?P<source>\S+): on (?P<target>\S+) type fuse\.rclone\b")


def _parse_proc_mounts(content: str) -> list[tuple[str, str]]:
    mounts: list[tuple[str, str]] = []
    for line in content.splitlines():
        match = _PROC_MOUNT_RE.match(line)
        if match:
            source = match.group("source")
            if not source.endswith(":"):
                source = f"{source}:"
            mounts.append((source, match.group("target")))
    return mounts


def _parse_mount_output(output: str) -> list[tuple[str, str]]:
    return _parse_proc_mounts(output)


def _normalize_remote_source(source: str) -> str | None:
    source = source.strip()
    if not source.endswith(":"):
        return None
    remote = source[:-1].strip()
    if not remote:
        return None
    # FUSE mount sources may include an rclone suffix like personal{AbCdE}.
    remote = re.sub(r"\{[^}]+\}$", "", remote)
    return remote or None


def list_rclone_remotes() -> set[str]:
    if not shutil.which("rclone"):
        return set()
    output = _run_command(["rclone", "listremotes"])
    remotes: set[str] = set()
    for line in output.splitlines():
        line = line.strip().rstrip(":")
        if line:
            remotes.add(line)
    return remotes
