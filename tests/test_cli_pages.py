from __future__ import annotations

from typer.testing import CliRunner

from pacx.cli import app
from pacx.clients.power_pages import PowerPagesClient

runner = CliRunner()


def test_cli_pages_upload_strategy_option(monkeypatch, tmp_path):
    monkeypatch.setenv("PACX_ACCESS_TOKEN", "dummy")
    monkeypatch.setenv("DATAVERSE_HOST", "example.crm.dynamics.com")

    captured: dict[str, tuple[str, str, str]] = {}

    def fake_upload(self, website_id: str, src_dir: str, *, strategy: str = "replace") -> None:  # type: ignore[override]
        captured["call"] = (website_id, src_dir, strategy)

    monkeypatch.setattr(PowerPagesClient, "upload_site", fake_upload, raising=True)

    result = runner.invoke(
        app,
        [
            "pages",
            "upload",
            "--website-id",
            "site",
            "--src",
            str(tmp_path),
            "--strategy",
            "merge",
        ],
    )

    assert result.exit_code == 0
    assert captured["call"] == ("site", str(tmp_path), "merge")
