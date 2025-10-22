from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

class EnvironmentSummary(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = Field(default=None, alias="environmentType")
    location: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)

class PowerApp(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)

class CloudFlow(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)

class FlowRun(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    status: Optional[str] = None
    startTime: Optional[str] = None
    endTime: Optional[str] = None
