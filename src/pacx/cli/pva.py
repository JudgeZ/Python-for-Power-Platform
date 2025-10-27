from __future__ import annotations

import json
from importlib import import_module
from typing import Any, cast

import typer
from rich import print

from ..cli_utils import resolve_environment_id_from_context
from ..clients.pva import DEFAULT_API_VERSION, OperationHandle
from ..clients.pva import PVAClient as _DefaultPVAClient
from .common import get_token_getter, handle_cli_errors

app = typer.Typer(help="Manage Power Virtual Agents bots.")
bots_app = typer.Typer(help="Manage bots in an environment.", invoke_without_command=True)
channels_app = typer.Typer(help="Manage bot channel configurations.")
quarantine_app = typer.Typer(help="Manage bot quarantine state.")

app.add_typer(bots_app, name="bots")
bots_app.add_typer(channels_app, name="channels")
bots_app.add_typer(quarantine_app, name="quarantine")


def _resolve_client_class() -> type[_DefaultPVAClient]:
    try:
        module = import_module("pacx.cli")
    except Exception:  # pragma: no cover - defensive
        return _DefaultPVAClient
    client_cls = getattr(module, "PVAClient", None)
    if client_cls is None:
        return _DefaultPVAClient
    return cast(type[_DefaultPVAClient], client_cls)


def _build_client(
    ctx: typer.Context,
    *,
    api_version: str | None = None,
) -> _DefaultPVAClient:
    token_getter = get_token_getter(ctx)
    client_cls = _resolve_client_class()
    if api_version is None:
        return client_cls(token_getter)
    return client_cls(token_getter, api_version=api_version)


def _ensure_api_version(ctx: typer.Context, override: str | None) -> str:
    data = ctx.ensure_object(dict)
    if override:
        data["pva_api_version"] = override
        return override
    return cast(str, data.get("pva_api_version", DEFAULT_API_VERSION))


def _resolve_environment(ctx: typer.Context, option_value: str | None) -> str:
    data = ctx.ensure_object(dict)
    if option_value:
        environment = resolve_environment_id_from_context(ctx, option_value)
        data["pva_environment_id"] = environment
        return environment
    cached = data.get("pva_environment_id")
    if isinstance(cached, str) and cached:
        return cached
    environment = resolve_environment_id_from_context(ctx, None)
    data["pva_environment_id"] = environment
    return environment


def _parse_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [segment.strip() for segment in value.split(",") if segment.strip()]
    return items or None


def _parse_locale_mapping(value: str | None) -> dict[str, str] | None:
    if not value:
        return None
    result: dict[str, str] = {}
    for segment in value.split(","):
        if not segment.strip():
            continue
        if "=" not in segment:
            raise typer.BadParameter(
                "Locale mappings must use the form source=target, separated by commas."
            )
        source, target = segment.split("=", 1)
        source = source.strip()
        target = target.strip()
        if not source or not target:
            raise typer.BadParameter("Locale mapping keys and values must be non-empty.")
        result[source] = target
    return result or None


def _parse_json_option(value: str | None) -> dict[str, Any] | None:
    if value in (None, ""):
        return None
    try:
        value_str = cast(str, value)
        data = json.loads(value_str)
    except json.JSONDecodeError as exc:  # pragma: no cover - option validation
        raise typer.BadParameter(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(data, dict):
        raise typer.BadParameter("Payload must be a JSON object.")
    return cast(dict[str, Any], data)


def _compact_dict(mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if value is not None}


def _handle_operation_result(
    action: str,
    handle: OperationHandle,
    *,
    client: _DefaultPVAClient,
    poll: bool,
    interval: float,
    timeout: float,
) -> None:
    if poll and handle.operation_location:
        status = client.wait_for_operation(
            handle.operation_location, interval=interval, timeout=timeout
        )
        print(f"[green]{action} completed[/green] status={status.get('status')}")
        if status:
            print(json.dumps(status, indent=2, sort_keys=True))
        return

    message = f"[green]{action} accepted[/green]"
    if handle.operation_location:
        message += f" operation={handle.operation_id}"
    print(message)
    if handle.metadata:
        print(json.dumps(handle.metadata, indent=2, sort_keys=True))


@bots_app.callback(invoke_without_command=True)
@handle_cli_errors
def bots_root(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(
        None, help="Environment ID (defaults to the active profile)."
    ),
    api_version: str = typer.Option(
        DEFAULT_API_VERSION,
        help="Power Virtual Agents API version (defaults to 2022-03-01-preview).",
    ),
) -> None:
    ctx.ensure_object(dict)["pva_api_version"] = api_version
    _resolve_environment(ctx, environment_id)
    if ctx.invoked_subcommand is None:
        list_bots(ctx, environment_id=environment_id, api_version=api_version)


@bots_app.command("list")
@handle_cli_errors
def list_bots(
    ctx: typer.Context,
    environment_id: str | None = typer.Option(
        None, help="Environment ID (defaults to the active profile)."
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Virtual Agents API version (defaults to 2022-03-01-preview).",
    ),
    top: int | None = typer.Option(None, help="Optional maximum number of bots to return."),
) -> None:
    """List bots in an environment."""

    version = _ensure_api_version(ctx, api_version)
    env_id = _resolve_environment(ctx, environment_id)
    client = _build_client(ctx, api_version=version)
    bots = client.list_bots(env_id, top=top)
    if not bots:
        print("No bots found.")
        return
    for bot in bots:
        display = bot.display_name or bot.name
        print(f"[bold]{display}[/bold] id={bot.id} locale={bot.locale} status={bot.status}")


@bots_app.command("get")
@handle_cli_errors
def get_bot(
    ctx: typer.Context,
    bot_id: str = typer.Option(..., help="Bot identifier."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID (defaults to the active profile)."
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Virtual Agents API version (defaults to 2022-03-01-preview).",
    ),
) -> None:
    """Fetch metadata for a specific bot."""

    version = _ensure_api_version(ctx, api_version)
    env_id = _resolve_environment(ctx, environment_id)
    client = _build_client(ctx, api_version=version)
    bot = client.get_bot(env_id, bot_id)
    print(json.dumps(bot.model_dump(by_alias=True, exclude_none=True), indent=2, sort_keys=True))


@bots_app.command("publish")
@handle_cli_errors
def publish_bot_command(
    ctx: typer.Context,
    bot_id: str = typer.Option(..., help="Bot identifier."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID (defaults to the active profile)."
    ),
    comment: str | None = typer.Option(None, help="Optional publish comment."),
    locale: str | None = typer.Option(None, help="Locale to publish."),
    target_environment_id: str | None = typer.Option(
        None, help="Target environment ID when publishing to a managed environment."
    ),
    channels: str | None = typer.Option(
        None, help="Comma-separated channel identifiers to include in the publish."
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Virtual Agents API version (defaults to 2022-03-01-preview).",
    ),
    poll: bool = typer.Option(
        False,
        "--poll/--no-poll",
        help="Poll the publish operation until it completes.",
    ),
    poll_interval: float = typer.Option(2.0, help="Seconds between poll attempts."),
    poll_timeout: float = typer.Option(600.0, help="Maximum seconds to wait when polling."),
) -> None:
    """Publish a bot."""

    version = _ensure_api_version(ctx, api_version)
    env_id = _resolve_environment(ctx, environment_id)
    client = _build_client(ctx, api_version=version)
    payload = _compact_dict(
        {
            "comment": comment,
            "locale": locale,
            "targetEnvironmentId": target_environment_id,
            "includedChannels": _parse_csv(channels),
        }
    )
    handle = client.publish_bot(env_id, bot_id, payload)
    _handle_operation_result(
        "Publish", handle, client=client, poll=poll, interval=poll_interval, timeout=poll_timeout
    )


@bots_app.command("unpublish")
@handle_cli_errors
def unpublish_bot_command(
    ctx: typer.Context,
    bot_id: str = typer.Option(..., help="Bot identifier."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID (defaults to the active profile)."
    ),
    comment: str | None = typer.Option(None, help="Optional unpublish reason."),
    channels: str | None = typer.Option(
        None, help="Comma-separated channel identifiers to unpublish."
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Virtual Agents API version (defaults to 2022-03-01-preview).",
    ),
    poll: bool = typer.Option(
        False,
        "--poll/--no-poll",
        help="Poll the unpublish operation until it completes.",
    ),
    poll_interval: float = typer.Option(2.0, help="Seconds between poll attempts."),
    poll_timeout: float = typer.Option(600.0, help="Maximum seconds to wait when polling."),
) -> None:
    """Unpublish a bot."""

    version = _ensure_api_version(ctx, api_version)
    env_id = _resolve_environment(ctx, environment_id)
    client = _build_client(ctx, api_version=version)
    payload = _compact_dict({"comment": comment, "channels": _parse_csv(channels)})
    handle = client.unpublish_bot(env_id, bot_id, payload)
    _handle_operation_result(
        "Unpublish",
        handle,
        client=client,
        poll=poll,
        interval=poll_interval,
        timeout=poll_timeout,
    )


@bots_app.command("export")
@handle_cli_errors
def export_bot_command(
    ctx: typer.Context,
    bot_id: str = typer.Option(..., help="Bot identifier."),
    package_format: str = typer.Option(..., help="Export package format."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID (defaults to the active profile)."
    ),
    include_analytics: bool | None = typer.Option(
        None, "--include-analytics/--no-include-analytics", help="Include analytics telemetry."
    ),
    include_secrets: bool | None = typer.Option(
        None, "--include-secrets/--no-include-secrets", help="Include secrets in the package."
    ),
    storage_url: str | None = typer.Option(
        None, help="Storage destination URL (for SAS delivery)."
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Virtual Agents API version (defaults to 2022-03-01-preview).",
    ),
    poll: bool = typer.Option(
        False,
        "--poll/--no-poll",
        help="Poll the export operation until it completes.",
    ),
    poll_interval: float = typer.Option(2.0, help="Seconds between poll attempts."),
    poll_timeout: float = typer.Option(600.0, help="Maximum seconds to wait when polling."),
) -> None:
    """Export a bot package."""

    version = _ensure_api_version(ctx, api_version)
    env_id = _resolve_environment(ctx, environment_id)
    client = _build_client(ctx, api_version=version)
    payload = _compact_dict(
        {
            "packageFormat": package_format,
            "includeAnalytics": include_analytics,
            "includeSecrets": include_secrets,
            "storageUrl": storage_url,
        }
    )
    handle = client.export_bot_package(env_id, bot_id, payload)
    _handle_operation_result(
        "Export",
        handle,
        client=client,
        poll=poll,
        interval=poll_interval,
        timeout=poll_timeout,
    )


@bots_app.command("import")
@handle_cli_errors
def import_bot_command(
    ctx: typer.Context,
    bot_id: str = typer.Option(..., help="Bot identifier."),
    package_url: str = typer.Option(..., help="URL of the bot package to import."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID (defaults to the active profile)."
    ),
    overwrite_existing_resources: bool | None = typer.Option(
        None, "--overwrite/--no-overwrite", help="Overwrite existing resources if present."
    ),
    publish_on_completion: bool | None = typer.Option(
        None,
        "--publish-on-completion/--no-publish-on-completion",
        help="Publish when import finishes.",
    ),
    locale_mappings: str | None = typer.Option(
        None, help="Locale remapping using source=target pairs separated by commas."
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Virtual Agents API version (defaults to 2022-03-01-preview).",
    ),
    poll: bool = typer.Option(
        False,
        "--poll/--no-poll",
        help="Poll the import operation until it completes.",
    ),
    poll_interval: float = typer.Option(2.0, help="Seconds between poll attempts."),
    poll_timeout: float = typer.Option(600.0, help="Maximum seconds to wait when polling."),
) -> None:
    """Import a bot package."""

    version = _ensure_api_version(ctx, api_version)
    env_id = _resolve_environment(ctx, environment_id)
    client = _build_client(ctx, api_version=version)
    payload = _compact_dict(
        {
            "packageUrl": package_url,
            "overwriteExistingResources": overwrite_existing_resources,
            "publishOnCompletion": publish_on_completion,
            "localeMappings": _parse_locale_mapping(locale_mappings),
        }
    )
    handle = client.import_bot_package(env_id, bot_id, payload)
    _handle_operation_result(
        "Import",
        handle,
        client=client,
        poll=poll,
        interval=poll_interval,
        timeout=poll_timeout,
    )


@channels_app.command("list")
@handle_cli_errors
def list_channels(
    ctx: typer.Context,
    bot_id: str = typer.Option(..., help="Bot identifier."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID (defaults to the active profile)."
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Virtual Agents API version (defaults to 2022-03-01-preview).",
    ),
) -> None:
    """List channel configurations for a bot."""

    version = _ensure_api_version(ctx, api_version)
    env_id = _resolve_environment(ctx, environment_id)
    client = _build_client(ctx, api_version=version)
    channels = client.list_channels(env_id, bot_id)
    if not channels:
        print("No channels configured.")
        return
    for channel in channels:
        print(
            f"[bold]{channel.channel_type}[/bold] id={channel.id} status={channel.status} enabled={channel.configuration.get('isEnabled')}"
        )


@channels_app.command("get")
@handle_cli_errors
def get_channel(
    ctx: typer.Context,
    bot_id: str = typer.Option(..., help="Bot identifier."),
    channel_id: str = typer.Option(..., help="Channel identifier."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID (defaults to the active profile)."
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Virtual Agents API version (defaults to 2022-03-01-preview).",
    ),
) -> None:
    """Retrieve a specific channel configuration."""

    version = _ensure_api_version(ctx, api_version)
    env_id = _resolve_environment(ctx, environment_id)
    client = _build_client(ctx, api_version=version)
    channel = client.get_channel(env_id, bot_id, channel_id)
    print(
        json.dumps(channel.model_dump(by_alias=True, exclude_none=True), indent=2, sort_keys=True)
    )


@channels_app.command("enable")
@handle_cli_errors
def enable_channel(
    ctx: typer.Context,
    bot_id: str = typer.Option(..., help="Bot identifier."),
    channel_type: str = typer.Option(..., help="Channel type to enable."),
    configuration: str | None = typer.Option(None, help="Channel configuration as a JSON object."),
    is_enabled: bool | None = typer.Option(
        None, "--enable/--disable", help="Explicitly set the enabled state."
    ),
    environment_id: str | None = typer.Option(
        None, help="Environment ID (defaults to the active profile)."
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Virtual Agents API version (defaults to 2022-03-01-preview).",
    ),
    poll: bool = typer.Option(
        False,
        "--poll/--no-poll",
        help="Poll the channel operation until it completes.",
    ),
    poll_interval: float = typer.Option(2.0, help="Seconds between poll attempts."),
    poll_timeout: float = typer.Option(600.0, help="Maximum seconds to wait when polling."),
) -> None:
    """Enable a channel configuration."""

    version = _ensure_api_version(ctx, api_version)
    env_id = _resolve_environment(ctx, environment_id)
    client = _build_client(ctx, api_version=version)
    payload = _compact_dict(
        {
            "channelType": channel_type,
            "configuration": _parse_json_option(configuration),
            "isEnabled": is_enabled,
        }
    )
    handle = client.create_channel(env_id, bot_id, payload)
    _handle_operation_result(
        "Enable channel",
        handle,
        client=client,
        poll=poll,
        interval=poll_interval,
        timeout=poll_timeout,
    )


@channels_app.command("update")
@handle_cli_errors
def update_channel(
    ctx: typer.Context,
    bot_id: str = typer.Option(..., help="Bot identifier."),
    channel_id: str = typer.Option(..., help="Channel identifier."),
    channel_type: str = typer.Option(..., help="Channel type."),
    configuration: str | None = typer.Option(
        None, help="Updated channel configuration as a JSON object."
    ),
    is_enabled: bool | None = typer.Option(
        None, "--enable/--disable", help="Explicitly set the enabled state."
    ),
    environment_id: str | None = typer.Option(
        None, help="Environment ID (defaults to the active profile)."
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Virtual Agents API version (defaults to 2022-03-01-preview).",
    ),
    poll: bool = typer.Option(
        False,
        "--poll/--no-poll",
        help="Poll the update operation until it completes.",
    ),
    poll_interval: float = typer.Option(2.0, help="Seconds between poll attempts."),
    poll_timeout: float = typer.Option(600.0, help="Maximum seconds to wait when polling."),
) -> None:
    """Update a channel configuration."""

    version = _ensure_api_version(ctx, api_version)
    env_id = _resolve_environment(ctx, environment_id)
    client = _build_client(ctx, api_version=version)
    payload = _compact_dict(
        {
            "channelType": channel_type,
            "configuration": _parse_json_option(configuration),
            "isEnabled": is_enabled,
        }
    )
    handle = client.update_channel(env_id, bot_id, channel_id, payload)
    _handle_operation_result(
        "Update channel",
        handle,
        client=client,
        poll=poll,
        interval=poll_interval,
        timeout=poll_timeout,
    )


@channels_app.command("disable")
@handle_cli_errors
def disable_channel(
    ctx: typer.Context,
    bot_id: str = typer.Option(..., help="Bot identifier."),
    channel_id: str = typer.Option(..., help="Channel identifier."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID (defaults to the active profile)."
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Virtual Agents API version (defaults to 2022-03-01-preview).",
    ),
    poll: bool = typer.Option(
        False,
        "--poll/--no-poll",
        help="Poll the disable operation until it completes.",
    ),
    poll_interval: float = typer.Option(2.0, help="Seconds between poll attempts."),
    poll_timeout: float = typer.Option(600.0, help="Maximum seconds to wait when polling."),
) -> None:
    """Disable a channel configuration."""

    version = _ensure_api_version(ctx, api_version)
    env_id = _resolve_environment(ctx, environment_id)
    client = _build_client(ctx, api_version=version)
    handle = client.delete_channel(env_id, bot_id, channel_id)
    _handle_operation_result(
        "Disable channel",
        handle,
        client=client,
        poll=poll,
        interval=poll_interval,
        timeout=poll_timeout,
    )


@quarantine_app.command("status")
@handle_cli_errors
def quarantine_status(
    ctx: typer.Context,
    bot_id: str = typer.Option(..., help="Bot identifier."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID (defaults to the active profile)."
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Virtual Agents API version (defaults to 2022-03-01-preview).",
    ),
) -> None:
    """Show the current quarantine status for a bot."""

    version = _ensure_api_version(ctx, api_version)
    env_id = _resolve_environment(ctx, environment_id)
    client = _build_client(ctx, api_version=version)
    status = client.get_quarantine_status(env_id, bot_id)
    if status:
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        print("No quarantine status available.")


@quarantine_app.command("set")
@handle_cli_errors
def quarantine_set(
    ctx: typer.Context,
    bot_id: str = typer.Option(..., help="Bot identifier."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID (defaults to the active profile)."
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Virtual Agents API version (defaults to 2022-03-01-preview).",
    ),
    poll: bool = typer.Option(
        False,
        "--poll/--no-poll",
        help="Poll the quarantine operation until it completes.",
    ),
    poll_interval: float = typer.Option(2.0, help="Seconds between poll attempts."),
    poll_timeout: float = typer.Option(600.0, help="Maximum seconds to wait when polling."),
) -> None:
    """Mark a bot as quarantined."""

    version = _ensure_api_version(ctx, api_version)
    env_id = _resolve_environment(ctx, environment_id)
    client = _build_client(ctx, api_version=version)
    handle = client.set_quarantined(env_id, bot_id)
    _handle_operation_result(
        "Set quarantine",
        handle,
        client=client,
        poll=poll,
        interval=poll_interval,
        timeout=poll_timeout,
    )


@quarantine_app.command("unset")
@handle_cli_errors
def quarantine_unset(
    ctx: typer.Context,
    bot_id: str = typer.Option(..., help="Bot identifier."),
    environment_id: str | None = typer.Option(
        None, help="Environment ID (defaults to the active profile)."
    ),
    api_version: str | None = typer.Option(
        None,
        help="Power Virtual Agents API version (defaults to 2022-03-01-preview).",
    ),
    poll: bool = typer.Option(
        False,
        "--poll/--no-poll",
        help="Poll the operation until it completes.",
    ),
    poll_interval: float = typer.Option(2.0, help="Seconds between poll attempts."),
    poll_timeout: float = typer.Option(600.0, help="Maximum seconds to wait when polling."),
) -> None:
    """Remove quarantine from a bot."""

    version = _ensure_api_version(ctx, api_version)
    env_id = _resolve_environment(ctx, environment_id)
    client = _build_client(ctx, api_version=version)
    handle = client.set_unquarantined(env_id, bot_id)
    _handle_operation_result(
        "Unset quarantine",
        handle,
        client=client,
        poll=poll,
        interval=poll_interval,
        timeout=poll_timeout,
    )


__all__ = [
    "app",
    "bots_app",
    "channels_app",
    "quarantine_app",
    "PVAClient",
]

PVAClient = _DefaultPVAClient
