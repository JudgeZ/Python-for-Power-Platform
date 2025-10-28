"""Models supporting Power Automate client operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .power_platform import CloudFlow

CloudFlowState = Literal["Started", "Stopped", "Suspended"]


@dataclass(frozen=True, slots=True)
class CloudFlowPage:
    """Container for a page of cloud flows and paging metadata."""

    flows: list[CloudFlow] = field(default_factory=list)
    next_link: str | None = None
    continuation_token: str | None = None

    def is_empty(self) -> bool:
        """Return ``True`` when the page does not contain any flows."""

        return not self.flows


class CloudFlowStatePatch(BaseModel):
    """Payload used when toggling the state of a cloud flow."""

    state: CloudFlowState

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    def to_payload(self) -> dict[str, str]:
        """Return a JSON-safe payload compatible with the REST endpoint."""

        return self.model_dump(by_alias=True, exclude_none=True)


__all__ = [
    "CloudFlowPage",
    "CloudFlowState",
    "CloudFlowStatePatch",
]
