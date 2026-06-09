from pathlib import Path

from dolphin_gdrive_actions.config import load_config, set_mount_google_authuser


def test_set_mount_google_authuser(tmp_path: Path) -> None:
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'[[mounts]]\nlocal_root = "{mount_root}"\nremote = "WorkDrive"\n',
        encoding="utf-8",
    )

    set_mount_google_authuser("WorkDrive", "1", config_path)
    config = load_config(config_path)
    assert config.mounts[0].google_authuser == "1"


def test_load_config_parses_google_authuser(tmp_path: Path) -> None:
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        (
            f'[[mounts]]\nlocal_root = "{mount_root}"\nremote = "WorkDrive"\n'
            f'google_authuser = "1"\n'
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    assert config.mounts[0].google_authuser == "1"
