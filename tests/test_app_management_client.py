from __future__ import annotations

import httpx
import pytest

from pacx.clients.app_management import ApplicationOperationHandle, AppManagementClient
from pacx.models.app_management import ApplicationPackageOperation


@pytest.fixture
def build_client(token_getter):
    def factory(api_version: str | None = None) -> AppManagementClient:
        if api_version:
            return AppManagementClient(token_getter, api_version=api_version)
        return AppManagementClient(token_getter)

    return factory


def test_list_tenant_packages(respx_mock, build_client):
    client = build_client()
    route = respx_mock.get(
        "https://api.powerplatform.com/appmanagement/applicationPackages",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "packageId": "pkg-1",
                        "displayName": "Package One",
                        "version": "1.0.0",
                    }
                ]
            },
        )
    )

    packages = client.list_tenant_packages()

    assert route.called
    assert len(packages) == 1
    assert packages[0].package_id == "pkg-1"
    assert packages[0].display_name == "Package One"


def test_list_environment_packages(respx_mock, build_client):
    client = build_client()
    route = respx_mock.get(
        "https://api.powerplatform.com/appmanagement/environments/env-1/applicationPackages",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "packageId": "pkg-2",
                        "displayName": "Package Two",
                        "environmentId": "env-1",
                        "version": "2.0.0",
                    }
                ]
            },
        )
    )

    packages = client.list_environment_packages("env-1")

    assert route.called
    assert len(packages) == 1
    assert packages[0].environment_id == "env-1"


def test_install_application_package(respx_mock, build_client):
    client = build_client()
    route = respx_mock.post(
        "https://api.powerplatform.com/appmanagement/applications/installApplicationPackage",
        params={"api-version": "2022-03-01-preview"},
        json={"packageId": "pkg", "environmentId": "env"},
    ).mock(
        return_value=httpx.Response(
            202,
            json={"operationId": "op-1", "status": "Running"},
            headers={
                "Operation-Location": "https://api.powerplatform.com/appmanagement/applications/installStatuses/op-1"
            },
        )
    )

    handle = client.install_application_package("pkg", "env")

    assert route.called
    assert handle.operation_location.endswith("op-1")
    assert handle.metadata is not None
    assert handle.metadata.operation_id == "op-1"


def test_install_environment_package(respx_mock, build_client):
    client = build_client()
    route = respx_mock.post(
        "https://api.powerplatform.com/appmanagement/environments/env-1/applicationPackages/app-1/install",
        params={"api-version": "2022-03-01-preview"},
        json={"param": "value"},
    ).mock(return_value=httpx.Response(202, json={"operationId": "op-env"}))

    handle = client.install_environment_package("env-1", "app-1", payload={"param": "value"})

    assert route.called
    assert handle.metadata is not None
    assert handle.metadata.operation_id == "op-env"


def test_upgrade_environment_package(respx_mock, build_client):
    client = build_client()
    route = respx_mock.post(
        "https://api.powerplatform.com/appmanagement/environments/env-1/applicationPackages/pkg-1:upgrade",
        params={"api-version": "2022-03-01-preview"},
        json={"targetVersion": "3.0"},
    ).mock(return_value=httpx.Response(202, json={"operationId": "op-upgrade"}))

    handle = client.upgrade_environment_package("env-1", "pkg-1", payload={"targetVersion": "3.0"})

    assert route.called
    assert handle.metadata is not None
    assert handle.metadata.operation_id == "op-upgrade"


def test_get_install_status(respx_mock, build_client):
    client = build_client()
    respx_mock.get(
        "https://api.powerplatform.com/appmanagement/applications/installStatuses/op-1",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"operationId": "op-1", "status": "Succeeded"}))

    status = client.get_install_status("op-1")

    assert isinstance(status, ApplicationPackageOperation)
    assert status.status == "Succeeded"


def test_get_environment_operation_status(respx_mock, build_client):
    client = build_client()
    respx_mock.get(
        "https://api.powerplatform.com/appmanagement/environments/env-1/operations/op-2",
        params={"api-version": "2022-03-01-preview"},
    ).mock(return_value=httpx.Response(200, json={"operationId": "op-2", "status": "Running"}))

    status = client.get_environment_operation_status("env-1", "op-2")

    assert isinstance(status, ApplicationPackageOperation)
    assert status.operation_id == "op-2"


def test_wait_for_operation_uses_location(respx_mock, build_client):
    client = build_client()
    route = respx_mock.get(
        "https://api.powerplatform.com/appmanagement/applications/installStatuses/op-1",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        side_effect=[
            httpx.Response(200, json={"status": "Running", "percentComplete": 50}),
            httpx.Response(200, json={"status": "Succeeded", "operationId": "op-1"}),
        ]
    )
    handle = ApplicationOperationHandle(
        "https://api.powerplatform.com/appmanagement/applications/installStatuses/op-1",
        ApplicationPackageOperation(operation_id="op-1"),
    )

    result = client.wait_for_operation(handle, interval=0.0, timeout=1.0)

    assert route.called
    assert result.status == "Succeeded"


def test_wait_for_operation_builds_status_path(respx_mock, build_client):
    client = build_client()
    route = respx_mock.get(
        "https://api.powerplatform.com/appmanagement/environments/env-1/operations/op-2",
        params={"api-version": "2022-03-01-preview"},
    ).mock(
        side_effect=[
            httpx.Response(200, json={"status": "Running"}),
            httpx.Response(200, json={"status": "Succeeded", "operationId": "op-2"}),
        ]
    )
    handle = ApplicationOperationHandle(None, ApplicationPackageOperation(operation_id="op-2"))

    result = client.wait_for_operation(handle, environment_id="env-1", interval=0.0, timeout=1.0)

    assert route.called
    assert result.operation_id == "op-2"
