"""Lightweight CoE (Center of Excellence) client stub.

This module defines a minimal client surface area used by the `ppx coe` CLI
for inventory, makers, metrics, and export flows. The real implementation can
be built on top of :class:`pacx.http_client.HttpClient`; for now, methods raise
``NotImplementedError`` by default and are expected to be monkeypatched/stubbed
in tests.

Public methods are typed to keep the surface stable for future expansion.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class CoeClient:
    """Client facade for CoE insights and export helpers."""

    def __init__(self, token_getter: Callable[[], str]) -> None:
        # Intentionally minimal; real implementation would store HttpClient.
        self._token_getter = token_getter

    # Inventory -----------------------------------------------------------------
    def inventory(self, *, environment_id: str | None = None) -> list[dict[str, Any]]:
        """Return a flat inventory of apps/flows for optional environment scope.

        Each item should contain at least: ``type``, ``id``, and ``name``.
        """

        raise NotImplementedError

    # Makers --------------------------------------------------------------------
    def makers(self, *, environment_id: str | None = None) -> list[dict[str, Any]]:
        """Return a list of makers (users) with minimal identity fields."""

        raise NotImplementedError

    # Metrics -------------------------------------------------------------------
    def metrics(self, *, environment_id: str | None = None) -> dict[str, Any]:
        """Return summary metrics for apps, flows, and makers."""

        raise NotImplementedError
