from __future__ import annotations

from urllib.parse import quote

from dataclasses import dataclass


@dataclass(frozen=True)
class DriveItemMetadata:
    item_id: str
    mime_type: str
    is_dir: bool


def split_remote_path(remote_path: str) -> tuple[str, str]:
    """Split ``remote:path`` into remote name and relative path."""
    if ":" not in remote_path:
        raise ValueError(f"Invalid remote path (missing ':'): {remote_path}")
    remote, _, relative = remote_path.partition(":")
    if not remote:
        raise ValueError(f"Invalid remote path (empty remote): {remote_path}")
    return remote, relative


def parse_lsjson_stat(payload: dict[str, object] | list[dict[str, object]]) -> DriveItemMetadata:
    """Parse a ``rclone lsjson --stat`` response (single object or one-element list)."""
    if isinstance(payload, dict):
        item = payload
    elif isinstance(payload, list):
        if not payload:
            raise ValueError("rclone lsjson --stat returned no items.")
        if len(payload) != 1:
            raise ValueError(f"rclone lsjson --stat returned {len(payload)} items; expected 1.")
        item = payload[0]
    else:
        raise ValueError("rclone lsjson --stat returned unexpected JSON structure.")
    item_id = item.get("ID")
    mime_type = item.get("MimeType")
    is_dir = item.get("IsDir")

    if not isinstance(mime_type, str):
        raise ValueError("rclone lsjson --stat response is missing MimeType.")
    if not isinstance(is_dir, bool):
        raise ValueError("rclone lsjson --stat response is missing IsDir.")

    if isinstance(item_id, str) and item_id:
        resolved_id = item_id
    elif is_dir:
        # Google Drive directories omit ID in lsjson --stat; resolved later.
        resolved_id = ""
    else:
        raise ValueError("rclone lsjson --stat response is missing a valid ID.")

    return DriveItemMetadata(item_id=resolved_id, mime_type=mime_type, is_dir=is_dir)


def build_drive_url(item_id: str, *, is_dir: bool) -> str:
    """Build a Google Drive web URL for a file or folder ID."""
    if is_dir:
        return build_drive_folder_url(item_id)
    return f"https://drive.google.com/file/d/{item_id}/view"


def build_drive_folder_url(folder_id: str, *, authuser: str | None = None) -> str:
    """Build a Google Drive folder URL, optionally scoped to a browser account."""
    if authuser is not None and authuser.isdigit():
        return f"https://drive.google.com/drive/u/{authuser}/folders/{folder_id}"
    url = f"https://drive.google.com/drive/folders/{folder_id}"
    if authuser:
        url += f"?authuser={quote(authuser, safe='@.')}"
    return url


def build_my_drive_url(*, authuser: str | None = None) -> str:
    """Build a Google Drive My Drive URL, optionally scoped to a browser account."""
    if authuser is not None and authuser.isdigit():
        return f"https://drive.google.com/drive/u/{authuser}/my-drive"
    url = "https://drive.google.com/drive/my-drive"
    if authuser:
        url += f"?authuser={quote(authuser, safe='@.')}"
    return url


def build_drive_share_url(item_id: str, *, is_dir: bool) -> str:
    """Build a Google Drive URL for sharing a file or folder ID.

    Google's internal ``/sharing/share`` endpoint returns 404 when opened
    directly in a browser. Open the item in Drive instead; use the Share
    button in the Drive toolbar.
    """
    if is_dir:
        return f"https://drive.google.com/drive/folders/{item_id}"
    return f"https://drive.google.com/open?id={item_id}"


def is_google_workspace_file(mime_type: str) -> bool:
    return mime_type.startswith("application/vnd.google-apps.")


_WORKSPACE_CREATE_PATH: dict[str, str] = {
    "doc": "document",
    "sheet": "spreadsheets",
    "slide": "presentation",
    "drawing": "drawings",
}


def build_workspace_create_url(
    file_type: str,
    folder_id: str | None,
    *,
    authuser: str | None = None,
) -> str:
    """Build a browser URL that opens a blank Google Workspace editor in a folder."""
    try:
        segment = _WORKSPACE_CREATE_PATH[file_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported workspace file type: {file_type}") from exc

    if authuser is not None and authuser.isdigit():
        base = f"https://docs.google.com/{segment}/u/{authuser}/create"
    else:
        base = f"https://docs.google.com/{segment}/create"

    params = ["usp=drive_web"]
    if folder_id:
        params.append(f"folder={folder_id}")
    if authuser and not authuser.isdigit():
        params.append(f"authuser={quote(authuser, safe='@.')}")
    return f"{base}?{'&'.join(params)}"
