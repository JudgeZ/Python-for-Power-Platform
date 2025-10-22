from __future__ import annotations
from abc import ABC, abstractmethod

class TokenProvider(ABC):
    @abstractmethod
    def get_token(self) -> str:
        """Return an access token string for Authorization: Bearer."""

class StaticTokenProvider(TokenProvider):
    def __init__(self, token: str) -> None:
        self._token = token
    def get_token(self) -> str:
        return self._token
