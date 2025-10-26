from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from types import TracebackType
from typing import Any

import httpx

from .errors import HttpError


class HttpClient:
    """Thin httpx wrapper that injects Authorization and handles errors + basic retry."""

    def __init__(
        self,
        base_url: str,
        token_getter: Callable[[], str] | None = None,
        default_headers: dict[str, str] | None = None,
        data: bytes | str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        retry_statuses: Iterable[int] | None = None,
        backoff_factor: float = 0.5,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._token_getter = token_getter
        self._client = httpx.Client(timeout=timeout)
        self._default_headers = default_headers or {}
        self._max_retries = max_retries
        self._retry_statuses: set[int] = set(retry_statuses or {429, 500, 502, 503, 504})
        self._backoff_factor = backoff_factor

    def _auth_header(self) -> dict[str, str]:
        if not self._token_getter:
            return {}
        token = self._token_getter()
        return {"Authorization": f"Bearer {token}"} if token else {}

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        headers: dict[str, str] | None = None,
        data: bytes | str | None = None,
        content: bytes | str | None = None,
    ) -> httpx.Response:
        if path.startswith(("http://", "https://")):
            url = path
        else:
            url = f"{self.base_url}/{path.lstrip('/')}"
        merged_headers = {**self._default_headers, **(headers or {}), **self._auth_header()}
        attempt = 0
        while True:
            try:
                request_kwargs: dict[str, Any] = {
                    "params": params,
                    "headers": merged_headers,
                }
                if json is not None:
                    request_kwargs["json"] = json
                if content is not None:
                    request_kwargs["content"] = content
                else:
                    request_kwargs["data"] = data
                resp = self._client.request(method, url, **request_kwargs)
            except httpx.TransportError as e:
                if attempt < self._max_retries:
                    time.sleep(self._backoff_factor * (2**attempt))
                    attempt += 1
                    continue
                raise HttpError(0, f"Transport error: {e}") from e

            if resp.status_code in self._retry_statuses and attempt < self._max_retries:
                ra = resp.headers.get("Retry-After")
                delay = float(ra) if ra and ra.isdigit() else self._backoff_factor * (2**attempt)
                time.sleep(delay)
                attempt += 1
                continue

            if resp.status_code >= 400:
                try:
                    detail = resp.json()
                except Exception:
                    detail = resp.text
                raise HttpError(resp.status_code, resp.reason_phrase, details=detail)
            return resp

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", path, **kwargs)

    def close(self) -> None:
        """Close the underlying :class:`httpx.Client`."""

        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
