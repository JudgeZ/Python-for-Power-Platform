from __future__ import annotations

import time
from collections.abc import Callable
from typing import Generic, TypeVar

StatusType = TypeVar("StatusType")


class PollTimeoutError(TimeoutError, Generic[StatusType]):
    """Timeout raised by :func:`poll_until` with last status metadata."""

    def __init__(self, timeout: float, last_status: StatusType | None) -> None:
        super().__init__(f"Operation did not complete within {timeout} seconds")
        self.timeout = timeout
        self.last_status = last_status


def poll_until(
    get_status: Callable[[], StatusType],
    is_done: Callable[[StatusType], bool],
    get_progress: Callable[[StatusType], int | None] | None = None,
    interval: float = 2.0,
    timeout: float = 600.0,
    on_update: Callable[[StatusType], None] | None = None,
) -> StatusType:
    """Generic polling loop for long-running operations."""
    start = time.time()
    last_pct = None
    while True:
        status = get_status()
        if on_update:
            on_update(status)
        if get_progress:
            pct = get_progress(status)
            if pct is not None and pct != last_pct:
                last_pct = pct
        if is_done(status):
            return status
        if time.time() - start > timeout:
            raise PollTimeoutError(timeout, status)
        time.sleep(interval)


__all__ = ["PollTimeoutError", "poll_until"]
