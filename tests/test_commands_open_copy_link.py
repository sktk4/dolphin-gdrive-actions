from __future__ import annotations

from pathlib import Path

import pytest

from dolphin_gdrive_actions.commands import cmd_copy_link, cmd_open
from dolphin_gdrive_actions.drive_metadata import DriveItemMetadata


class Args:
    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


def _sample_metadata() -> DriveItemMetadata:
    return DriveItemMetadata(
        item_id="abc123",
        mime_type="application/pdf",
        is_dir=False,
    )


def _write_config(tmp_path: Path, mount_root: Path) -> Path:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'[[mounts]]\nlocal_root = "{mount_root}"\nremote = "personal"\n',
        encoding="utf-8",
    )
    return config_path


def test_cmd_copy_link_uses_share_style_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    target = mount_root / "Misc" / "File.txt"
    target.parent.mkdir()
    target.write_text("hello", encoding="utf-8")
    config_path = _write_config(tmp_path, mount_root)

    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands._lookup_drive_metadata",
        lambda _remote_path: _sample_metadata(),
    )

    args = Args(local_path=str(target), config=str(config_path), clipboard=False)
    assert cmd_copy_link(args) == 0
    assert capsys.readouterr().out.strip() == "https://drive.google.com/open?id=abc123"


def test_cmd_open_uses_view_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    target = mount_root / "Misc" / "File.txt"
    target.parent.mkdir()
    target.write_text("hello", encoding="utf-8")
    config_path = _write_config(tmp_path, mount_root)

    opened: list[str] = []
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands._lookup_drive_metadata",
        lambda _remote_path: _sample_metadata(),
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.open_url_app",
        lambda url: opened.append(url),
    )
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)

    args = Args(local_path=str(target), config=str(config_path))
    assert cmd_open(args) == 0
    assert opened == ["https://drive.google.com/file/d/abc123/view"]


def test_open_and_copy_link_do_not_call_rclone_link(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import dolphin_gdrive_actions.rclone as rclone_module

    assert not hasattr(rclone_module, "create_link")

    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    target = mount_root / "Misc" / "File.txt"
    target.parent.mkdir()
    target.write_text("hello", encoding="utf-8")
    config_path = _write_config(tmp_path, mount_root)

    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands._lookup_drive_metadata",
        lambda _remote_path: _sample_metadata(),
    )
    monkeypatch.setattr("dolphin_gdrive_actions.commands.open_url_app", lambda _url: None)
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.copy_text_to_clipboard",
        lambda _url: True,
    )
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)

    open_args = Args(local_path=str(target), config=str(config_path))
    copy_args = Args(local_path=str(target), config=str(config_path), clipboard=True)
    assert cmd_open(open_args) == 0
    assert cmd_copy_link(copy_args) == 0
