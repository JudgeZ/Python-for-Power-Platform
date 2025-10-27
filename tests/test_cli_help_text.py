from __future__ import annotations

from typer.testing import CliRunner

from pacx.cli import app

runner = CliRunner()


def test_dataverse_list_help_highlights_docstring_and_options() -> None:
    result = runner.invoke(app, ["dv", "list", "--help"])
    assert result.exit_code == 0
    output = result.stdout
    assert "List table rows with optional OData query parameters" in output
    assert "--select" in output and "Comma-separated column logical names" in output
    assert "--host" in output and "defaults to profile or DATAVERSE_HOST" in output


def test_connector_push_help_mentions_openapi_details() -> None:
    result = runner.invoke(app, ["connector", "push", "--help"])
    assert result.exit_code == 0
    output = result.stdout
    assert "Create or update a connector from an OpenAPI document" in output
    assert "--openapi" in output and "YAML or JSON" in output
    assert "--display-name" in output and "Optional friendly name" in output


def test_pages_download_help_describes_binary_options() -> None:
    result = runner.invoke(app, ["pages", "download", "--help"])
    assert result.exit_code == 0
    output = result.stdout
    assert "Download a Power Pages site to a local folder" in output
    assert "--binaries" in output and "default binary provider" in output
    assert "--provider-options" in output and "custom binary providers" in output


def test_solution_command_help_lists_lifecycle_summary() -> None:
    result = runner.invoke(app, ["solution", "--help"])
    assert result.exit_code == 0
    output = result.stdout
    assert "Perform solution lifecycle operations" in output
    assert "--host" in output and "defaults to profile or DATAVERSE_HOST" in output
    assert "--managed" in output and "default: unmanaged" in output


def test_profile_list_help_mentions_default_highlight() -> None:
    result = runner.invoke(app, ["profile", "list", "--help"])
    assert result.exit_code == 0
    assert "Show all saved profiles" in result.stdout


def test_auth_use_help_mentions_default_profile() -> None:
    result = runner.invoke(app, ["auth", "use", "--help"])
    assert result.exit_code == 0
    assert "Set a profile as the default" in result.stdout


def test_auth_roles_help_mentions_scopes() -> None:
    result = runner.invoke(app, ["auth", "roles", "--help"])
    assert result.exit_code == 0
    output = result.stdout
    assert "Manage RBAC role definitions" in output
    assert "Authorization.RBAC" in output


def test_auth_assignments_create_help_mentions_manage_scope() -> None:
    result = runner.invoke(app, ["auth", "assignments", "create", "--help"])
    assert result.exit_code == 0
    output = result.stdout
    assert "Requires Authorization.RBAC.Manage" in output
    assert "--principal-id" in output and "Principal object ID" in output
