from __future__ import annotations

import base64
from typing import Any

from pydantic import BaseModel, field_validator


def _encode_base64(value: str | bytes | bytearray) -> str:
    if isinstance(value, str):
        return value
    data = bytes(value)
    return base64.b64encode(data).decode("ascii")


class Solution(BaseModel):
    solutionid: str | None = None
    uniquename: str | None = None
    friendlyname: str | None = None
    version: str | None = None


class ExportSolutionRequest(BaseModel):
    SolutionName: str
    Managed: bool = False


class ExportSolutionAsManagedRequest(ExportSolutionRequest):
    Managed: bool = True

    @field_validator("Managed", mode="before")
    @classmethod
    def _enforce_managed_true(cls, value: Any) -> bool:
        return True


class ExportSolutionUpgradeRequest(BaseModel):
    SolutionName: str
    IncludeTranslations: bool | None = None
    IncludeSales: bool | None = None


class ExportTranslationRequest(BaseModel):
    SolutionName: str


class ExportTranslationResponse(BaseModel):
    ExportTranslationFile: str | None = None


class ImportSolutionRequest(BaseModel):
    OverwriteUnmanagedCustomizations: bool = True
    PublishWorkflows: bool = True
    CustomizationFile: str  # base64 zip
    ImportJobId: str | None = None

    @field_validator("CustomizationFile", mode="before")
    @classmethod
    def _encode_customization_file(cls, value: str | bytes | bytearray) -> str:
        return _encode_base64(value)


class ImportTranslationRequest(BaseModel):
    TranslationFile: str  # base64 zip
    ImportJobId: str

    @field_validator("TranslationFile", mode="before")
    @classmethod
    def _encode_translation_file(cls, value: str | bytes | bytearray) -> str:
        return _encode_base64(value)


class CloneAsPatchRequest(BaseModel):
    ParentSolutionUniqueName: str
    DisplayName: str
    VersionNumber: str


class CloneAsPatchResponse(BaseModel):
    SolutionId: str | None = None


class CloneAsSolutionRequest(BaseModel):
    ParentSolutionUniqueName: str
    DisplayName: str
    VersionNumber: str


class CloneAsSolutionResponse(BaseModel):
    SolutionId: str | None = None


class DeleteAndPromoteRequest(BaseModel):
    UniqueName: str


class ApplySolutionUpgradeRequest(BaseModel):
    SolutionName: str
    DeleteHoldingSolution: bool | None = None


class StageSolutionRequest(BaseModel):
    CustomizationFile: str  # base64 zip
    StageSolutionUploadId: str | None = None

    @field_validator("CustomizationFile", mode="before")
    @classmethod
    def _encode_stage_solution_file(cls, value: str | bytes | bytearray) -> str:
        return _encode_base64(value)


class StageSolutionResponse(BaseModel):
    StageSolutionResults: dict[str, Any] | None = None
