from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dolphin_gdrive_actions.errors import ConfigError


@dataclass(frozen=True)
class MountMapping:
    local_root: Path
    remote: str
    google_authuser: str | None = None


@dataclass(frozen=True)
class AppConfig:
    mounts: tuple[MountMapping, ...]


def default_config_path() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        return Path(config_home) / "dolphin-gdrive-actions" / "config.toml"
    return Path.home() / ".config" / "dolphin-gdrive-actions" / "config.toml"


def read_config_data(config_path: Path | None = None) -> dict[str, object]:
    path = config_path or default_config_path()
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in config file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Config file {path} must contain a TOML table at the top level.")
    return data


def write_config_data(path: Path, data: dict[str, object]) -> None:
    lines: list[str] = []
    mounts = data.get("mounts")
    if isinstance(mounts, list):
        for entry in mounts:
            if not isinstance(entry, dict):
                continue
            local_root = entry.get("local_root")
            remote = entry.get("remote")
            if local_root is None or remote is None:
                continue
            lines.extend(
                [
                    "[[mounts]]",
                    f'local_root = "{_toml_escape(str(local_root))}"',
                    f'remote = "{_toml_escape(str(remote))}"',
                ]
            )
            authuser = entry.get("google_authuser")
            if isinstance(authuser, str) and authuser.strip():
                lines.append(f'google_authuser = "{_toml_escape(authuser.strip())}"')
            lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines).rstrip()
    path.write_text(f"{content}\n" if content else "", encoding="utf-8")


def set_mount_google_authuser(
    remote: str,
    authuser: str,
    config_path: Path | None = None,
) -> None:
    remote_name = _normalize_remote(remote)
    authuser_value = authuser.strip()
    if not authuser_value:
        raise ConfigError("google_authuser must not be empty.")

    path = config_path or default_config_path()
    data = read_config_data(path)
    raw_mounts = data.get("mounts")
    if not isinstance(raw_mounts, list):
        raise ConfigError(f"Config file {path} must define at least one [[mounts]] entry.")

    updated = False
    for entry in raw_mounts:
        if not isinstance(entry, dict):
            continue
        if _normalize_remote(str(entry.get("remote", ""))) == remote_name:
            entry["google_authuser"] = authuser_value
            updated = True
            break

    if not updated:
        raise ConfigError(
            f"No mount configured for remote {remote_name!r}.\n"
            "Run `dga setup` or add a [[mounts]] entry first."
        )

    write_config_data(path, data)


def _normalize_remote(remote: str) -> str:
    remote = remote.strip()
    if not remote:
        raise ConfigError("Mount entry has an empty remote name.")
    return remote.rstrip(":")


def _normalize_local_root(raw_root: str) -> Path:
    expanded = os.path.expanduser(raw_root.strip())
    if not expanded:
        raise ConfigError("Mount entry has an empty local_root.")
    root = Path(expanded).resolve()
    return Path(os.path.normpath(str(root).rstrip("/")))


def _parse_mount(entry: object, index: int) -> MountMapping:
    if not isinstance(entry, dict):
        raise ConfigError(f"Mount entry {index + 1} must be a table.")

    if "local_root" not in entry:
        raise ConfigError(f"Mount entry {index + 1} is missing local_root.")
    if "remote" not in entry:
        raise ConfigError(f"Mount entry {index + 1} is missing remote.")

    local_root = _normalize_local_root(str(entry["local_root"]))
    remote = _normalize_remote(str(entry["remote"]))
    authuser_raw = entry.get("google_authuser")
    google_authuser: str | None = None
    if isinstance(authuser_raw, str) and authuser_raw.strip():
        google_authuser = authuser_raw.strip()

    if not local_root.is_dir():
        raise ConfigError(
            f"Configured mount root does not exist or is not a directory: {local_root}"
        )

    return MountMapping(
        local_root=local_root,
        remote=remote,
        google_authuser=google_authuser,
    )


def load_config(config_path: Path | None = None) -> AppConfig:
    path = config_path or default_config_path()

    if not path.is_file():
        raise ConfigError(
            f"Config file not found: {path}\n"
            "Run `dga setup` or pass --config."
        )

    data = read_config_data(path)

    raw_mounts = data.get("mounts")
    if not raw_mounts:
        raise ConfigError(f"Config file {path} must define at least one [[mounts]] entry.")
    if not isinstance(raw_mounts, list):
        raise ConfigError("Config key 'mounts' must be an array of tables.")

    mounts = tuple(_parse_mount(entry, index) for index, entry in enumerate(raw_mounts))
    _validate_unique_roots(mounts)
    return AppConfig(mounts=mounts)


def _validate_unique_roots(mounts: tuple[MountMapping, ...]) -> None:
    seen: dict[Path, str] = {}
    for mount in mounts:
        if mount.local_root in seen:
            raise ConfigError(
                "Duplicate mount local_root configured: "
                f"{mount.local_root} (remotes {seen[mount.local_root]!r} and {mount.remote!r})."
            )
        seen[mount.local_root] = mount.remote


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
