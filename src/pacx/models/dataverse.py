from __future__ import annotations
from pydantic import BaseModel
from typing import Optional

class Solution(BaseModel):
    solutionid: Optional[str] = None
    uniquename: Optional[str] = None
    friendlyname: Optional[str] = None
    version: Optional[str] = None

class ExportSolutionRequest(BaseModel):
    SolutionName: str
    Managed: bool = False

class ImportSolutionRequest(BaseModel):
    OverwriteUnmanagedCustomizations: bool = True
    PublishWorkflows: bool = True
    CustomizationFile: str  # base64 zip
    ImportJobId: str | None = None
