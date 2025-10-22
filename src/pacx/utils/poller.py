
from __future__ import annotations

import time
from typing import Callable, Dict, Any, Optional


def poll_until(
    get_status: Callable[[], Dict[str, Any]],
    is_done: Callable[[Dict[str, Any]], bool],
    get_progress: Optional[Callable[[Dict[str, Any]], Optional[int]]] = None,
    interval: float = 2.0,
    timeout: float = 600.0,
    on_update: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
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
            return status
        time.sleep(interval)
