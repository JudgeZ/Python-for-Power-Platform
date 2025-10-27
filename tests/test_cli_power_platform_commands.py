from __future__ import annotations

import importlib
import sys
from typing import Iterable

import pytest
import typer

from pacx.clients.power_platform import AppVersionPage, OperationHandle
from pacx.models.power_platform import AppPermissionAssignment, AppVersion


def load_cli_app(monkeypatch: pytest.MonkeyPatch):
    original_option = typer.Option

    def patched_option(*args, **kwargs):
        kwargs.pop("multiple", None)
        return original_option(*args, **kwargs)

    monkeypatch.setattr(typer, "Option", patched_option)
    for module in [name for name in sys.modules if name.startswith("pacx.cli")]:
        sys.modules.pop(module)
    module = importlib.import_module("pacx.cli")
    return module.app, module


class StubEnvironment:
    def __init__(self, name: str, type: str = "Production", location: str = "us") -> None:
        self.name = name
        self.type = type
        self.location = location
        self.id = name


class StubSummary:
    def __init__(self, identifier: str) -> None:
        self.name = identifier
        self.id = identifier


class StubPowerPlatformClient:
    instances: list["StubPowerPlatformClient"] = []

    def __init__(self, token_getter, api_version: str | None = None) -> None:
        self.token = token_getter()
        self.api_version = api_version
        self.apps_calls: list[str] = []
        self.flows_calls: list[str] = []
        self.copy_calls: list[tuple[str, dict[str, object]]] = []
        self.reset_calls: list[tuple[str, dict[str, object]]] = []
        self.backup_calls: list[tuple[str, dict[str, object]]] = []
        self.restore_calls: list[tuple[str, dict[str, object]]] = []
        self.apply_calls: list[tuple[str, str]] = []
        self.revoke_calls: list[tuple[str, str]] = []
        self.version_calls: list[tuple[str, str, dict[str, object]]] = []
        self.app_restore_calls: list[tuple[str, str, dict[str, object]]] = []
        self.publish_calls: list[tuple[str, str, dict[str, object]]] = []
        self.share_calls: list[tuple[str, str, dict[str, object]]] = []
        self.revoke_share_calls: list[tuple[str, str, dict[str, object]]] = []
        self.permission_calls: list[tuple[str, str]] = []
        self.set_owner_calls: list[tuple[str, str, dict[str, object]]] = []
        StubPowerPlatformClient.instances.append(self)

    def list_environments(self) -> Iterable[StubEnvironment]:
        return [StubEnvironment("env-1"), StubEnvironment("env-2", location="eu")]

    def list_apps(self, environment_id: str) -> Iterable[StubSummary]:
        self.apps_calls.append(environment_id)
        return [StubSummary("app-1"), StubSummary("app-2")]

    def list_cloud_flows(self, environment_id: str) -> Iterable[StubSummary]:
        self.flows_calls.append(environment_id)
        return [StubSummary("flow-1")]

    def copy_environment(self, environment_id: str, payload: dict[str, object]) -> OperationHandle:
        self.copy_calls.append((environment_id, payload))
        return OperationHandle("https://example/operations/copy", {"status": "Accepted"})

    def reset_environment(self, environment_id: str, payload: dict[str, object]) -> OperationHandle:
        self.reset_calls.append((environment_id, payload))
        return OperationHandle("https://example/operations/reset", {})

    def backup_environment(self, environment_id: str, payload: dict[str, object]) -> OperationHandle:
        self.backup_calls.append((environment_id, payload))
        return OperationHandle("https://example/operations/backup", {})

    def restore_environment(self, environment_id: str, payload: dict[str, object]) -> OperationHandle:
        self.restore_calls.append((environment_id, payload))
        return OperationHandle("https://example/operations/restore", {})

    def list_app_versions(
        self,
        environment_id: str,
        app_id: str,
        *,
        top: int | None = None,
        skiptoken: str | None = None,
    ) -> AppVersionPage:
        params: dict[str, object] = {}
        if top is not None:
            params["top"] = top
        if skiptoken is not None:
            params["skiptoken"] = skiptoken
        self.version_calls.append((environment_id, app_id, params))
        versions = [
            AppVersion(id="ver-1", version_id="1.0"),
            AppVersion(id="ver-2", version_id="2.0"),
        ]
        return AppVersionPage(versions, next_link="next", continuation_token="token")

    def restore_app(self, environment_id: str, app_id: str, payload: dict[str, object]) -> OperationHandle:
        self.app_restore_calls.append((environment_id, app_id, payload))
        return OperationHandle("https://example/operations/app-restore", {})

    def publish_app(self, environment_id: str, app_id: str, payload: dict[str, object]) -> OperationHandle:
        self.publish_calls.append((environment_id, app_id, payload))
        return OperationHandle("https://example/operations/app-publish", {})

    def share_app(self, environment_id: str, app_id: str, payload: dict[str, object]) -> OperationHandle:
        self.share_calls.append((environment_id, app_id, payload))
        return OperationHandle("https://example/operations/app-share", {})

    def revoke_app_share(
        self, environment_id: str, app_id: str, payload: dict[str, object]
    ) -> OperationHandle:
        self.revoke_share_calls.append((environment_id, app_id, payload))
        return OperationHandle("https://example/operations/app-revoke", {})

    def list_app_permissions(
        self, environment_id: str, app_id: str
    ) -> Iterable[AppPermissionAssignment]:
        self.permission_calls.append((environment_id, app_id))
        return [
            AppPermissionAssignment(
                id="assign-1", role_name="CanEdit", principal_type="User", display_name="User"
            )
        ]

    def set_app_owner(
        self, environment_id: str, app_id: str, payload: dict[str, object]
    ) -> OperationHandle:
        self.set_owner_calls.append((environment_id, app_id, payload))
        return OperationHandle("https://example/operations/app-owner", {})

    def list_environment_groups(self) -> list[dict[str, object]]:
        return [{"id": "group-1"}]

    def get_environment_group(self, group_id: str) -> dict[str, object]:
        return {"id": group_id}

    def create_environment_group(self, payload: dict[str, object]) -> dict[str, object]:
        return {"id": "group-created", **payload}

    def update_environment_group(self, group_id: str, payload: dict[str, object]) -> dict[str, object]:
        return {"id": group_id, **payload}

    def delete_environment_group(self, group_id: str) -> OperationHandle:
        return OperationHandle(f"https://example/groups/{group_id}/operations/delete", {})

    def apply_environment_group(self, group_id: str, environment_id: str) -> OperationHandle:
        self.apply_calls.append((group_id, environment_id))
        return OperationHandle("https://example/operations/apply", {})

    def revoke_environment_group(self, group_id: str, environment_id: str) -> OperationHandle:
        self.revoke_calls.append((group_id, environment_id))
        return OperationHandle("https://example/operations/revoke", {})


@pytest.fixture
def cli_app(monkeypatch: pytest.MonkeyPatch):
    app, module = load_cli_app(monkeypatch)
    monkeypatch.setattr(module, "PowerPlatformClient", StubPowerPlatformClient)
    monkeypatch.setattr("pacx.cli.power_platform.PowerPlatformClient", StubPowerPlatformClient)
    StubPowerPlatformClient.instances = []
    return app, StubPowerPlatformClient


def test_list_environments(cli_runner, cli_app) -> None:
    app, _ = cli_app
    result = cli_runner.invoke(
        app,
        ["env"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )
    assert result.exit_code == 0
    assert "env-1" in result.stdout
    assert "env-2" in result.stdout


def test_list_apps_and_flows(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result_apps = cli_runner.invoke(
        app,
        ["apps", "--environment-id", "ENV"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )
    assert result_apps.exit_code == 0
    assert "app-1" in result_apps.stdout
    assert "app-2" in result_apps.stdout

    result_flows = cli_runner.invoke(
        app,
        ["flows", "--environment-id", "ENV"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )
    assert result_flows.exit_code == 0
    assert "flow-1" in result_flows.stdout
    assert any(instance.apps_calls for instance in client_cls.instances)


def test_environment_copy_command(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result = cli_runner.invoke(
        app,
        ["env", "copy", "--environment-id", "ENV", "--payload", "{}"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert any(instance.copy_calls for instance in client_cls.instances)


def test_environment_group_apply(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result = cli_runner.invoke(
        app,
        ["env-group", "apply", "group-1", "--environment-id", "ENV"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert any(instance.apply_calls for instance in client_cls.instances)


def test_apps_versions_command(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result = cli_runner.invoke(
        app,
        [
            "apps",
            "versions",
            "app-1",
            "--environment-id",
            "ENV",
            "--top",
            "5",
            "--skiptoken",
            "cursor",
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert "ver-1" in result.stdout
    assert "nextLink" in result.stdout
    instance = client_cls.instances[-1]
    assert instance.version_calls
    env_id, app_id, params = instance.version_calls[0]
    assert env_id == "ENV"
    assert app_id == "app-1"
    assert params["top"] == 5
    assert params["skiptoken"] == "cursor"


def test_apps_restore_command(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result = cli_runner.invoke(
        app,
        [
            "apps",
            "restore",
            "app-1",
            "--environment-id",
            "ENV",
            "--version-id",
            "1.0",
            "--target-app-name",
            "Copy",
            "--make-new-app",
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert "App restore" in result.stdout
    instance = client_cls.instances[-1]
    assert instance.app_restore_calls
    env_id, app_id, payload = instance.app_restore_calls[0]
    assert env_id == "ENV"
    assert app_id == "app-1"
    assert payload["restoreVersionId"] == "1.0"
    assert payload["makeNewApp"] is True


def test_apps_publish_command(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result = cli_runner.invoke(
        app,
        [
            "apps",
            "publish",
            "app-1",
            "--environment-id",
            "ENV",
            "--version-id",
            "2.0",
            "--description",
            "Release",
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert "App publish" in result.stdout
    instance = client_cls.instances[-1]
    assert instance.publish_calls
    _, _, payload = instance.publish_calls[0]
    assert payload == {"versionId": "2.0", "description": "Release"}


def test_apps_share_command(cli_runner, cli_app) -> None:
    app, client_cls = cli_app
    payload = (
        '{"principals":[{"id":"user","principalType":"User","roleName":"CanEdit"}]}'
    )

    result = cli_runner.invoke(
        app,
        ["apps", "share", "app-1", "--environment-id", "ENV", "--payload", payload],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert "App share" in result.stdout
    instance = client_cls.instances[-1]
    assert instance.share_calls
    _, _, body = instance.share_calls[0]
    assert body["principals"][0]["id"] == "user"


def test_apps_revoke_share_command(cli_runner, cli_app) -> None:
    app, client_cls = cli_app
    payload = '{"principalIds":["user"]}'

    result = cli_runner.invoke(
        app,
        [
            "apps",
            "revoke-share",
            "app-1",
            "--environment-id",
            "ENV",
            "--payload",
            payload,
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert "App share revoke" in result.stdout
    instance = client_cls.instances[-1]
    assert instance.revoke_share_calls
    _, _, body = instance.revoke_share_calls[0]
    assert body["principalIds"] == ["user"]


def test_apps_permissions_command(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result = cli_runner.invoke(
        app,
        ["apps", "permissions", "app-1", "--environment-id", "ENV"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert "assign-1" in result.stdout
    instance = client_cls.instances[-1]
    assert instance.permission_calls
    env_id, app_id = instance.permission_calls[0]
    assert env_id == "ENV"
    assert app_id == "app-1"


def test_apps_set_owner_command(cli_runner, cli_app) -> None:
    app, client_cls = cli_app
    payload = (
        '{"owner":{"id":"user","principalType":"User","roleName":"CanEdit"}}'
    )

    result = cli_runner.invoke(
        app,
        ["apps", "set-owner", "app-1", "--environment-id", "ENV", "--payload", payload],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert "App owner update" in result.stdout
    instance = client_cls.instances[-1]
    assert instance.set_owner_calls
    _, _, body = instance.set_owner_calls[0]
    assert body["owner"]["id"] == "user"
