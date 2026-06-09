import pytest

from dolphin_gdrive_actions.drive_metadata import (
    build_drive_folder_url,
    build_drive_share_url,
    build_drive_url,
    build_my_drive_url,
    build_workspace_create_url,
    is_google_workspace_file,
    parse_lsjson_stat,
    split_remote_path,
)


def test_split_remote_path() -> None:
    assert split_remote_path("personal:Misc/File.txt") == ("personal", "Misc/File.txt")


def test_split_remote_path_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="missing ':'"):
        split_remote_path("invalid")


def test_parse_lsjson_stat_file() -> None:
    payload = [
        {
            "ID": "abc123",
            "MimeType": "application/pdf",
            "IsDir": False,
        }
    ]
    metadata = parse_lsjson_stat(payload)
    assert metadata.item_id == "abc123"
    assert metadata.mime_type == "application/pdf"
    assert metadata.is_dir is False


def test_parse_lsjson_stat_folder() -> None:
    payload = [
        {
            "ID": "folder-id",
            "MimeType": "inode/directory",
            "IsDir": True,
        }
    ]
    metadata = parse_lsjson_stat(payload)
    assert metadata.is_dir is True


def test_parse_lsjson_stat_rejects_empty() -> None:
    with pytest.raises(ValueError, match="no items"):
        parse_lsjson_stat([])


def test_parse_lsjson_stat_single_object() -> None:
    payload = {
        "Path": "Misc/File.txt",
        "Name": "File.txt",
        "ID": "abc123",
        "MimeType": "application/pdf",
        "IsDir": False,
    }
    metadata = parse_lsjson_stat(payload)
    assert metadata.item_id == "abc123"
    assert metadata.mime_type == "application/pdf"
    assert metadata.is_dir is False


def test_build_drive_url_file() -> None:
    assert build_drive_url("abc123", is_dir=False) == (
        "https://drive.google.com/file/d/abc123/view"
    )


def test_build_drive_url_folder() -> None:
    assert build_drive_url("folder-id", is_dir=True) == (
        "https://drive.google.com/drive/folders/folder-id"
    )


def test_build_drive_share_url_file() -> None:
    assert build_drive_share_url("abc123", is_dir=False) == (
        "https://drive.google.com/open?id=abc123"
    )


def test_build_drive_share_url_folder() -> None:
    assert build_drive_share_url("folder-id", is_dir=True) == (
        "https://drive.google.com/drive/folders/folder-id"
    )


def test_is_google_workspace_file() -> None:
    assert is_google_workspace_file("application/vnd.google-apps.document") is True
    assert is_google_workspace_file("application/pdf") is False


@pytest.mark.parametrize(
    ("file_type", "expected_base"),
    [
        ("doc", "https://docs.google.com/document/create"),
        ("sheet", "https://docs.google.com/spreadsheets/create"),
        ("slide", "https://docs.google.com/presentation/create"),
        ("drawing", "https://docs.google.com/drawings/create"),
    ],
)
def test_build_workspace_create_url(file_type: str, expected_base: str) -> None:
    url = build_workspace_create_url(file_type, "folder-id")
    assert url == f"{expected_base}?usp=drive_web&folder=folder-id"


def test_build_workspace_create_url_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="Unsupported workspace file type"):
        build_workspace_create_url("form", "folder-id")


def test_build_workspace_create_url_omits_folder_for_drive_root() -> None:
    url = build_workspace_create_url("doc", None)
    assert url == "https://docs.google.com/document/create?usp=drive_web"
    assert "folder=" not in url


def test_build_workspace_create_url_includes_authuser_index_in_path() -> None:
    url = build_workspace_create_url("doc", "folder-id", authuser="1")
    assert url == (
        "https://docs.google.com/document/u/1/create?"
        "usp=drive_web&folder=folder-id"
    )


def test_build_workspace_create_url_includes_authuser_email() -> None:
    url = build_workspace_create_url(
        "doc",
        "folder-id",
        authuser="user@work.example.com",
    )
    assert url == (
        "https://docs.google.com/document/create?"
        "usp=drive_web&folder=folder-id&authuser=user@work.example.com"
    )


def test_build_workspace_create_url_root_with_authuser_index() -> None:
    url = build_workspace_create_url("doc", None, authuser="1")
    assert url == "https://docs.google.com/document/u/1/create?usp=drive_web"


def test_build_drive_folder_url_includes_authuser_index_in_path() -> None:
    url = build_drive_folder_url("folder-id", authuser="1")
    assert url == "https://drive.google.com/drive/u/1/folders/folder-id"


def test_build_drive_folder_url_includes_authuser_email() -> None:
    url = build_drive_folder_url("folder-id", authuser="user@work.example.com")
    assert url == (
        "https://drive.google.com/drive/folders/folder-id?"
        "authuser=user@work.example.com"
    )


def test_build_my_drive_url_includes_authuser_index_in_path() -> None:
    url = build_my_drive_url(authuser="1")
    assert url == "https://drive.google.com/drive/u/1/my-drive"


def test_build_my_drive_url_includes_authuser_email() -> None:
    url = build_my_drive_url(authuser="user@personal.example.com")
    assert url == (
        "https://drive.google.com/drive/my-drive?authuser=user@personal.example.com"
    )
