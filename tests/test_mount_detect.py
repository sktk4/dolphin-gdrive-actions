from pathlib import Path

import pytest

from dolphin_gdrive_actions.errors import SetupError
from dolphin_gdrive_actions.mount_detect import (
    _parse_findmnt_output,
    _parse_proc_mounts,
    detect_mounts,
)


def test_parse_findmnt_output() -> None:
    output = "personal: /home/user/Drives/personal\nwork: /home/user/Drives/work\n"
    assert _parse_findmnt_output(output) == [
        ("personal:", "/home/user/Drives/personal"),
        ("work:", "/home/user/Drives/work"),
    ]


def test_parse_proc_mounts() -> None:
    content = (
        "personal: on /home/user/Drives/personal type fuse.rclone (rw,nosuid,nodev)\n"
        "tmpfs on /run type tmpfs (rw)\n"
    )
    assert _parse_proc_mounts(content) == [("personal:", "/home/user/Drives/personal")]


def test_detect_mounts_from_flags(tmp_path: Path) -> None:
    root = tmp_path / "mount"
    root.mkdir()
    mounts = detect_mounts(mount_roots=[str(root)], remotes=["personal"])
    assert len(mounts) == 1
    assert mounts[0].local_root == root.resolve()
    assert mounts[0].remote == "personal"


def test_detect_mounts_flag_mismatch_raises() -> None:
    with pytest.raises(SetupError, match="same number"):
        detect_mounts(mount_roots=["/a"], remotes=[])


def test_normalize_remote_source_strips_hash_suffix() -> None:
    from dolphin_gdrive_actions.mount_detect import _normalize_remote_source

    assert _normalize_remote_source("personal{AbCdE}:") == "personal"


def test_detect_mounts_auto(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "drive"
    root.mkdir()
    monkeypatch.setattr(
        "dolphin_gdrive_actions.mount_detect._read_mount_lines",
        lambda: [("personal:", str(root))],
    )
    mounts = detect_mounts()
    assert mounts[0].remote == "personal"
    assert mounts[0].local_root == root.resolve()
