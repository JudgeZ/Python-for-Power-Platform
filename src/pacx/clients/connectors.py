
from __future__ import annotations

from typing import Any, Dict, Optional

from ..http_client import HttpClient


DEFAULT_API_VERSION = "2022-03-01-preview"


class ConnectorsClient:
    """Client for Custom Connectors (APIs) via Power Apps endpoints."""

    def __init__(
        self,
        token_getter,
        base_url: str = "https://api.powerplatform.com",
        api_version: str = DEFAULT_API_VERSION,
    ) -> None:
        self.http = HttpClient(base_url, token_getter=token_getter)
        self.api_version = api_version

    def list_apis(self, environment_id: str, top: Optional[int] = None, skiptoken: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"api-version": self.api_version}
        if top is not None:
            params["$top"] = top
        if skiptoken:
            params["$skiptoken"] = skiptoken
        resp = self.http.get(f"powerapps/environments/{environment_id}/apis", params=params)
        return resp.json()

    def get_api(self, environment_id: str, api_name: str) -> Dict[str, Any]:
        params = {"api-version": self.api_version}
        resp = self.http.get(f"powerapps/environments/{environment_id}/apis/{api_name}", params=params)
        return resp.json()

    def put_api(self, environment_id: str, api_name: str, body: Dict[str, Any]) -> Dict[str, Any]:
        params = {"api-version": self.api_version}
        resp = self.http.put(f"powerapps/environments/{environment_id}/apis/{api_name}", params=params, json=body)
        return resp.json() if resp.text else {}

    def put_api_from_openapi(self, environment_id: str, api_name: str, openapi_text: str, display_name: str | None = None) -> Dict[str, Any]:
        body = {
            "name": api_name,
            "properties": {
                "displayName": display_name or api_name,
                "iconBrandColor": "#0078D4",
                "apiDefinition": {
                    "format": "swagger",
                    "value": openapi_text,
                },
            },
        }
        return self.put_api(environment_id, api_name, body)
