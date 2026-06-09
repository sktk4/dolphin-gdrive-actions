from __future__ import annotations

import os
from pathlib import Path

from dolphin_gdrive_actions.config import default_config_path


def config_dir() -> Path:
    return default_config_path().parent


def manifest_path() -> Path:
    return config_dir() / "install.toml"


def app_data_dir() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        return Path(data_home) / "dolphin-gdrive-actions"
    return Path.home() / ".local" / "share" / "dolphin-gdrive-actions"


def installed_icons_dir() -> Path:
    return app_data_dir() / "icons"


def servicemenu_dir() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        return Path(data_home) / "kio" / "servicemenus"
    return Path.home() / ".local" / "share" / "kio" / "servicemenus"
