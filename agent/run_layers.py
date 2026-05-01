from __future__ import annotations

import contextlib
import contextvars
import logging
import threading
from collections import defaultdict, deque
from collections.abc import Iterator, Sequence
from typing import Protocol

from agent.run_events import RunEventRecord, RunNodeRecord, RunRecord
from agent.run_graph import RunGraph
from hermes_state import SessionDB

logger = logging.getLogger(__name__)
_current_run_graph: contextvars.ContextVar[RunGraph | None] = contextvars.ContextVar(
    "current_run_graph", default=None
)


class RunLayer(Protocol):
    def on_run_start(self, graph: RunGraph, run: RunRecord) -> None: ...
    def on_node_start(self, graph: RunGraph, node: RunNodeRecord) -> None: ...
    def on_event(self, graph: RunGraph, event: RunEventRecord) -> None: ...
    def on_node_end(self, graph: RunGraph, node: RunNodeRecord) -> None: ...
    def on_run_end(self, graph: RunGraph, run: RunRecord) -> None: ...


class RunLayerDispatcher:
    """Dispatch run graph lifecycle hooks to layers with Dify-style isolation."""

    def __init__(self, layers: Sequence[RunLayer] = ()) -> None:
        self._layers = list(layers)

    def _dispatch(self, hook_name: str, graph: RunGraph, payload: RunRecord | RunNodeRecord | RunEventRecord) -> None:
        for layer in self._layers:
            hook = getattr(layer, hook_name, None)
            if hook is None:
                continue
            try:
                hook(graph, payload)
            except Exception:
                logger.warning(
                    "Run graph layer %s failed during %s",
                    layer.__class__.__name__,
                    hook_name,
                    exc_info=True,
                )

    def on_run_start(self, graph: RunGraph, run: RunRecord) -> None:
        self._dispatch("on_run_start", graph, run)

    def on_node_start(self, graph: RunGraph, node: RunNodeRecord) -> None:
        self._dispatch("on_node_start", graph, node)

    def on_event(self, graph: RunGraph, event: RunEventRecord) -> None:
        self._dispatch("on_event", graph, event)

    def on_node_end(self, graph: RunGraph, node: RunNodeRecord) -> None:
        self._dispatch("on_node_end", graph, node)

    def on_run_end(self, graph: RunGraph, run: RunRecord) -> None:
        self._dispatch("on_run_end", graph, run)


class PersistenceLayer:
    """Persist run graph records into SessionDB using best-effort writes."""

    def __init__(self, db: SessionDB) -> None:
        self._db = db

    def _safe(self, action: str, fn) -> None:
        try:
            fn()
        except Exception:
            logger.warning("Run graph persistence failed during %s", action, exc_info=True)

    def on_run_start(self, graph: RunGraph, run: RunRecord) -> None:
        self._safe("on_run_start", lambda: self._db.save_run_record(run))

    def on_node_start(self, graph: RunGraph, node: RunNodeRecord) -> None:
        self._safe("on_node_start", lambda: self._db.save_run_node_record(node))

    def on_event(self, graph: RunGraph, event: RunEventRecord) -> None:
        self._safe("on_event", lambda: self._db.append_run_event_record(event))

    def on_node_end(self, graph: RunGraph, node: RunNodeRecord) -> None:
        self._safe("on_node_end", lambda: self._db.save_run_node_record(node))

    def on_run_end(self, graph: RunGraph, run: RunRecord) -> None:
        self._safe("on_run_end", lambda: self._db.save_run_record(run))


class InMemoryEventSink:
    """Thread-safe bounded event tail per run for live UI consumers."""

    def __init__(self, *, max_events_per_run: int = 200) -> None:
        self._max_events_per_run = max_events_per_run
        self._events_by_run: dict[str, deque[RunEventRecord]] = defaultdict(
            lambda: deque(maxlen=self._max_events_per_run)
        )
        self._lock = threading.Lock()

    def on_event(self, graph: RunGraph, event: RunEventRecord) -> None:
        with self._lock:
            self._events_by_run[event.run_id].append(event)

    def tail(self, run_id: str, *, limit: int | None = None) -> list[RunEventRecord]:
        with self._lock:
            events = list(self._events_by_run.get(run_id, ()))
        if limit is None:
            return events
        return events[-limit:]

    def clear(self, run_id: str | None = None) -> None:
        with self._lock:
            if run_id is None:
                self._events_by_run.clear()
            else:
                self._events_by_run.pop(run_id, None)


def current_run_graph() -> RunGraph | None:
    return _current_run_graph.get()


@contextlib.contextmanager
def run_graph_context(graph: RunGraph | None) -> Iterator[RunGraph | None]:
    token = _current_run_graph.set(graph)
    try:
        yield graph
    finally:
        _current_run_graph.reset(token)
