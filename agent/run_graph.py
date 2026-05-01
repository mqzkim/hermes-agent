from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from agent.run_events import RunEventRecord, RunEventType, RunNodeRecord, RunNodeType, RunRecord, RunStatus


@dataclass(slots=True)
class RunNodeTreeItem:
    node_id: str
    record: RunNodeRecord
    children: list["RunNodeTreeItem"] = field(default_factory=list)


class RunGraph:
    """In-memory lifecycle state for one Hermes run."""

    def __init__(self, run: RunRecord | None = None) -> None:
        self.run = run
        self.nodes: dict[str, RunNodeRecord] = {}
        self.events: list[RunEventRecord] = []
        self._sequence = 0

    @classmethod
    def start(
        cls,
        *,
        session_id: str | None,
        source: str,
        root_goal: str,
        parent_run_id: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "RunGraph":
        run = RunRecord.new(
            session_id=session_id,
            source=source,
            root_goal=root_goal,
            parent_run_id=parent_run_id,
            model=model,
            provider=provider,
            metadata=metadata or {},
        )
        graph = cls(run=run)
        graph.emit(RunEventType.RUN_STARTED, payload={"status": run.status.value})
        return graph

    def emit(
        self,
        event_type: RunEventType,
        *,
        node_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> RunEventRecord:
        if self.run is None:
            return RunEventRecord.new(run_id="noop", event_type=event_type, node_id=node_id, payload=payload or {})
        self._sequence += 1
        event = RunEventRecord.new(
            run_id=self.run.run_id,
            node_id=node_id,
            event_type=event_type,
            sequence=self._sequence,
            payload=payload or {},
        )
        self.events.append(event)
        return event

    def start_node(
        self,
        node_type: RunNodeType,
        *,
        title: str,
        parent_node_id: str | None = None,
        inputs: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RunNodeRecord:
        if self.run is None:
            return RunNodeRecord.new(
                run_id="noop",
                node_type=node_type,
                title=title,
                parent_node_id=parent_node_id,
                inputs=inputs or {},
                metadata=metadata or {},
            )
        node = RunNodeRecord.new(
            run_id=self.run.run_id,
            node_type=node_type,
            title=title,
            parent_node_id=parent_node_id,
            inputs=inputs or {},
            metadata=metadata or {},
        )
        self.nodes[node.node_id] = node
        self.emit(RunEventType.NODE_STARTED, node_id=node.node_id, payload={"node_type": node_type.value})
        return node

    def finish_node(
        self,
        node_id: str,
        *,
        outputs: dict[str, Any] | None = None,
        error: str | None = None,
        status: RunStatus | None = None,
    ) -> RunNodeRecord | None:
        node = self.nodes.get(node_id)
        if node is None:
            return None
        node.outputs = outputs or {}
        node.error = error
        node.ended_at = time.time()
        node.status = status or (RunStatus.FAILED if error else RunStatus.SUCCEEDED)
        self.emit(
            RunEventType.NODE_FAILED if node.status == RunStatus.FAILED else RunEventType.NODE_SUCCEEDED,
            node_id=node.node_id,
            payload={"status": node.status.value, "error": error},
        )
        return node

    def finish_run(
        self,
        *,
        outputs: dict[str, Any] | None = None,
        error: str | None = None,
        status: RunStatus | None = None,
    ) -> RunRecord | None:
        if self.run is None:
            return None
        self.run.ended_at = time.time()
        self.run.status = status or (RunStatus.FAILED if error else RunStatus.SUCCEEDED)
        if outputs:
            self.run.metadata = {**self.run.metadata, "outputs": outputs}
        event_type = RunEventType.RUN_FAILED if self.run.status == RunStatus.FAILED else RunEventType.RUN_SUCCEEDED
        self.emit(event_type, payload={"status": self.run.status.value, "error": error})
        return self.run

    def node_tree(self) -> list[RunNodeTreeItem]:
        items = {node_id: RunNodeTreeItem(node_id=node_id, record=node) for node_id, node in self.nodes.items()}
        roots: list[RunNodeTreeItem] = []
        for node in self.nodes.values():
            item = items[node.node_id]
            if node.parent_node_id and node.parent_node_id in items:
                items[node.parent_node_id].children.append(item)
            else:
                roots.append(item)
        return roots


class NoopRunGraph(RunGraph):
    """RunGraph-compatible no-op implementation for disabled instrumentation."""

    def __init__(self) -> None:
        super().__init__(run=None)

    def emit(
        self,
        event_type: RunEventType,
        *,
        node_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> RunEventRecord:
        return RunEventRecord.new(run_id="noop", event_type=event_type, node_id=node_id, payload=payload or {})

    def start_node(
        self,
        node_type: RunNodeType,
        *,
        title: str,
        parent_node_id: str | None = None,
        inputs: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RunNodeRecord:
        return RunNodeRecord.new(
            run_id="noop",
            node_type=node_type,
            title=title,
            parent_node_id=parent_node_id,
            inputs=inputs or {},
            metadata=metadata or {},
        )
