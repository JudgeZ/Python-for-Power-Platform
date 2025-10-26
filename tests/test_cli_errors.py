from __future__ import annotations

# ruff: noqa: S101
from typer.testing import CliRunner

import pacx.config as config_module
from pacx.cli import app
from pacx.errors import HttpError

runner = CliRunner()


def test_http_error_prints_friendly_message(monkeypatch):
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "dummy")

    class FakeClient:
        def list_environments(self):
            raise HttpError(500, "boom", details={"error": "bad"})

    monkeypatch.setattr("pacx.cli.PowerPlatformClient", lambda *args, **kwargs: FakeClient())

    result = runner.invoke(app, ["env"])
    output = result.stdout or result.stderr
    assert result.exit_code == 1
    assert "Error:" in output
    assert "HTTP 500" in output
    assert "bad" in output
    assert "Traceback" not in output


def test_missing_host_guidance(monkeypatch, tmp_path):
    monkeypatch.setenv("PACX_HOME", str(tmp_path))
    monkeypatch.setattr(config_module, "PACX_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(config_module, "CONFIG_PATH", str(tmp_path / "config.json"), raising=False)
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "token")

    result = runner.invoke(app, ["dv", "whoami"])
    assert result.exit_code != 0
    assert "Dataverse host" in result.stderr


def test_encrypted_config_without_key_shows_recovery_steps(monkeypatch, tmp_path):
    monkeypatch.setenv("PACX_HOME", str(tmp_path))
    monkeypatch.setattr(config_module, "PACX_DIR", str(tmp_path), raising=False)
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_PATH", str(config_path), raising=False)
    monkeypatch.setattr(config_module, "_cached_cipher", None, raising=False)
    monkeypatch.setattr(config_module, "_cached_cipher_key", None, raising=False)
    monkeypatch.delenv("PACX_CONFIG_ENCRYPTION_KEY", raising=False)

    config_path.write_text(
        """
{
  "default": "alpha",
  "profiles": {
    "alpha": {
      "name": "alpha",
      "access_token": "enc:dummytoken"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["profile", "list"])
    output = result.stdout or result.stderr

    assert result.exit_code == 1
    assert "PACX_CONFIG_ENCRYPTION_KEY" in output
    assert "ppx auth create NAME --flow" in output
