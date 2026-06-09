from pathlib import Path

import pytest

from dolphin_gdrive_actions.commands import cmd_new
from dolphin_gdrive_actions.drive_metadata import DriveItemMetadata


class Args:
    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


def _write_config(config_path: Path, mount_root: Path, *, remote: str = "personal") -> None:
    config_path.write_text(
        f'[[mounts]]\nlocal_root = "{mount_root}"\nremote = "{remote}"\n',
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("file_type", "expected_base"),
    [
        ("doc", "https://docs.google.com/document/create"),
        ("sheet", "https://docs.google.com/spreadsheets/create"),
        ("slide", "https://docs.google.com/presentation/create"),
        ("drawing", "https://docs.google.com/drawings/create"),
    ],
)
def test_cmd_new_opens_workspace_create_url_for_folder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    file_type: str,
    expected_base: str,
) -> None:
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    folder = mount_root / "Projects"
    folder.mkdir()

    config_path = tmp_path / "config.toml"
    _write_config(config_path, mount_root)

    looked_up: list[str] = []
    opened: list[str] = []

    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.get_drive_account_email",
        lambda _remote: None,
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands._lookup_drive_metadata",
        lambda remote_path: looked_up.append(remote_path)
        or DriveItemMetadata(
            item_id="folder-id",
            mime_type="inode/directory",
            is_dir=True,
        ),
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.open_url",
        lambda url: opened.append(url),
    )

    args = Args(type=file_type, local_path=str(folder), config=str(config_path))
    assert cmd_new(args) == 0
    assert looked_up == ["personal:Projects"]
    assert opened == [f"{expected_base}?usp=drive_web&folder=folder-id"]


def test_cmd_new_uses_auto_detected_account_email(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    folder = mount_root / "Projects"
    folder.mkdir()

    config_path = tmp_path / "config.toml"
    _write_config(config_path, mount_root, remote="WorkDrive")

    opened: list[str] = []
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.get_drive_account_email",
        lambda _remote: "user@work.example.com",
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands._lookup_drive_metadata",
        lambda _remote_path: DriveItemMetadata(
            item_id="folder-id",
            mime_type="inode/directory",
            is_dir=True,
        ),
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.open_url",
        lambda url: opened.append(url),
    )

    args = Args(type="doc", local_path=str(folder), config=str(config_path))
    assert cmd_new(args) == 0
    assert opened == [
        "https://docs.google.com/document/create?"
        "usp=drive_web&folder=folder-id&authuser=user@work.example.com"
    ]


def test_cmd_new_prefers_configured_authuser_index(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    folder = mount_root / "Projects"
    folder.mkdir()

    config_path = tmp_path / "config.toml"
    config_path.write_text(
        (
            f'[[mounts]]\nlocal_root = "{mount_root}"\nremote = "WorkDrive"\n'
            f'google_authuser = "1"\n'
        ),
        encoding="utf-8",
    )

    opened: list[str] = []
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.get_drive_account_email",
        lambda _remote: "user@work.example.com",
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands._lookup_drive_metadata",
        lambda _remote_path: DriveItemMetadata(
            item_id="folder-id",
            mime_type="inode/directory",
            is_dir=True,
        ),
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.open_url",
        lambda url: opened.append(url),
    )

    args = Args(type="doc", local_path=str(folder), config=str(config_path))
    assert cmd_new(args) == 0
    assert opened == [
        "https://docs.google.com/document/u/1/create?"
        "usp=drive_web&folder=folder-id"
    ]


def test_cmd_new_resolves_authuser_via_combine_upstream(
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
        "dolphin_gdrive_actions.commands.open_url",
        lambda url: opened.append(url),
    )

    args = Args(type="doc", local_path=str(folder), config=str(config_path))
    assert cmd_new(args) == 0
    assert looked_up == ["AllDrives:WorkAlias/Tools"]
    assert email_calls == ["WorkAlias"]
    assert opened == [
        "https://docs.google.com/document/create?"
        "usp=drive_web&folder=shared-folder-id&authuser=user@work.example.com"
    ]


def test_cmd_new_uses_parent_folder_for_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    target = mount_root / "Misc" / "File.txt"
    target.parent.mkdir()
    target.write_text("hello", encoding="utf-8")

    config_path = tmp_path / "config.toml"
    _write_config(config_path, mount_root)

    looked_up: list[str] = []
    opened: list[str] = []

    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.get_drive_account_email",
        lambda _remote: None,
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands._lookup_drive_metadata",
        lambda remote_path: looked_up.append(remote_path)
        or DriveItemMetadata(
            item_id="parent-folder-id",
            mime_type="inode/directory",
            is_dir=True,
        ),
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.open_url",
        lambda url: opened.append(url),
    )

    args = Args(type="doc", local_path=str(target), config=str(config_path))
    assert cmd_new(args) == 0
    assert looked_up == ["personal:Misc"]
    assert opened == [
        "https://docs.google.com/document/create?usp=drive_web&folder=parent-folder-id"
    ]


def test_cmd_new_uses_mount_root_for_file_at_mount_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    target = mount_root / "File.txt"
    target.write_text("hello", encoding="utf-8")

    config_path = tmp_path / "config.toml"
    _write_config(config_path, mount_root)

    looked_up: list[str] = []

    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands.get_drive_account_email",
        lambda _remote: None,
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.commands._lookup_drive_metadata",
        lambda remote_path: looked_up.append(remote_path)
        or DriveItemMetadata(
            item_id="root-folder-id",
            mime_type="inode/directory",
            is_dir=True,
        ),
    )
    monkeypatch.setattr("dolphin_gdrive_actions.commands.open_url", lambda _url: None)

    args = Args(type="sheet", local_path=str(target), config=str(config_path))
    assert cmd_new(args) == 0
    assert looked_up == ["personal:"]
