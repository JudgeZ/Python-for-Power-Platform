"""Utilities for recording and verifying filesystem event replays.

The developer experience around reproducing filesystem bugs relies on
capturing deterministic sequences of events and replaying them later.  The
helper functions in this module keep the YAML representation predictable so the
CLI scripts (``scripts/record_fs_events.py`` and
``scripts/verify_event_order.py``) can provide a friendly workflow.

The key abstractions are:

``ReplayScenario``
    A declaration of the events that should be written to a YAML replay file.

``ReplayEvent``
    A single filesystem operation including optional metadata.

``ReplayFileReport``
    The result of validating a replay file.  The verification step is very
    strict about ordering to make diagnosing regressions trivial.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

import yaml


class ReplayConfigError(ValueError):
    """Raised when a replay configuration file cannot be parsed."""


class ReplayVerificationError(ValueError):
    """Raised when a replay file fails structural verification."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ReplayEvent:
    """A single filesystem event that should be replayed later."""

    operation: str
    path: str
    timestamp: str | None = None
    data: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], *, index: int) -> "ReplayEvent":
        """Create an event from a YAML mapping.

        Parameters
        ----------
        raw:
            The parsed YAML mapping for the event.
        index:
            The position of the event in the source configuration.  The value
            is used only for error reporting.
        """

        if not isinstance(raw, Mapping):
            msg = f"Event #{index} must be a mapping, got {type(raw).__name__}"
            raise ReplayConfigError(msg)

        operation = raw.get("operation")
        path = raw.get("path")

        if not isinstance(operation, str) or not operation:
            raise ReplayConfigError(f"Event #{index} is missing a string 'operation'")
        if not isinstance(path, str) or not path:
            raise ReplayConfigError(f"Event #{index} is missing a string 'path'")

        timestamp_raw = raw.get("timestamp")
        timestamp_value: str | None = None
        if isinstance(timestamp_raw, str):
            timestamp_value = timestamp_raw
        elif isinstance(timestamp_raw, datetime):
            if timestamp_raw.tzinfo is None:
                normalized = timestamp_raw.replace(microsecond=0).isoformat()
                timestamp_value = normalized + "Z"
            else:
                normalized = timestamp_raw.astimezone(UTC).replace(microsecond=0).isoformat()
                timestamp_value = normalized.replace("+00:00", "Z")
        elif timestamp_raw is not None:
            raise ReplayConfigError(f"Event #{index} timestamp must be a string if provided")

        reserved_keys = {"operation", "path", "timestamp"}
        payload: dict[str, Any] = {
            key: value for key, value in raw.items() if key not in reserved_keys
        }

        return cls(operation=operation, path=path, timestamp=timestamp_value, data=payload)


@dataclass(frozen=True)
class ReplayScenario:
    """A named collection of events that will be written to a replay file."""

    name: str
    description: str | None
    events: Sequence[ReplayEvent]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], *, index: int) -> "ReplayScenario":
        if not isinstance(raw, Mapping):
            msg = f"Replay #{index} must be a mapping, got {type(raw).__name__}"
            raise ReplayConfigError(msg)

        name = raw.get("name")
        description = raw.get("description")
        events_raw = raw.get("events")

        if not isinstance(name, str) or not name:
            raise ReplayConfigError(f"Replay #{index} is missing a string 'name'")
        if description is not None and not isinstance(description, str):
            raise ReplayConfigError(f"Replay '{name}' description must be a string if provided")
        if events_raw is None:
            raise ReplayConfigError(f"Replay '{name}' must provide an 'events' list")
        if not isinstance(events_raw, Sequence) or isinstance(events_raw, (str, bytes)):
            raise ReplayConfigError(f"Replay '{name}' events must be a list of mappings")

        events = [
            ReplayEvent.from_mapping(event_raw, index=event_index + 1)
            for event_index, event_raw in enumerate(events_raw)
        ]

        return cls(name=name, description=description, events=events)


@dataclass(frozen=True)
class ReplayFileReport:
    """Represents the outcome of verifying a single replay YAML file."""

    path: Path
    ok: bool
    message: str
    error_code: int | None = None


def load_replay_config(path: Path) -> Sequence[ReplayScenario]:
    """Load a replay configuration file from ``path``."""

    with path.open("r", encoding="utf-8") as stream:
        payload = yaml.safe_load(stream)

    if payload is None:
        raise ReplayConfigError("Replay configuration file is empty")
    if not isinstance(payload, Mapping):
        raise ReplayConfigError("Replay configuration root must be a mapping")

    replays_raw = payload.get("replays")
    if replays_raw is None:
        raise ReplayConfigError("Replay configuration must contain a 'replays' key")
    if not isinstance(replays_raw, Sequence) or isinstance(replays_raw, (str, bytes)):
        raise ReplayConfigError("'replays' must be a list of replay declarations")

    return [
        ReplayScenario.from_mapping(raw_replay, index=index + 1)
        for index, raw_replay in enumerate(replays_raw)
    ]


def write_replay_files(replays: Sequence[ReplayScenario], directory: Path) -> Sequence[Path]:
    """Write the provided ``replays`` to ``directory``.

    The output files are named ``<replay.name>.yaml`` and contain a stable
    ``sequence`` number for each event.  Any additional metadata provided on
    the events is preserved.
    """

    directory.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []

    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for replay in replays:
        document: MutableMapping[str, Any] = {
            "name": replay.name,
            "generated_at": now,
            "events": [],
        }
        if replay.description:
            document["description"] = replay.description

        events_payload: list[MutableMapping[str, Any]] = []
        for sequence, event in enumerate(replay.events, start=1):
            event_payload: MutableMapping[str, Any] = {
                "sequence": sequence,
                "operation": event.operation,
                "path": event.path,
            }
            if event.timestamp is not None:
                event_payload["timestamp"] = event.timestamp
            if event.data:
                event_payload.update(event.data)
            events_payload.append(event_payload)

        document["events"] = events_payload

        target_path = directory / f"{replay.name}.yaml"
        with target_path.open("w", encoding="utf-8") as stream:
            yaml.safe_dump(document, stream, sort_keys=False)

        written_paths.append(target_path)

    return written_paths


def _parse_timestamp(value: str, *, sequence: int, file_path: Path) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:  # pragma: no cover - defensive branch
        message = f"Event #{sequence} timestamp in {file_path} is not ISO-8601: {value!r}"
        raise ReplayVerificationError(5, message) from exc


def verify_replay_file(path: Path) -> ReplayFileReport:
    """Verify a single replay file located at ``path``."""

    with path.open("r", encoding="utf-8") as stream:
        payload = yaml.safe_load(stream)

    if not isinstance(payload, Mapping):
        raise ReplayVerificationError(2, "Replay root must be a mapping")

    events = payload.get("events")
    if events is None:
        raise ReplayVerificationError(3, "Replay document must include an 'events' list")
    if not isinstance(events, list):
        raise ReplayVerificationError(3, "Replay 'events' entry must be a list")

    previous_sequence = 0
    previous_timestamp: datetime | None = None

    for item in events:
        if not isinstance(item, Mapping):
            raise ReplayVerificationError(4, "Each event must be a mapping")

        sequence = item.get("sequence")
        if not isinstance(sequence, int):
            raise ReplayVerificationError(4, "Each event must define an integer 'sequence'")
        if sequence != previous_sequence + 1:
            message = f"Event sequences must increase by 1 (expected {previous_sequence + 1}, got {sequence})"
            raise ReplayVerificationError(4, message)

        timestamp_value = item.get("timestamp")
        if timestamp_value is not None:
            if not isinstance(timestamp_value, str):
                raise ReplayVerificationError(5, "Event timestamp must be a string when provided")
            timestamp = _parse_timestamp(timestamp_value, sequence=sequence, file_path=path)
            if previous_timestamp and timestamp < previous_timestamp:
                message = (
                    "Event timestamps must be monotonically increasing. "
                    f"Event #{sequence} is earlier than the previous event."
                )
                raise ReplayVerificationError(6, message)
            previous_timestamp = timestamp

        previous_sequence = sequence

    return ReplayFileReport(path=path, ok=True, message="OK")


def verify_replay_directory(directory: Path) -> Sequence[ReplayFileReport]:
    """Verify all replay files located beneath ``directory``."""

    reports: list[ReplayFileReport] = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            report = verify_replay_file(path)
        except ReplayVerificationError as exc:
            reports.append(
                ReplayFileReport(
                    path=path,
                    ok=False,
                    message=str(exc),
                    error_code=exc.code,
                )
            )
        else:
            reports.append(report)
    return reports


__all__ = [
    "ReplayConfigError",
    "ReplayEvent",
    "ReplayFileReport",
    "ReplayScenario",
    "ReplayVerificationError",
    "load_replay_config",
    "verify_replay_directory",
    "verify_replay_file",
    "write_replay_files",
]

