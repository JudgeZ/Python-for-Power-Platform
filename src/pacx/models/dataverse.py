from __future__ import annotations

from pydantic import BaseModel


class Solution(BaseModel):
    solutionid: str | None = None
    uniquename: str | None = None
    friendlyname: str | None = None
    version: str | None = None


class ExportSolutionRequest(BaseModel):
    SolutionName: str
    Managed: bool = False


class ImportSolutionRequest(BaseModel):
    OverwriteUnmanagedCustomizations: bool = True
    PublishWorkflows: bool = True
    CustomizationFile: str  # base64 zip
    ImportJobId: str | None = None
