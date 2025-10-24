from __future__ import annotations

from typing import Any, Callable, cast

from ..http_client import HttpClient

DEFAULT_API_VERSION = "2022-03-01-preview"


class ConnectorsClient:
    """Client for Custom Connectors (APIs) via Power Apps endpoints."""

    def __init__(
        self,
        token_getter: Callable[[], str],
        base_url: str = "https://api.powerplatform.com",
        api_version: str = DEFAULT_API_VERSION,
    ) -> None:
        """Initialize the connectors client with HTTP transport configuration.

        Args:
            token_getter: Callable that returns an access token for requests.
            base_url: Power Platform base URL for connector operations.
            api_version: REST API version passed as the ``api-version`` query
                parameter.
        """
        self.http = HttpClient(base_url, token_getter=token_getter)
        self.api_version = api_version

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self.http.close()

    def __enter__(self) -> ConnectorsClient:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def list_apis(
        self, environment_id: str, top: int | None = None, skiptoken: str | None = None
    ) -> dict[str, Any]:
        """Return a page of custom connectors available in an environment.

        Args:
            environment_id: Target environment unique name.
            top: Optional page size override for the ``$top`` query option.
            skiptoken: Continuation token returned from a previous page.

        Returns:
            Connector list payload from the Power Apps API response.
        """
        params: dict[str, Any] = {"api-version": self.api_version}
        if top is not None:
            params["$top"] = top
        if skiptoken:
            params["$skiptoken"] = skiptoken
        resp = self.http.get(f"powerapps/environments/{environment_id}/apis", params=params)
        return cast(dict[str, Any], resp.json())

    def get_api(self, environment_id: str, api_name: str) -> dict[str, Any]:
        """Fetch a connector definition from an environment by logical name.

        Args:
            environment_id: Target environment unique name.
            api_name: Connector logical name (``{publisher}_{name}``).

        Returns:
            JSON metadata describing the requested connector.
        """
        params = {"api-version": self.api_version}
        resp = self.http.get(
            f"powerapps/environments/{environment_id}/apis/{api_name}", params=params
        )
        return cast(dict[str, Any], resp.json())

    def put_api(self, environment_id: str, api_name: str, body: dict[str, Any]) -> dict[str, Any]:
        """Create or update a connector definition with a raw request body.

        Args:
            environment_id: Target environment unique name.
            api_name: Connector logical name to create or update.
            body: Connector payload that will be serialized as JSON.

        Returns:
            Connector metadata returned from the API, or an empty dict when the
            response contains no JSON body.
        """
        params = {"api-version": self.api_version}
        resp = self.http.put(
            f"powerapps/environments/{environment_id}/apis/{api_name}", params=params, json=body
        )
        return cast(dict[str, Any], resp.json()) if resp.text else {}

    def put_api_from_openapi(
        self, environment_id: str, api_name: str, openapi_text: str, display_name: str | None = None
    ) -> dict[str, Any]:
        """Provision a connector from an OpenAPI document.

        Args:
            environment_id: Target environment unique name.
            api_name: Connector logical name to create or update.
            openapi_text: OpenAPI document content (Swagger JSON/YAML) as a
                string.
            display_name: Optional friendly name shown in the maker portal.

        Returns:
            Connector metadata returned from the API after the operation.
        """
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

    def delete_api(self, environment_id: str, api_name: str) -> bool:
        """Delete a connector API from an environment.

        Args:
            environment_id: Target environment unique name.
            api_name: Connector logical name to remove.

        Returns:
            ``True`` when the service responds with a 2xx status code.
        """

        params = {"api-version": self.api_version}
        resp = self.http.delete(
            f"powerapps/environments/{environment_id}/apis/{api_name}",
            params=params,
        )
        return 200 <= resp.status_code < 300
