from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from types import TracebackType
from typing import Any, cast
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from ..errors import HttpError
from ..http_client import HttpClient

DEFAULT_API_VERSION = "2022-03-01-preview"


class ConnectorsClient:
    """Client for Custom Connectors (APIs) via Power Apps endpoints."""

    def __init__(
        self,
        token_getter: Callable[[], str],
        base_url: str = "https://api.powerplatform.com",
        api_version: str = DEFAULT_API_VERSION,
        *,
        use_connectivity: bool = False,
        client_request_id: str | None = None,
    ) -> None:
        """Initialize the connectors client with HTTP transport configuration.

        Args:
            token_getter: Callable that returns an access token for requests.
            base_url: Power Platform base URL for connector operations.
            api_version: REST API version passed as the ``api-version`` query
                parameter.
            use_connectivity: Toggle for the ARM-style ``/connectivity``
                endpoints.
            client_request_id: Optional identifier injected into the
                ``x-ms-client-request-id`` header on connectivity calls.
        """
        self.http = HttpClient(base_url, token_getter=token_getter)
        self.api_version = api_version
        self.use_connectivity = use_connectivity
        self._client_request_id = client_request_id or str(uuid4())

    def close(self) -> None:
        """Close the underlying HTTP client."""

        self.http.close()

    def __enter__(self) -> ConnectorsClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
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
        if self.use_connectivity:
            return self.list_custom_connectors(
                environment_id,
                top=top,
                skiptoken=skiptoken,
            )
        params: dict[str, Any] = {"api-version": self.api_version}
        if top is not None:
            params["$top"] = top
        if skiptoken:
            params["$skiptoken"] = skiptoken
        resp = self.http.get(f"powerapps/environments/{environment_id}/apis", params=params)
        return cast(dict[str, Any], resp.json())

    @staticmethod
    def _extract_next_link(payload: Mapping[str, object]) -> str | None:
        for key in ("@odata.nextLink", "odata.nextLink", "nextLink"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _extract_skiptoken(link: str) -> str | None:
        parsed = urlparse(link)
        query = parse_qs(parsed.query)
        for key in ("$skiptoken", "skiptoken"):
            tokens = query.get(key)
            if tokens:
                token = tokens[0]
                if isinstance(token, str) and token:
                    return token
        return None

    @staticmethod
    def _coerce_items(payload: Mapping[str, object]) -> list[dict[str, Any]]:
        raw_items = payload.get("value", [])
        if not isinstance(raw_items, Iterable):
            return []
        items: list[dict[str, Any]] = []
        for obj in raw_items:
            if isinstance(obj, Mapping):
                items.append(dict(obj))
        return items

    def iter_apis(
        self, environment_id: str, *, top: int | None = None
    ) -> Iterator[list[dict[str, Any]]]:
        """Yield connector pages by following ``@odata.nextLink`` pointers.

        Args:
            environment_id: Target environment unique name.
            top: Optional page size override sent on the initial request.

        Yields:
            Lists of connector definitions from each page returned by the
            service.
        """

        payload = self.list_apis(environment_id, top=top)
        while True:
            yield self._coerce_items(payload)
            next_link = self._extract_next_link(payload)
            if not next_link:
                break
            skiptoken = self._extract_skiptoken(next_link)
            if skiptoken:
                payload = self.list_apis(environment_id, skiptoken=skiptoken)
            else:
                payload = cast(dict[str, Any], self.http.get(next_link).json())

    def get_api(self, environment_id: str, api_name: str) -> dict[str, Any]:
        """Fetch a connector definition from an environment by logical name.

        Args:
            environment_id: Target environment unique name.
            api_name: Connector logical name (``{publisher}_{name}``).

        Returns:
            JSON metadata describing the requested connector.
        """
        if self.use_connectivity:
            return self.get_custom_connector(environment_id, api_name)
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
        if self.use_connectivity:
            try:
                return self.update_custom_connector(environment_id, api_name, body)
            except HttpError as exc:
                if exc.status_code != 404:
                    raise
                return self.create_custom_connector(environment_id, api_name, body)
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
        body = self._build_openapi_payload(api_name, openapi_text, display_name)
        return self.put_api(environment_id, api_name, body)

    def delete_api(self, environment_id: str, api_name: str) -> bool:
        """Delete a connector API from an environment.

        Args:
            environment_id: Target environment unique name.
            api_name: Connector logical name to remove.

        Returns:
            ``True`` when the service responds with a 2xx status code.
        """

        if self.use_connectivity:
            return self.delete_custom_connector(environment_id, api_name)
        params = {"api-version": self.api_version}
        resp = self.http.delete(
            f"powerapps/environments/{environment_id}/apis/{api_name}",
            params=params,
        )
        return 200 <= resp.status_code < 300

    @staticmethod
    def _build_openapi_payload(
        api_name: str, openapi_text: str, display_name: str | None
    ) -> dict[str, Any]:
        return {
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

    def _connectivity_headers(
        self, extra: Mapping[str, str] | None = None
    ) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "x-ms-client-request-id": self._client_request_id,
        }
        if extra:
            headers.update(extra)
        return headers

    def _connectivity_params(self, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"api-version": self.api_version}
        if extra:
            for key, value in extra.items():
                if value is not None:
                    params[key] = value
        return params

    @staticmethod
    def _arm_resource_name(environment_id: str, connector_id: str) -> str:
        return (
            f"/providers/Microsoft.PowerApps/environments/{environment_id}/"
            f"customConnectors/{connector_id}"
        )

    def list_custom_connectors(
        self,
        environment_id: str,
        *,
        filter_expression: str | None = None,
        top: int | None = None,
        skiptoken: str | None = None,
    ) -> dict[str, Any]:
        """List custom connectors in an environment via the connectivity API."""

        params = self._connectivity_params(
            {"$filter": filter_expression, "$top": top, "$skiptoken": skiptoken}
        )
        resp = self.http.get(
            f"connectivity/environments/{environment_id}/customConnectors",
            params=params,
            headers=self._connectivity_headers(),
        )
        return cast(dict[str, Any], resp.json())

    def get_custom_connector(self, environment_id: str, connector_id: str) -> dict[str, Any]:
        """Retrieve a custom connector definition via the connectivity API."""

        params = self._connectivity_params()
        resp = self.http.get(
            f"connectivity/environments/{environment_id}/customConnectors/{connector_id}",
            params=params,
            headers=self._connectivity_headers(),
        )
        return cast(dict[str, Any], resp.json())

    def create_custom_connector(
        self, environment_id: str, connector_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a custom connector using the ARM-style endpoints."""

        payload = dict(body)
        arm_name = self._arm_resource_name(environment_id, connector_id)
        name = payload.get("name")
        if not isinstance(name, str) or not name.startswith("/"):
            payload["name"] = arm_name
        payload.setdefault("id", arm_name)
        payload.setdefault("type", "Microsoft.PowerApps/customConnectors")
        resp = self.http.post(
            f"connectivity/environments/{environment_id}/customConnectors",
            params=self._connectivity_params(),
            json=payload,
            headers=self._connectivity_headers(),
        )
        return cast(dict[str, Any], resp.json())

    def update_custom_connector(
        self, environment_id: str, connector_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """Patch an existing custom connector definition."""

        payload = dict(body)
        arm_name = self._arm_resource_name(environment_id, connector_id)
        name = payload.get("name")
        if not isinstance(name, str) or not name.startswith("/"):
            payload["name"] = arm_name
        resp = self.http.patch(
            f"connectivity/environments/{environment_id}/customConnectors/{connector_id}",
            params=self._connectivity_params(),
            json=payload,
            headers=self._connectivity_headers(),
        )
        return cast(dict[str, Any], resp.json())

    def delete_custom_connector(self, environment_id: str, connector_id: str) -> bool:
        """Delete a custom connector resource."""

        resp = self.http.delete(
            f"connectivity/environments/{environment_id}/customConnectors/{connector_id}",
            params=self._connectivity_params(),
            headers=self._connectivity_headers(),
        )
        return 200 <= resp.status_code < 300

    def validate_custom_connector(
        self, environment_id: str, connector_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate a custom connector definition without persisting changes."""

        body = dict(payload)
        resp = self.http.post(
            f"connectivity/environments/{environment_id}/customConnectors/{connector_id}:validate",
            params=self._connectivity_params(),
            json=body,
            headers=self._connectivity_headers(),
        )
        return cast(dict[str, Any], resp.json())

    def validate_custom_connector_from_openapi(
        self,
        environment_id: str,
        connector_id: str,
        openapi_text: str,
        *,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        """Validate a custom connector using an OpenAPI document."""

        payload = self._build_openapi_payload(connector_id, openapi_text, display_name)
        return self.validate_custom_connector(environment_id, connector_id, payload)

    def get_custom_connector_runtime_status(
        self, environment_id: str, connector_id: str
    ) -> dict[str, Any]:
        """Return runtime health information for a custom connector."""

        resp = self.http.get(
            f"connectivity/environments/{environment_id}/customConnectors/{connector_id}/runtimeStatus",
            params=self._connectivity_params(),
            headers=self._connectivity_headers(),
        )
        return cast(dict[str, Any], resp.json())

    def list_policy_templates(self) -> dict[str, Any]:
        """List available policy templates for custom connectors."""

        resp = self.http.get(
            "connectivity/policyTemplates",
            params=self._connectivity_params(),
            headers=self._connectivity_headers(),
        )
        return cast(dict[str, Any], resp.json())

    def get_policy_template(self, policy_template_id: str) -> dict[str, Any]:
        """Fetch a policy template by identifier."""

        resp = self.http.get(
            f"connectivity/policyTemplates/{policy_template_id}",
            params=self._connectivity_params(),
            headers=self._connectivity_headers(),
        )
        return cast(dict[str, Any], resp.json())
