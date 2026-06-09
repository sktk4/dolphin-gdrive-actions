import json

import pytest

from dolphin_gdrive_actions.errors import RcloneMetadataError
from dolphin_gdrive_actions.rclone import stat_item, stat_item_with_combine_fallback


def test_stat_item_success(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "Path": "Misc/File.txt",
        "Name": "File.txt",
        "ID": "abc123",
        "MimeType": "application/pdf",
        "IsDir": False,
    }

    def fake_run(command, **kwargs):
        assert command == ["/usr/bin/rclone", "lsjson", "--stat", "personal:Misc/File.txt"]
        result = type("Result", (), {})()
        result.returncode = 0
        result.stdout = json.dumps(payload)
        result.stderr = ""
        return result

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/rclone")
    monkeypatch.setattr("dolphin_gdrive_actions.rclone.subprocess.run", fake_run)

    metadata = stat_item("personal:Misc/File.txt")
    assert metadata.item_id == "abc123"
    assert metadata.is_dir is False


def test_stat_item_success_with_list_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [
        {
            "ID": "abc123",
            "MimeType": "application/pdf",
            "IsDir": False,
        }
    ]

    def fake_run(command, **kwargs):
        result = type("Result", (), {})()
        result.returncode = 0
        result.stdout = json.dumps(payload)
        result.stderr = ""
        return result

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/rclone")
    monkeypatch.setattr("dolphin_gdrive_actions.rclone.subprocess.run", fake_run)

    metadata = stat_item("personal:Misc/File.txt")
    assert metadata.item_id == "abc123"


def test_stat_item_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, **kwargs):
        result = type("Result", (), {})()
        result.returncode = 1
        result.stdout = ""
        result.stderr = "item not found"
        return result

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/rclone")
    monkeypatch.setattr("dolphin_gdrive_actions.rclone.subprocess.run", fake_run)

    with pytest.raises(RcloneMetadataError, match="Drive metadata lookup failed"):
        stat_item("personal:missing.txt")


def test_stat_item_with_combine_fallback_retries_upstream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "ID": "abc123",
        "MimeType": "application/pdf",
        "IsDir": False,
    }
    calls: list[str] = []

    def fake_run(command, **kwargs):
        calls.append(command[-1])
        result = type("Result", (), {})()
        if command[-1].startswith("AllDrives:"):
            result.returncode = 1
            result.stdout = ""
            result.stderr = "combine stat failed"
            return result
        result.returncode = 0
        result.stdout = json.dumps(payload)
        result.stderr = ""
        return result

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/rclone")
    monkeypatch.setattr("dolphin_gdrive_actions.rclone.subprocess.run", fake_run)
    monkeypatch.setattr(
        "dolphin_gdrive_actions.rclone.rewrite_if_combine",
        lambda remote_path: "Legal:Working Files/file.pdf"
        if remote_path == "AllDrives:Legal/Working Files/file.pdf"
        else None,
    )

    metadata = stat_item_with_combine_fallback("AllDrives:Legal/Working Files/file.pdf")
    assert metadata.item_id == "abc123"
    assert calls == [
        "AllDrives:Legal/Working Files/file.pdf",
        "Legal:Working Files/file.pdf",
    ]


def test_stat_item_resolves_directory_id_from_parent_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stat_payload = {
        "Path": "",
        "Name": "",
        "MimeType": "inode/directory",
        "IsDir": True,
    }
    list_payload = [
        {
            "Path": "Misc",
            "Name": "Misc",
            "MimeType": "inode/directory",
            "IsDir": True,
            "ID": "folder-id-123",
        }
    ]
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        result = type("Result", (), {})()
        result.returncode = 0
        if command[-1] == "--dirs-only":
            result.stdout = json.dumps(list_payload)
        else:
            result.stdout = json.dumps(stat_payload)
        result.stderr = ""
        return result

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/rclone")
    monkeypatch.setattr("dolphin_gdrive_actions.rclone.subprocess.run", fake_run)

    metadata = stat_item("personal:Misc")
    assert metadata.item_id == "folder-id-123"
    assert metadata.is_dir is True
    assert calls == [
        ["/usr/bin/rclone", "lsjson", "--stat", "personal:Misc"],
        ["/usr/bin/rclone", "lsjson", "personal:", "--dirs-only"],
    ]


def test_stat_item_resolves_shared_drive_root_from_alias_team_drive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stat_payload = {
        "Path": "",
        "Name": "",
        "MimeType": "inode/directory",
        "IsDir": True,
    }
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        result = type("Result", (), {})()
        result.returncode = 0
        result.stdout = json.dumps(stat_payload)
        result.stderr = ""
        return result

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/rclone")
    monkeypatch.setattr("dolphin_gdrive_actions.rclone.subprocess.run", fake_run)
    monkeypatch.setattr(
        "dolphin_gdrive_actions.rclone._load_rclone_config_dump",
        lambda: {
            "WorkAlias": {
                "type": "alias",
                "remote": "WorkDrive,team_drive=shared-drive-id,root_folder_id=:",
            },
            "WorkDrive": {"type": "drive", "token": "{}"},
        },
    )

    metadata = stat_item("WorkAlias:")
    assert metadata.item_id == "shared-drive-id"
    assert metadata.is_dir is True
    assert calls == [["/usr/bin/rclone", "lsjson", "--stat", "WorkAlias:"]]


def test_stat_item_resolves_shared_drive_root_from_top_level_team_drive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stat_payload = {
        "Path": "",
        "Name": "",
        "MimeType": "inode/directory",
        "IsDir": True,
    }

    def fake_run(command, **kwargs):
        result = type("Result", (), {})()
        result.returncode = 0
        result.stdout = json.dumps(stat_payload)
        result.stderr = ""
        return result

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/rclone")
    monkeypatch.setattr("dolphin_gdrive_actions.rclone.subprocess.run", fake_run)
    monkeypatch.setattr(
        "dolphin_gdrive_actions.rclone._load_rclone_config_dump",
        lambda: {
            "WorkDrive": {"type": "drive", "team_drive": "top-level-team-drive-id"},
        },
    )

    metadata = stat_item("WorkDrive:")
    assert metadata.item_id == "top-level-team-drive-id"
