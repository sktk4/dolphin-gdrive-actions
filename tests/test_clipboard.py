from __future__ import annotations

import subprocess

import pytest

from dolphin_gdrive_actions import clipboard


def test_try_kde_klipper_prefers_qdbus6(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        if name in {"qdbus6", "qdbus"}:
            return f"/usr/bin/{name}"
        return None

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(clipboard.shutil, "which", fake_which)
    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)

    assert clipboard._try_kde_klipper("https://example.com") is True
    assert len(calls) == 1
    assert calls[0][0] == "qdbus6"


def test_try_kde_klipper_falls_back_to_qdbus(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        if name == "qdbus":
            return "/usr/bin/qdbus"
        return None

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[0] == "qdbus":
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 1, "", "")

    monkeypatch.setattr(clipboard.shutil, "which", fake_which)
    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)

    assert clipboard._try_kde_klipper("https://example.com") is True
    assert len(calls) == 1
    assert calls[0][0] == "qdbus"


def test_copy_text_to_clipboard_skips_qdbus_when_qdbus6_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        if name in {"qdbus6", "qdbus", "wl-copy", "xclip"}:
            return f"/usr/bin/{name}"
        return None

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[0] == "qdbus6":
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 1, "", "")

    monkeypatch.setattr(clipboard.shutil, "which", fake_which)
    monkeypatch.setattr(clipboard.subprocess, "run", fake_run)

    assert clipboard.copy_text_to_clipboard("https://example.com") is True
    assert len(calls) == 1
    assert calls[0][0] == "qdbus6"
