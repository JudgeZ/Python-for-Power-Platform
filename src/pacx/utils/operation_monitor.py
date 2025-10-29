from __future__ import annotations

import time
from typing import Any

from ..http_client import HttpClient


class OperationMonitor:
    """Poll a long‑running operation URL until completion or timeout.

    The monitor issues GET requests against ``url`` using the provided
    :class:`HttpClient` and inspects the JSON payload for a status/state field.
    Polling stops when the state is one of {Succeeded, Completed, Failed,
    Canceled, Cancelled, Faulted, Error} (case‑insensitive) or the timeout elapses. The last JSON
    payload is returned.
    """

    terminal_states = frozenset(
        {
            "succeeded",
            "completed",
            "failed",
            "canceled",
            "cancelled",
            "faulted",
            "error",
        }
    )

    def track(
        self,
        client: HttpClient,
        url: str,
        *,
        timeout_s: int = 900,
        interval_s: float = 1.5,
    ) -> dict[str, Any]:
        start = time.time()
        last: dict[str, Any] = {}
        while True:
            resp = client.get(url)
            try:
                data = resp.json()
            except Exception:
                data = {}
            if isinstance(data, dict):
                last = data
            state = str(
                last.get("status") or last.get("state") or last.get("provisioningState") or ""
            ).lower()
            if state in self.terminal_states:
                return last
            if time.time() - start >= timeout_s:
                return last
            time.sleep(interval_s)
