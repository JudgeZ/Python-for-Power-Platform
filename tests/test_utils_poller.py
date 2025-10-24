from __future__ import annotations

import itertools

from pacx.utils.poller import poll_until


def test_poll_until_tracks_progress(monkeypatch):
    statuses = iter([
        {"done": False, "progress": 10},
        {"done": True, "progress": 90},
    ])
    updates: list[int] = []

    monkeypatch.setattr("pacx.utils.poller.time.sleep", lambda _: None)

    result = poll_until(
        get_status=lambda: next(statuses),
        is_done=lambda status: status["done"],
        get_progress=lambda status: status["progress"],
        on_update=lambda status: updates.append(status["progress"]),
        interval=0,
    )

    assert result["progress"] == 90
    # Both updates should have been emitted even though the progress changed only once.
    assert updates == [10, 90]


def test_poll_until_times_out(monkeypatch):
    status = {"done": False}
    time_values = itertools.chain([0.0, 10.0], itertools.repeat(10.0))

    def fake_time():
        return next(time_values)

    monkeypatch.setattr("pacx.utils.poller.time.sleep", lambda _: None)
    monkeypatch.setattr("pacx.utils.poller.time.time", fake_time)

    result = poll_until(
        get_status=lambda: status,
        is_done=lambda _: False,
        interval=0,
        timeout=1.0,
    )

    assert result is status
