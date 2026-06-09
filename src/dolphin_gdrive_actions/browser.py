from __future__ import annotations

import shutil
import subprocess
import webbrowser
from pathlib import Path

from dolphin_gdrive_actions.errors import BrowserError

_CHROMIUM_BINARIES = frozenset(
    {
        "browseros",
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "brave-browser",
        "microsoft-edge",
        "microsoft-edge-stable",
    }
)

_DESKTOP_FIELD_CODES = ("%U", "%u", "%F", "%f", "%i", "%c", "%k")


def open_url(url: str) -> None:
    """Open a URL in the default browser, reusing an existing Chromium window when possible."""
    binary = _default_chromium_binary()
    if binary and _launch_chromium_url(binary, url):
        return

    try:
        opened = webbrowser.open(url)
    except OSError as exc:
        raise BrowserError(f"Failed to open the default browser: {exc}") from exc

    if not opened:
        raise BrowserError(
            "Failed to open the default browser.\n"
            "Check that a web browser is configured as the system default."
        )


def open_url_app(url: str) -> None:
    """Open a URL in a standalone Chromium app window when possible."""
    binary = _default_chromium_binary()
    if binary and _launch_chromium_app(binary, url):
        return
    open_url(url)


def _default_chromium_binary() -> str | None:
    desktop = _default_browser_desktop()
    if not desktop:
        return None

    exec_line, startup_wm_class = _read_desktop_entry(desktop)
    if not exec_line:
        return None

    binary = _resolve_binary(exec_line)
    if binary and _is_chromium_binary(binary, startup_wm_class):
        return binary
    return None


def _default_browser_desktop() -> str | None:
    try:
        result = subprocess.run(
            ["xdg-settings", "get", "default-web-browser"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None

    if result.returncode != 0:
        return None

    desktop = result.stdout.strip()
    return desktop or None


def _desktop_search_paths() -> list[Path]:
    paths = [
        Path("/usr/share/applications"),
        Path.home() / ".local/share/applications",
    ]
    return [path for path in paths if path.is_dir()]


def _read_desktop_entry(desktop_file: str) -> tuple[str | None, str | None]:
    name = desktop_file if desktop_file.endswith(".desktop") else f"{desktop_file}.desktop"
    exec_line: str | None = None
    startup_wm_class: str | None = None
    for base in _desktop_search_paths():
        path = base / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("Exec=") and exec_line is None:
                exec_line = line[5:].strip()
            elif line.startswith("StartupWMClass=") and startup_wm_class is None:
                startup_wm_class = line[len("StartupWMClass=") :].strip()
        if exec_line is not None:
            return exec_line, startup_wm_class
    return None, None


def _resolve_binary(exec_line: str) -> str | None:
    cleaned = exec_line
    for code in _DESKTOP_FIELD_CODES:
        cleaned = cleaned.replace(code, "")
    cleaned = cleaned.strip()
    if not cleaned:
        return None

    binary = cleaned.split()[0]
    path = Path(binary)
    if path.is_absolute() and path.is_file():
        return str(path)

    return shutil.which(binary)


def _is_chromium_binary(binary: str, startup_wm_class: str | None) -> bool:
    if Path(binary).name in _CHROMIUM_BINARIES:
        return True
    if startup_wm_class and "chromium" in startup_wm_class.lower():
        return True
    return False


def _launch_chromium_url(binary: str, url: str) -> bool:
    """Open a URL in Chromium without ``--app`` (new tab in existing window when running)."""
    try:
        subprocess.Popen(
            [binary, url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False
    return True


def _launch_chromium_app(binary: str, url: str) -> bool:
    try:
        subprocess.Popen(
            [binary, f"--app={url}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False
    return True
