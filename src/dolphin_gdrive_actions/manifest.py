from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from dolphin_gdrive_actions.errors import SetupError
from dolphin_gdrive_actions.paths_util import manifest_path


@dataclass(frozen=True)
class InstalledFile:
    path: Path
    kind: str
    source: str
    content: str


@dataclass(frozen=True)
class InstallManifest:
    version: int
    dga_path: Path
    installed_at: str
    files: tuple[InstalledFile, ...]


def manifest_exists() -> bool:
    return manifest_path().is_file()


def load_manifest() -> InstallManifest:
    path = manifest_path()
    if not path.is_file():
        raise SetupError(f"Install manifest not found: {path}")

    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise SetupError(f"Invalid install manifest {path}: {exc}") from exc

    version = data.get("version")
    dga_path = data.get("dga_path")
    installed_at = data.get("installed_at")
    raw_files = data.get("files")

    if version != 1:
        raise SetupError(f"Unsupported install manifest version: {version!r}")
    if not dga_path or not installed_at:
        raise SetupError(f"Install manifest {path} is missing required fields.")
    if not isinstance(raw_files, list) or not raw_files:
        raise SetupError(f"Install manifest {path} has no tracked files.")

    files: list[InstalledFile] = []
    for index, entry in enumerate(raw_files):
        if not isinstance(entry, dict):
            raise SetupError(f"Manifest file entry {index + 1} must be a table.")
        for key in ("path", "kind", "source", "content"):
            if key not in entry:
                raise SetupError(f"Manifest file entry {index + 1} is missing {key!r}.")
        files.append(
            InstalledFile(
                path=Path(str(entry["path"])),
                kind=str(entry["kind"]),
                source=str(entry["source"]),
                content=str(entry["content"]).rstrip("\n"),
            )
        )

    return InstallManifest(
        version=1,
        dga_path=Path(str(dga_path)),
        installed_at=str(installed_at),
        files=tuple(files),
    )


def write_manifest(*, dga_path: Path, files: list[InstalledFile]) -> None:
    path = manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "version = 1",
        f'dga_path = "{_toml_escape(str(dga_path))}"',
        f'installed_at = "{datetime.now(UTC).replace(microsecond=0).isoformat()}"',
        "",
    ]
    for installed in files:
        lines.extend(
            [
                "[[files]]",
                f'path = "{_toml_escape(str(installed.path))}"',
                f'kind = "{_toml_escape(installed.kind)}"',
                f'source = "{_toml_escape(installed.source)}"',
                'content = """',
                installed.content,
                '"""',
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
