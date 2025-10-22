from __future__ import annotations
from typing import Any, Optional

class PacxError(Exception):
    """Base error for PACX."""

class AuthError(PacxError):
    pass

class HttpError(PacxError):
    def __init__(self, status_code: int, message: str, *, details: Optional[Any] = None) -> None:
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.details = details
