from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
import typer
from typer.testing import CliRunner


class StubCoeClient:
    instances: list[StubCoeClient] = []

    def __init__(self, token_getter: Callable[[], str]) -> None:  # noqa: D401 - mirrors other stubs
        self.token = token_getter()
        self.inventory_calls: list[dict[str, object]] = []
        self.makers_calls: list[dict[str, object]] = []
        self.metrics_calls: list[dict[str, object]] = []
        StubCoeClient.instances.append(self)

    def inventory(self, *, environment_id: str | None = None) -> list[dict[str, object]]:
        self.inventory_calls.append({"environment_id": environment_id})
        return [
            {"type": "app", "id": "app-1", "name": "App One"},
            {"type": "flow", "id": "flow-1", "name": "Flow One"},
        ]

    def makers(self, *, environment_id: str | None = None) -> list[dict[str, object]]:
        self.makers_calls.append({"environment_id": environment_id})
        return [
            {"id": "user-1", "displayName": "User One"},
            {"id": "user-2", "displayName": "User Two"},
        ]

    def metrics(self, *, environment_id: str | None = None) -> dict[str, int]:
        self.metrics_calls.append({"environment_id": environment_id})
        return {"apps": 2, "flows": 1, "makers": 2}


def load_cli_app(monkeypatch: pytest.MonkeyPatch) -> typer.Typer:
    # Reload CLI to ensure our patching is visible
    for name in [m for m in list(sys.modules) if m.startswith("pacx.cli")]:
        sys.modules.pop(name)
    module = importlib.import_module("pacx.cli")
    monkeypatch.setattr("pacx.cli.coe.CoeClient", StubCoeClient)
    monkeypatch.setattr(module.coe, "CoeClient", StubCoeClient)
    StubCoeClient.instances = []
    return cast(typer.Typer, module.app)


@pytest.fixture
def cli_app(monkeypatch: pytest.MonkeyPatch) -> typer.Typer:
    return load_cli_app(monkeypatch)


runner = CliRunner()


def test_inventory_lists_value_json(cli_app: typer.Typer) -> None:
    result = runner.invoke(cli_app, ["coe", "inventory"])
    assert result.exit_code == 0
    assert '"value"' in result.stdout
    assert "App One" in result.stdout and "Flow One" in result.stdout


def test_makers_lists_value_json(cli_app: typer.Typer) -> None:
    result = runner.invoke(cli_app, ["coe", "makers", "-e", "ENV1"])
    assert result.exit_code == 0
    assert '"value"' in result.stdout
    assert "User One" in result.stdout
    client = StubCoeClient.instances[-1]
    assert client.makers_calls[-1] == {"environment_id": "ENV1"}


def test_metrics_prints_json(cli_app: typer.Typer) -> None:
    result = runner.invoke(cli_app, ["coe", "metrics"])
    assert result.exit_code == 0
    assert '"apps"' in result.stdout and '"makers"' in result.stdout


def test_export_json_wraps_value_for_lists(cli_app: typer.Typer, tmp_path: Path) -> None:
    path = tmp_path / "out.json"
    result = runner.invoke(
        cli_app, ["coe", "export", "-r", "inventory", "-o", str(path), "-f", "json"]
    )
    assert result.exit_code == 0
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    assert isinstance(payload.get("value"), list)
    assert payload["value"][0]["name"] == "App One"


def test_export_csv_writes_rows(cli_app: typer.Typer, tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    result = runner.invoke(
        cli_app, ["coe", "export", "-r", "inventory", "-o", str(path), "-f", "csv"]
    )
    assert result.exit_code == 0
    text = path.read_text(encoding="utf-8")
    assert "id" in text and "name" in text and "type" in text
    assert "app-1" in text and "flow-1" in text


def test_export_csv_metrics_key_value(cli_app: typer.Typer, tmp_path: Path) -> None:
    path = tmp_path / "metrics.csv"
    result = runner.invoke(
        cli_app, ["coe", "export", "-r", "metrics", "-o", str(path), "-f", "csv"]
    )
    assert result.exit_code == 0
    rows = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[0] == "key,value"
    assert any(row.startswith("apps,") for row in rows[1:])
