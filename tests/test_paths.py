import pytest
from pathlib import Path

from dolphin_gdrive_actions.config import MountMapping
from dolphin_gdrive_actions.errors import PathMappingError
from dolphin_gdrive_actions.paths import (
    find_mount_for_path,
    local_to_remote_path,
    resolve_target_folder_remote_path,
)


def _mounts(tmp_path: Path) -> tuple[MountMapping, ...]:
    root = tmp_path / "drives" / "personal"
    nested = tmp_path / "drives" / "work"
    root.mkdir(parents=True)
    nested.mkdir(parents=True)
    return (
        MountMapping(local_root=root.resolve(), remote="personal"),
        MountMapping(local_root=nested.resolve(), remote="work"),
    )


def test_local_to_remote_path_happy_path(tmp_path: Path) -> None:
    mounts = _mounts(tmp_path)
    target = mounts[0].local_root / "Misc" / "File.txt"
    target.parent.mkdir()
    target.write_text("hello")

    assert local_to_remote_path(target, mounts) == "personal:Misc/File.txt"


def test_local_to_remote_path_with_spaces(tmp_path: Path) -> None:
    mounts = _mounts(tmp_path)
    target = mounts[0].local_root / "My Files" / "Quarterly Report.txt"
    target.parent.mkdir()
    target.write_text("hello")

    assert local_to_remote_path(target, mounts) == "personal:My Files/Quarterly Report.txt"


def test_local_to_remote_path_outside_mount(tmp_path: Path) -> None:
    mounts = _mounts(tmp_path)
    outside = tmp_path / "elsewhere" / "file.txt"
    outside.parent.mkdir()
    outside.write_text("hello")

    with pytest.raises(PathMappingError, match="not under any configured mount root"):
        local_to_remote_path(outside, mounts)


def test_local_to_remote_path_mount_root_itself(tmp_path: Path) -> None:
    mounts = _mounts(tmp_path)

    with pytest.raises(PathMappingError, match="mount root itself"):
        local_to_remote_path(mounts[0].local_root, mounts)


def test_longest_prefix_mount_wins(tmp_path: Path) -> None:
    mounts = _mounts(tmp_path)
    target = mounts[1].local_root / "Projects" / "plan.md"
    target.parent.mkdir()
    target.write_text("hello")

    assert local_to_remote_path(target, mounts) == "work:Projects/plan.md"


def test_find_mount_for_path_returns_longest_match(tmp_path: Path) -> None:
    mounts = _mounts(tmp_path)
    nested_file = mounts[1].local_root / "a" / "b.txt"
    nested_file.parent.mkdir()
    nested_file.write_text("x")

    match = find_mount_for_path(nested_file.resolve(), mounts)
    assert match is not None
    assert match.remote == "work"


def test_remote_path_uses_forward_slashes(tmp_path: Path) -> None:
    mounts = _mounts(tmp_path)
    target = mounts[0].local_root / "a" / "b" / "c.txt"
    target.parent.mkdir(parents=True)
    target.write_text("hello")

    assert local_to_remote_path(target, mounts) == "personal:a/b/c.txt"


def test_resolve_target_folder_remote_path_for_folder(tmp_path: Path) -> None:
    mounts = _mounts(tmp_path)
    folder = mounts[0].local_root / "Projects"
    folder.mkdir()

    assert resolve_target_folder_remote_path(folder, mounts) == "personal:Projects"


def test_resolve_target_folder_remote_path_for_file_uses_parent(tmp_path: Path) -> None:
    mounts = _mounts(tmp_path)
    target = mounts[0].local_root / "Misc" / "File.txt"
    target.parent.mkdir()
    target.write_text("hello")

    assert resolve_target_folder_remote_path(target, mounts) == "personal:Misc"


def test_resolve_target_folder_remote_path_for_mount_root(tmp_path: Path) -> None:
    mounts = _mounts(tmp_path)

    assert resolve_target_folder_remote_path(mounts[0].local_root, mounts) == "personal:"


def test_resolve_target_folder_remote_path_for_file_at_mount_root(tmp_path: Path) -> None:
    mounts = _mounts(tmp_path)
    target = mounts[0].local_root / "File.txt"
    target.write_text("hello")

    assert resolve_target_folder_remote_path(target, mounts) == "personal:"
