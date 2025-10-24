from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EnvironmentSummary(BaseModel):
    id: str | None = None
    name: str | None = None
    type: str | None = Field(default=None, alias="environmentType")
    location: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class PowerApp(BaseModel):
    id: str | None = None
    name: str | None = None
    type: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class CloudFlow(BaseModel):
    id: str | None = None
    name: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class FlowRun(BaseModel):
    id: str | None = None
    name: str | None = None
    status: str | None = None
    start_time: str | None = Field(default=None, alias="startTime")
    end_time: str | None = Field(default=None, alias="endTime")

    model_config = ConfigDict(populate_by_name=True)
