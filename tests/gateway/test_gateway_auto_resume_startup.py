"""Tests for automatic gateway restart recovery of pending sessions."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.run import GatewayRunner
from gateway.session import SessionEntry, SessionSource


class FakeAdapter:
    def __init__(self):
        self.events: list[MessageEvent] = []
        self.sent: list[tuple[str, str, object]] = []

    async def handle_message(self, event: MessageEvent) -> None:
        self.events.append(event)

    async def send(self, chat_id: str, content: str, **kwargs) -> None:
        self.sent.append((chat_id, content, kwargs.get("metadata")))


def _source(*, platform: Platform = Platform.DISCORD, chat_id: str = "chan", thread_id: str = "thread") -> SessionSource:
    return SessionSource(
        platform=platform,
        chat_id=chat_id,
        chat_type="channel",
        user_id="user-1",
        user_name="Marquez",
        thread_id=thread_id,
    )


def _entry(
    key: str,
    *,
    source: SessionSource | None = None,
    resume_pending: bool = True,
    suspended: bool = False,
    marked_delta: timedelta = timedelta(seconds=10),
) -> SessionEntry:
    now = datetime.now()
    return SessionEntry(
        session_key=key,
        session_id=f"session-{key}",
        created_at=now - timedelta(minutes=5),
        updated_at=now - timedelta(seconds=5),
        origin=source if source is not None else _source(thread_id=key),
        platform=(source.platform if source else Platform.DISCORD),
        chat_type="channel",
        resume_pending=resume_pending,
        resume_reason="restart_timeout",
        last_resume_marked_at=now - marked_delta,
        suspended=suspended,
    )


def _runner(entries: dict[str, SessionEntry], adapter: FakeAdapter | None = None) -> GatewayRunner:
    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.DISCORD: PlatformConfig(enabled=True, token="fake")}
    )
    runner.adapters = {Platform.DISCORD: adapter or FakeAdapter()}
    runner._running_agents = {}
    runner._background_tasks = set()
    runner._running = True
    runner._draining = False
    runner.session_store = SimpleNamespace(
        _entries=entries,
        _ensure_loaded=MagicMock(),
    )
    return runner


def test_collect_auto_resume_entries_only_selects_fresh_connected_pending_sessions(monkeypatch):
    monkeypatch.setenv("HERMES_AUTO_CONTINUE_FRESHNESS", "3600")
    fresh = _entry("fresh")
    stale = _entry("stale", marked_delta=timedelta(hours=2))
    suspended = _entry("suspended", suspended=True)
    missing_origin = _entry("missing-origin", source=None)
    missing_origin.origin = None
    not_pending = _entry("not-pending", resume_pending=False)
    running = _entry("running")
    other_platform_source = _source(platform=Platform.TELEGRAM, chat_id="tg", thread_id="tg-thread")
    disconnected = _entry("disconnected", source=other_platform_source)

    runner = _runner({
        "fresh": fresh,
        "stale": stale,
        "suspended": suspended,
        "missing-origin": missing_origin,
        "not-pending": not_pending,
        "running": running,
        "disconnected": disconnected,
    })
    runner._running_agents = {"running": object()}

    assert runner._collect_auto_resume_entries() == [("fresh", fresh)]
    runner.session_store._ensure_loaded.assert_called_once()


@pytest.mark.asyncio
async def test_auto_resume_startup_dispatches_internal_synthetic_events_to_original_threads(monkeypatch):
    monkeypatch.setenv("HERMES_GATEWAY_AUTO_RESUME_PENDING", "true")
    adapter = FakeAdapter()
    source_a = _source(chat_id="channel-a", thread_id="thread-a")
    source_b = _source(chat_id="channel-b", thread_id="thread-b")
    runner = _runner({
        "a": _entry("a", source=source_a),
        "b": _entry("b", source=source_b),
    }, adapter=adapter)

    count = await runner._auto_resume_pending_sessions()

    assert count == 2
    assert [event.source.thread_id for event in adapter.events] == ["thread-a", "thread-b"]
    assert all(event.internal for event in adapter.events)
    assert all("gateway restart" in event.text.lower() for event in adapter.events)
    assert [sent[0] for sent in adapter.sent] == ["channel-a", "channel-b"]
    assert [sent[2] for sent in adapter.sent] == [
        {"thread_id": "thread-a"},
        {"thread_id": "thread-b"},
    ]


@pytest.mark.asyncio
async def test_auto_resume_startup_can_be_disabled(monkeypatch):
    monkeypatch.setenv("HERMES_GATEWAY_AUTO_RESUME_PENDING", "false")
    adapter = FakeAdapter()
    runner = _runner({"fresh": _entry("fresh")}, adapter=adapter)

    count = await runner._auto_resume_pending_sessions()

    assert count == 0
    assert adapter.events == []
