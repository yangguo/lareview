from __future__ import annotations


class LareviewError(Exception):
    """Base error for backend service."""


class InvalidFileError(LareviewError):
    """Raised when an uploaded file cannot be parsed."""


class MissingColumnError(LareviewError):
    """Raised when required columns are missing."""


class AmbiguousTableError(LareviewError):
    """Raised when table classification is ambiguous."""


class EmptyDatasetError(LareviewError):
    """Raised when required datasets are empty."""
