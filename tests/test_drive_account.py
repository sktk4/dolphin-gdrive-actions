import json

import pytest

from dolphin_gdrive_actions.drive_account import (
    get_drive_account_email,
    resolve_drive_remote_name,
)


def test_resolve_drive_remote_name_follows_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "dolphin_gdrive_actions.drive_account._load_rclone_config_dump",
        lambda: {
            "WorkAlias": {"type": "alias", "remote": "WorkDrive,team_drive=abc,root_folder_id=:"},
            "WorkDrive": {"type": "drive", "token": "{}"},
        },
    )
    assert resolve_drive_remote_name("WorkAlias") == "WorkDrive"


def test_get_drive_account_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "dolphin_gdrive_actions.drive_account._load_rclone_config_dump",
        lambda: {
            "WorkDrive": {
                "type": "drive",
                "token": json.dumps({"access_token": "token-123"}),
            }
        },
    )
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/rclone")

    def fake_run(command, **kwargs):
        result = type("Result", (), {})()
        result.returncode = 0
        result.stdout = "[]"
        result.stderr = ""
        return result

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(
                {"user": {"emailAddress": "user@work.example.com"}}
            ).encode("utf-8")

    monkeypatch.setattr("dolphin_gdrive_actions.drive_account.subprocess.run", fake_run)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=15: FakeResponse(),
    )

    get_drive_account_email.cache_clear()
    assert get_drive_account_email("WorkDrive") == "user@work.example.com"
