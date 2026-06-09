from pathlib import Path

import pytest

from dolphin_gdrive_actions.commands import cmd_offline, cmd_open_folder
from dolphin_gdrive_actions.drive_metadata import DriveItemMetadata


class Args:
    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


def _patch_open_folder_account(
    monkeypatch: pytest.MonkeyPatch,
    *,
    email: str | None = None,
    rewrite: object | None = None,
) -> None:
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.get_drive_account_email",
        lambda _remote: email,
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.rewrite_if_combine",
        rewrite if rewrite is not None else (lambda _remote_path: None),
    )


def test_cmd_open_folder_opens_parent_folder_for_file(
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

    looked_up: list[str] = []
    opened: list[str] = []

    def fake_lookup(remote_path: str) -> DriveItemMetadata:
        looked_up.append(remote_path)
        return DriveItemMetadata(
            item_id="parent-folder-id",
            mime_type="inode/directory",
            is_dir=True,
        )

    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands._lookup_drive_metadata",
        fake_lookup,
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.open_url_app",
        lambda url: opened.append(url),
    )
    _patch_open_folder_account(monkeypatch)

    args = Args(local_path=str(target), config=str(config_path))
    assert cmd_open_folder(args) == 0
    assert looked_up == ["personal:Misc"]
    assert opened == ["https://drive.google.com/drive/folders/parent-folder-id"]


def test_cmd_open_folder_opens_folder_for_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mount_root = tmp_path / "mount"
    folder = mount_root / "Misc"
    folder.mkdir(parents=True)

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'[[mounts]]\nlocal_root = "{mount_root}"\nremote = "personal"\n',
        encoding="utf-8",
    )

    looked_up: list[str] = []
    opened: list[str] = []

    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands._lookup_drive_metadata",
        lambda remote_path: looked_up.append(remote_path)
        or DriveItemMetadata(
            item_id="misc-folder-id",
            mime_type="inode/directory",
            is_dir=True,
        ),
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.open_url_app",
        lambda url: opened.append(url),
    )
    _patch_open_folder_account(monkeypatch)

    args = Args(local_path=str(folder), config=str(config_path))
    assert cmd_open_folder(args) == 0
    assert looked_up == ["personal:Misc"]
    assert opened == ["https://drive.google.com/drive/folders/misc-folder-id"]


def test_cmd_open_folder_uses_my_drive_fallback_for_empty_folder_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    target = mount_root / "File.txt"
    target.write_text("hello", encoding="utf-8")

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'[[mounts]]\nlocal_root = "{mount_root}"\nremote = "personal"\n',
        encoding="utf-8",
    )

    opened: list[str] = []
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands._lookup_drive_metadata",
        lambda _remote_path: DriveItemMetadata(
            item_id="",
            mime_type="inode/directory",
            is_dir=True,
        ),
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.open_url_app",
        lambda url: opened.append(url),
    )
    _patch_open_folder_account(monkeypatch, email="user@personal.example.com")

    args = Args(local_path=str(target), config=str(config_path))
    assert cmd_open_folder(args) == 0
    assert opened == [
        "https://drive.google.com/drive/my-drive?authuser=user@personal.example.com"
    ]


def test_cmd_open_folder_prefers_configured_authuser_index(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    target = mount_root / "File.txt"
    target.write_text("hello", encoding="utf-8")

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        (
            f'[[mounts]]\nlocal_root = "{mount_root}"\nremote = "personal"\n'
            f'google_authuser = "1"\n'
        ),
        encoding="utf-8",
    )

    opened: list[str] = []
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands._lookup_drive_metadata",
        lambda _remote_path: DriveItemMetadata(
            item_id="folder-id",
            mime_type="inode/directory",
            is_dir=True,
        ),
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.open_url_app",
        lambda url: opened.append(url),
    )
    _patch_open_folder_account(monkeypatch, email="should-not-be-used@example.com")

    args = Args(local_path=str(target), config=str(config_path))
    assert cmd_open_folder(args) == 0
    assert opened == ["https://drive.google.com/drive/u/1/folders/folder-id"]


def test_cmd_open_folder_resolves_authuser_via_combine_upstream(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mount_root = tmp_path / "shared"
    folder = mount_root / "WorkAlias" / "Tools"
    folder.mkdir(parents=True)

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'[[mounts]]\nlocal_root = "{mount_root}"\nremote = "AllDrives"\n',
        encoding="utf-8",
    )

    looked_up: list[str] = []
    email_calls: list[str] = []
    opened: list[str] = []

    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.rewrite_if_combine",
        lambda remote_path: "WorkAlias:Tools"
        if remote_path == "AllDrives:WorkAlias/Tools"
        else None,
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.get_drive_account_email",
        lambda remote: email_calls.append(remote) or "user@work.example.com",
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands._lookup_drive_metadata",
        lambda remote_path: looked_up.append(remote_path)
        or DriveItemMetadata(
            item_id="shared-folder-id",
            mime_type="inode/directory",
            is_dir=True,
        ),
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.open_url_app",
        lambda url: opened.append(url),
    )

    args = Args(local_path=str(folder), config=str(config_path))
    assert cmd_open_folder(args) == 0
    assert looked_up == ["AllDrives:WorkAlias/Tools"]
    assert email_calls == ["WorkAlias"]
    assert opened == [
        "https://drive.google.com/drive/folders/shared-folder-id?"
        "authuser=user@work.example.com"
    ]


def test_cmd_open_folder_opens_shared_drive_root_with_authuser(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    target = mount_root / "File.txt"
    target.write_text("hello", encoding="utf-8")

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'[[mounts]]\nlocal_root = "{mount_root}"\nremote = "WorkAlias"\n',
        encoding="utf-8",
    )

    opened: list[str] = []
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands._lookup_drive_metadata",
        lambda remote_path: DriveItemMetadata(
            item_id="shared-drive-id",
            mime_type="inode/directory",
            is_dir=True,
        )
        if remote_path == "WorkAlias:"
        else DriveItemMetadata(
            item_id="",
            mime_type="inode/directory",
            is_dir=True,
        ),
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.open_url_app",
        lambda url: opened.append(url),
    )
    _patch_open_folder_account(monkeypatch, email="user@work.example.com")

    args = Args(local_path=str(target), config=str(config_path))
    assert cmd_open_folder(args) == 0
    assert opened == [
        "https://drive.google.com/drive/folders/shared-drive-id?"
        "authuser=user@work.example.com"
    ]


def test_cmd_open_folder_reports_path_mapping_error(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")

    config_path = tmp_path / "config.toml"
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    config_path.write_text(
        f'[[mounts]]\nlocal_root = "{mount_root}"\nremote = "personal"\n',
        encoding="utf-8",
    )

    args = Args(local_path=str(outside), config=str(config_path))
    assert cmd_open_folder(args) == 2


def test_cmd_offline_warms_cache_for_regular_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    target = mount_root / "Misc" / "File.txt"
    target.parent.mkdir()
    target.write_text("hello world", encoding="utf-8")

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
        "dolphin_gdrive_actions.commands.notify_success",
        lambda title, message: notified.append((title, message)),
    )
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)

    args = Args(local_path=str(target), config=str(config_path))
    assert cmd_offline(args) == 0
    assert notified
    assert notified[0][0] == "Available offline"


def test_cmd_offline_opens_browser_for_workspace_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    target = mount_root / "Doc.gdoc"
    target.write_text("placeholder", encoding="utf-8")

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'[[mounts]]\nlocal_root = "{mount_root}"\nremote = "personal"\n',
        encoding="utf-8",
    )

    opened: list[str] = []
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands._lookup_drive_metadata",
        lambda _remote_path: DriveItemMetadata(
            item_id="doc-id",
            mime_type="application/vnd.google-apps.document",
            is_dir=False,
        ),
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.open_url",
        lambda url: opened.append(url),
    )
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)

    args = Args(local_path=str(target), config=str(config_path))
    assert cmd_offline(args) == 0
    assert opened == ["https://drive.google.com/file/d/doc-id/view"]
