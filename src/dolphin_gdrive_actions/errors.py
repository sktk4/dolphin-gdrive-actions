"""Application errors with stable exit codes."""

from __future__ import annotations


class DgaError(Exception):
    """Base error with a stable CLI exit code."""

    exit_code: int = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConfigError(DgaError):
    exit_code = 2


class PathMappingError(DgaError):
    exit_code = 2


class RcloneNotFoundError(DgaError):
    exit_code = 3


class RcloneMetadataError(DgaError):
    exit_code = 4


class ClipboardError(DgaError):
    exit_code = 5


class SetupError(DgaError):
    exit_code = 2


class BrowserError(DgaError):
    exit_code = 6
