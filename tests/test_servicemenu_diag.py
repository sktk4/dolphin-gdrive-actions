from pathlib import Path

from dolphin_gdrive_actions.servicemenu_diag import diagnose_servicemenu


def test_diagnose_servicemenu_detects_separator_section(tmp_path: Path) -> None:
    menu = tmp_path / "gd-01-block.desktop"
    menu.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Actions=_SEPARATOR_;01openWithGoogleDrive;",
                "",
                "[Desktop Action _SEPARATOR_]",
                "Name=-",
                "",
                "[Desktop Action 01openWithGoogleDrive]",
                "Name=Open with Google Drive",
            ]
        ),
        encoding="utf-8",
    )

    diagnosis = diagnose_servicemenu(menu)
    assert diagnosis["action_keys"] == ["_SEPARATOR_", "01openWithGoogleDrive"]
    assert diagnosis["separator_tokens"] == 1
    assert diagnosis["has_separator_section"] is True
    assert diagnosis["separator_ready"] is True


def test_diagnose_servicemenu_flags_missing_separator_section(tmp_path: Path) -> None:
    menu = tmp_path / "google-drive.desktop"
    menu.write_text(
        "[Desktop Entry]\nActions=openWithGoogleDrive;_SEPARATOR_;share;\n",
        encoding="utf-8",
    )

    diagnosis = diagnose_servicemenu(menu)
    assert diagnosis["separator_tokens"] == 1
    assert diagnosis["has_separator_section"] is False
    assert diagnosis["separator_ready"] is False
