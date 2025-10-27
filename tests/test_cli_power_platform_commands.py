from __future__ import annotations

import importlib
import sys
from collections.abc import Iterable

import pytest
import typer

from pacx.clients.power_platform import AppVersionPage, FlowRunPage, OperationHandle
from pacx.models.power_platform import (
    AppPermissionAssignment,
    AppVersion,
    CloudFlow,
    FlowRun,
    FlowRunDiagnostics,
)


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
    instances: list[StubPowerPlatformClient] = []

    def __init__(self, token_getter, api_version: str | None = None) -> None:
        self.token = token_getter()
        self.api_version = api_version
        self.apps_calls: list[str] = []
        self.flows_calls: list[str] = []
        self.flow_get_calls: list[tuple[str, str]] = []
        self.flow_update_calls: list[tuple[str, str, dict[str, object]]] = []
        self.flow_delete_calls: list[tuple[str, str]] = []
        self.flow_run_calls: list[tuple[str, str, dict[str, object]]] = []
        self.flow_run_list_calls: list[tuple[str, str, dict[str, object]]] = []
        self.flow_run_get_calls: list[tuple[str, str, str]] = []
        self.flow_run_cancel_calls: list[tuple[str, str, str]] = []
        self.flow_run_diag_calls: list[tuple[str, str, str]] = []
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

    def list_cloud_flows(self, environment_id: str, **_: object) -> Iterable[CloudFlow]:
        self.flows_calls.append(environment_id)
        return [
            CloudFlow(id="flow-1", name="flow-1", properties={"state": "Started"}),
            CloudFlow(id="flow-2", name="flow-2", properties={"state": "Stopped"}),
        ]

    def get_cloud_flow(self, environment_id: str, flow_id: str) -> CloudFlow:
        self.flow_get_calls.append((environment_id, flow_id))
        return CloudFlow(id=flow_id, name=f"Flow {flow_id}", properties={"state": "Stopped"})

    def update_cloud_flow_state(
        self, environment_id: str, flow_id: str, payload: dict[str, object]
    ) -> CloudFlow:
        self.flow_update_calls.append((environment_id, flow_id, payload))
        return CloudFlow(
            id=flow_id, name=f"Flow {flow_id}", properties={"state": payload.get("state")}
        )

    def delete_cloud_flow(self, environment_id: str, flow_id: str) -> None:
        self.flow_delete_calls.append((environment_id, flow_id))

    def copy_environment(self, environment_id: str, payload: dict[str, object]) -> OperationHandle:
        self.copy_calls.append((environment_id, payload))
        return OperationHandle("https://example/operations/copy", {"status": "Accepted"})

    def reset_environment(self, environment_id: str, payload: dict[str, object]) -> OperationHandle:
        self.reset_calls.append((environment_id, payload))
        return OperationHandle("https://example/operations/reset", {})

    def backup_environment(
        self, environment_id: str, payload: dict[str, object]
    ) -> OperationHandle:
        self.backup_calls.append((environment_id, payload))
        return OperationHandle("https://example/operations/backup", {})

    def restore_environment(
        self, environment_id: str, payload: dict[str, object]
    ) -> OperationHandle:
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
        return AppVersionPage(versions, next_link="next", continuation_token="token")  # noqa: S106

    def restore_app(
        self, environment_id: str, app_id: str, payload: dict[str, object]
    ) -> OperationHandle:
        self.app_restore_calls.append((environment_id, app_id, payload))
        return OperationHandle("https://example/operations/app-restore", {})

    def publish_app(
        self, environment_id: str, app_id: str, payload: dict[str, object]
    ) -> OperationHandle:
        self.publish_calls.append((environment_id, app_id, payload))
        return OperationHandle("https://example/operations/app-publish", {})

    def share_app(
        self, environment_id: str, app_id: str, payload: dict[str, object]
    ) -> OperationHandle:
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

    def trigger_cloud_flow_run(
        self, environment_id: str, flow_id: str, payload: dict[str, object]
    ) -> FlowRun:
        self.flow_run_calls.append((environment_id, flow_id, payload))
        return FlowRun(id="run-1", name="run-1", status="Running")

    def list_cloud_flow_runs(
        self,
        environment_id: str,
        flow_id: str,
        *,
        status: str | None = None,
        trigger_name: str | None = None,
        top: int | None = None,
        continuation_token: str | None = None,
    ) -> FlowRunPage:
        params: dict[str, object] = {}
        if status:
            params["status"] = status
        if trigger_name:
            params["triggerName"] = trigger_name
        if top is not None:
            params["top"] = top
        if continuation_token:
            params["continuationToken"] = continuation_token
        self.flow_run_list_calls.append((environment_id, flow_id, params))
        runs = [FlowRun(id="run-1", name="run-1", status="Succeeded")]
        return FlowRunPage(runs, continuation_token="token-2")  # noqa: S106

    def get_cloud_flow_run(self, environment_id: str, flow_id: str, run_name: str) -> FlowRun:
        self.flow_run_get_calls.append((environment_id, flow_id, run_name))
        return FlowRun(id=run_name, name=run_name, status="Succeeded")

    def cancel_cloud_flow_run(self, environment_id: str, flow_id: str, run_name: str) -> None:
        self.flow_run_cancel_calls.append((environment_id, flow_id, run_name))

    def get_cloud_flow_run_diagnostics(
        self, environment_id: str, flow_id: str, run_name: str
    ) -> FlowRunDiagnostics:
        self.flow_run_diag_calls.append((environment_id, flow_id, run_name))
        return FlowRunDiagnostics(
            run_name=run_name,
            issues=[{"actionName": "Act", "code": "ERR", "message": "Issue"}],
        )

    def list_environment_groups(self) -> list[dict[str, object]]:
        return [{"id": "group-1"}]

    def get_environment_group(self, group_id: str) -> dict[str, object]:
        return {"id": group_id}

    def create_environment_group(self, payload: dict[str, object]) -> dict[str, object]:
        return {"id": "group-created", **payload}

    def update_environment_group(
        self, group_id: str, payload: dict[str, object]
    ) -> dict[str, object]:
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
        ["power", "flows", "list", "--environment-id", "ENV", "--owner-id", "owner"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )
    assert result_flows.exit_code == 0
    assert "flow-1" in result_flows.stdout
    assert "state=Started" in result_flows.stdout
    instance = client_cls.instances[-1]
    assert instance.flows_calls


def test_environment_copy_command(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result = cli_runner.invoke(
        app,
        ["env", "copy", "--environment-id", "ENV", "--payload", "{}"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert any(instance.copy_calls for instance in client_cls.instances)


def test_power_flows_get_update_delete(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result_get = cli_runner.invoke(
        app,
        ["power", "flows", "get", "flow-1", "--environment-id", "ENV"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )
    assert result_get.exit_code == 0
    assert "Flow flow-1" in result_get.stdout
    instance_get = client_cls.instances[-1]
    assert instance_get.flow_get_calls[-1] == ("ENV", "flow-1")

    result_update = cli_runner.invoke(
        app,
        [
            "power",
            "flows",
            "update",
            "flow-1",
            "--environment-id",
            "ENV",
            "--state",
            "stopped",
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )
    assert result_update.exit_code == 0
    assert "state=Stopped" in result_update.stdout
    instance_update = client_cls.instances[-1]
    assert instance_update.flow_update_calls[-1][2]["state"] == "Stopped"

    result_delete = cli_runner.invoke(
        app,
        ["power", "flows", "delete", "flow-1", "--environment-id", "ENV"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )
    assert result_delete.exit_code == 0
    instance_delete = client_cls.instances[-1]
    assert instance_delete.flow_delete_calls[-1] == ("ENV", "flow-1")


def test_power_flows_run(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result = cli_runner.invoke(
        app,
        [
            "power",
            "flows",
            "run",
            "flow-1",
            "--environment-id",
            "ENV",
            "--trigger-name",
            "manual",
            "--inputs",
            '{"foo":"bar"}',
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert "Cloud flow run triggered" in result.stdout
    instance = client_cls.instances[-1]
    assert instance.flow_run_calls
    env_id, flow_id, payload = instance.flow_run_calls[-1]
    assert env_id == "ENV"
    assert flow_id == "flow-1"
    assert payload["inputs"]["foo"] == "bar"


def test_power_flows_run_handles_empty_response(
    cli_runner, cli_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, client_cls = cli_app

    def empty_trigger(
        self, environment_id: str, flow_id: str, payload: dict[str, object]
    ) -> FlowRun:
        self.flow_run_calls.append((environment_id, flow_id, payload))
        return FlowRun()

    monkeypatch.setattr(client_cls, "trigger_cloud_flow_run", empty_trigger, raising=False)

    result = cli_runner.invoke(
        app,
        [
            "power",
            "flows",
            "run",
            "flow-1",
            "--environment-id",
            "ENV",
            "--trigger-name",
            "manual",
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )

    assert result.exit_code == 0
    assert "Cloud flow run triggered" in result.stdout
    assert "status=" not in result.stdout


def test_power_runs_commands(cli_runner, cli_app) -> None:
    app, client_cls = cli_app

    result_list = cli_runner.invoke(
        app,
        [
            "power",
            "runs",
            "list",
            "flow-1",
            "--environment-id",
            "ENV",
            "--status",
            "Succeeded",
            "--continuation-token",
            "token-1",
            "--top",
            "5",
        ],
        env={"PACX_ACCESS_TOKEN": "token"},
    )
    assert result_list.exit_code == 0
    assert "Continuation token" in result_list.stdout
    instance_list = client_cls.instances[-1]
    env_id, flow_id, params = instance_list.flow_run_list_calls[-1]
    assert env_id == "ENV"
    assert flow_id == "flow-1"
    assert params["status"] == "Succeeded"
    assert params["continuationToken"] == "token-1"

    result_get = cli_runner.invoke(
        app,
        ["power", "runs", "get", "flow-1", "run-1", "--environment-id", "ENV"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )
    assert result_get.exit_code == 0
    assert "Run status" in result_get.stdout
    instance_get = client_cls.instances[-1]
    assert instance_get.flow_run_get_calls[-1] == ("ENV", "flow-1", "run-1")

    result_cancel = cli_runner.invoke(
        app,
        ["power", "runs", "cancel", "flow-1", "run-1", "--environment-id", "ENV"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )
    assert result_cancel.exit_code == 0
    instance_cancel = client_cls.instances[-1]
    assert instance_cancel.flow_run_cancel_calls[-1] == ("ENV", "flow-1", "run-1")

    result_diag = cli_runner.invoke(
        app,
        ["power", "runs", "diagnostics", "flow-1", "run-1", "--environment-id", "ENV"],
        env={"PACX_ACCESS_TOKEN": "token"},
    )
    assert result_diag.exit_code == 0
    assert "ERR" in result_diag.stdout
    instance_diag = client_cls.instances[-1]
    assert instance_diag.flow_run_diag_calls[-1] == ("ENV", "flow-1", "run-1")


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
    payload = '{"principals":[{"id":"user","principalType":"User","roleName":"CanEdit"}]}'

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
    payload = '{"owner":{"id":"user","principalType":"User","roleName":"CanEdit"}}'

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
