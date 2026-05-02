from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any

from agent.run_events import RunEventRecord, RunEventType, RunNodeRecord, RunRecord, RunStatus
from agent.run_graph import RunGraph

SCHEMA_VERSION = 1

_TERMINAL_STATUSES = {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}
_EVIDENCE_EVENT_TYPES = {
    RunEventType.TOOL_RESULT,
    RunEventType.ARTIFACT_CREATED,
    RunEventType.ARTIFACT_UPDATED,
    RunEventType.ORACLE_RESULT,
}


@dataclass(slots=True)
class RunProjection:
    run_id: str
    goal: str
    source: str
    status: str
    phase: str
    active_node_ids: list[str] = field(default_factory=list)
    evidence_count: int = 0
    evidence_paths: list[str] = field(default_factory=list)
    blocked_reason: str | None = None
    next_action: str | None = None
    updated_at: float = field(default_factory=time.time)
    origin: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def from_graph(cls, graph: RunGraph) -> "RunProjection":
        if graph.run is None:
            return cls(
                run_id="noop",
                goal="",
                source="",
                status="noop",
                phase="noop",
                next_action="noop",
            )
        return cls.from_records(
            graph.run,
            list(graph.nodes.values()),
            graph.events,
        )

    @classmethod
    def from_records(
        cls,
        run: RunRecord,
        nodes: list[RunNodeRecord],
        events: list[RunEventRecord],
    ) -> "RunProjection":
        active_node_ids = [
            node.node_id
            for node in nodes
            if node.status == RunStatus.RUNNING and node.ended_at is None
        ]
        evidence_paths: list[str] = []
        evidence_count = 0
        blocked_reason: str | None = None

        for event in events:
            if event.event_type in _EVIDENCE_EVENT_TYPES:
                evidence_count += 1
                path = event.payload.get("artifact_path") or event.payload.get("path")
                if isinstance(path, str) and path not in evidence_paths:
                    evidence_paths.append(path)
            error = event.payload.get("error")
            if isinstance(error, str) and error:
                blocked_reason = error

        for node in nodes:
            if node.error:
                blocked_reason = node.error

        status = run.status.value
        if run.status == RunStatus.RUNNING:
            phase = "execute" if active_node_ids else "route"
            next_action = "wait_for_active_nodes" if active_node_ids else "start_next_node"
        elif run.status == RunStatus.FAILED:
            phase = "recover"
            next_action = "recover_or_escalate"
        elif run.status == RunStatus.SUCCEEDED:
            phase = "deliver"
            next_action = "deliver_or_archive"
        elif run.status == RunStatus.CANCELLED:
            phase = "recover"
            next_action = "acknowledge_cancelled"
        else:
            phase = "route"
            next_action = "inspect_run_state"

        if run.status in _TERMINAL_STATUSES:
            active_node_ids = []

        origin = run.metadata.get("origin") if isinstance(run.metadata, dict) else None
        if not isinstance(origin, dict):
            origin = {}

        return cls(
            run_id=run.run_id,
            goal=run.root_goal,
            source=run.source,
            status=status,
            phase=phase,
            active_node_ids=active_node_ids,
            evidence_count=evidence_count,
            evidence_paths=evidence_paths,
            blocked_reason=blocked_reason,
            next_action=next_action,
            origin=origin,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
