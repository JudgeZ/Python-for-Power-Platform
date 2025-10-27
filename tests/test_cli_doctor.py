from __future__ import annotations

import httpx
import typer
from typer.testing import CliRunner

from pacx.cli import app, doctor

runner = CliRunner()


def test_doctor_success(monkeypatch, respx_mock, token_getter):
    monkeypatch.setenv("PACX_ACCESS_TOKEN", token_getter())
    monkeypatch.setenv("DATAVERSE_HOST", "example.crm.dynamics.com")
    respx_mock.get("https://example.crm.dynamics.com/api/data/v9.2/WhoAmI()").mock(
        return_value=httpx.Response(200, json={"UserId": "user"})
    )

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Dataverse reachable" in result.stdout


def test_doctor_uses_profile_token(monkeypatch):
    monkeypatch.delenv("PACX_ACCESS_TOKEN", raising=False)

    calls: list[str] = []

    def fake_resolve(*_, **__):
        calls.append("resolve")
        return lambda: "profile-token"

    monkeypatch.setattr(doctor, "resolve_token_getter", fake_resolve)

    result = runner.invoke(app, ["doctor", "--no-check-dataverse"])

    assert result.exit_code == 0
    assert calls == ["resolve"]
    assert "Token acquisition successful" in result.stdout


def test_doctor_missing_token(monkeypatch):
    monkeypatch.delenv("PACX_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(
        doctor,
        "resolve_token_getter",
        lambda *_, **__: (_ for _ in ()).throw(typer.BadParameter("no token")),
    )

    result = runner.invoke(app, ["doctor"], catch_exceptions=False)
    assert result.exit_code == 1


def test_doctor_module_exposes_register():
    assert callable(doctor.register)
