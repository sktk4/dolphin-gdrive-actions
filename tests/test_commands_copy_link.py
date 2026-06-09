from __future__ import annotations

from pathlib import Path

import pytest

from dolphin_gdrive_actions.commands import cmd_copy_link
from dolphin_gdrive_actions.drive_metadata import DriveItemMetadata


class Args:
    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


def test_cmd_copy_link_notifies_on_clipboard_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    target = mount_root / "Misc" / "File.txt"
    target.parent.mkdir()
    target.write_text("hello", encoding="utf-8")

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'[[mounts]]\nlocal_root = "{mount_root}"\nremote = "personal"\n',
        encoding="utf-8",
    )

    notified: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands._lookup_drive_metadata",
        lambda _remote_path: DriveItemMetadata(
            item_id="abc123",
            mime_type="application/pdf",
            is_dir=False,
        ),
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.copy_text_to_clipboard",
        lambda _url: False,
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.notify_error",
        lambda title, message: notified.append((title, message)),
    )
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    monkeypatch.setattr("sys.stderr.isatty", lambda: False)

    args = Args(local_path=str(target), config=str(config_path), clipboard=True)
    assert cmd_copy_link(args) == 0
    assert len(notified) == 1
    assert notified[0][0] == "Copy Google Drive link failed"
    assert "could not be copied to the clipboard" in notified[0][1]


def test_cmd_copy_link_prints_stderr_warning_on_clipboard_failure_tty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    target = mount_root / "Misc" / "File.txt"
    target.parent.mkdir()
    target.write_text("hello", encoding="utf-8")

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'[[mounts]]\nlocal_root = "{mount_root}"\nremote = "personal"\n',
        encoding="utf-8",
    )

    notified: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands._lookup_drive_metadata",
        lambda _remote_path: DriveItemMetadata(
            item_id="abc123",
            mime_type="application/pdf",
            is_dir=False,
        ),
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.copy_text_to_clipboard",
        lambda _url: False,
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.notify_error",
        lambda title, message: notified.append((title, message)),
    )
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)

    args = Args(local_path=str(target), config=str(config_path), clipboard=True)
    assert cmd_copy_link(args) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "https://drive.google.com/open?id=abc123"
    assert "Could not copy link to clipboard." in captured.err
    assert notified == []
