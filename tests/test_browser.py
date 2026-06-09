from unittest.mock import patch

import pytest

from dolphin_gdrive_actions.browser import open_url, open_url_app
from dolphin_gdrive_actions.errors import BrowserError


def test_open_url_prefers_chromium_tab(monkeypatch: pytest.MonkeyPatch) -> None:
    launched: list[list[str]] = []

    def fake_popen(command, **kwargs):
        launched.append(command)
        return type("Process", (), {})()

    monkeypatch.setattr(
        "dolphin_gdrive_actions.browser._default_chromium_binary",
        lambda: "/usr/bin/google-chrome-stable",
    )
    monkeypatch.setattr("dolphin_gdrive_actions.browser.subprocess.Popen", fake_popen)

    open_url("https://drive.google.com/file/d/abc123/view")

    assert launched == [
        [
            "/usr/bin/google-chrome-stable",
            "https://drive.google.com/file/d/abc123/view",
        ]
    ]


def test_open_url_success() -> None:
    with patch("dolphin_gdrive_actions.browser.webbrowser.open", return_value=True) as mock_open:
        with patch("dolphin_gdrive_actions.browser._default_chromium_binary", return_value=None):
            open_url("https://drive.google.com/example")
    mock_open.assert_called_once_with("https://drive.google.com/example")


def test_open_url_failure() -> None:
    with patch("dolphin_gdrive_actions.browser._default_chromium_binary", return_value=None):
        with patch("dolphin_gdrive_actions.browser.webbrowser.open", return_value=False):
            with pytest.raises(BrowserError, match="default browser"):
                open_url("https://drive.google.com/example")


def test_open_url_app_uses_chromium_app(monkeypatch: pytest.MonkeyPatch) -> None:
    launched: list[list[str]] = []

    def fake_popen(command, **kwargs):
        launched.append(command)
        return type("Process", (), {})()

    monkeypatch.setattr(
        "dolphin_gdrive_actions.browser._default_chromium_binary",
        lambda: "/usr/bin/google-chrome-stable",
    )
    monkeypatch.setattr("dolphin_gdrive_actions.browser.subprocess.Popen", fake_popen)

    open_url_app("https://drive.google.com/file/d/abc123/view")

    assert launched == [
        [
            "/usr/bin/google-chrome-stable",
            "--app=https://drive.google.com/file/d/abc123/view",
        ]
    ]


def test_open_url_app_falls_back_to_webbrowser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dolphin_gdrive_actions.browser._default_chromium_binary", lambda: None)
    with patch("dolphin_gdrive_actions.browser.webbrowser.open", return_value=True) as mock_open:
        open_url_app("https://drive.google.com/file/d/abc123/view")
    mock_open.assert_called_once_with("https://drive.google.com/file/d/abc123/view")


def test_is_chromium_binary_detects_browseros() -> None:
    from dolphin_gdrive_actions.browser import _is_chromium_binary

    assert _is_chromium_binary("/usr/bin/browseros", None) is True


def test_is_chromium_binary_detects_startup_wm_class() -> None:
    from dolphin_gdrive_actions.browser import _is_chromium_binary

    assert _is_chromium_binary("/usr/bin/custom-browser", "chromium-browser") is True
