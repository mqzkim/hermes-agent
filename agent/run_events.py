from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

SCHEMA_VERSION = 1
_REDACTED = "[REDACTED]"
_SECRET_KEY_PARTS = frozenset(("api_key", "authorization", "password", "secret", "token"))


def _now() -> float:
    return time.time()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _SECRET_KEY_PARTS)


def sanitize_payload(value: Any, *, max_string_length: int = 8192) -> Any:
    """Return a JSON-safe, redacted copy of *value* for run graph storage."""
    if isinstance(value, dict):
        return {
            str(key): _REDACTED if _is_secret_key(str(key)) else sanitize_payload(val, max_string_length=max_string_length)
            for key, val in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [sanitize_payload(item, max_string_length=max_string_length) for item in value]
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        if len(value) > max_string_length:
            return f"{value[:max_string_length]}...[truncated]"
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    PARTIAL_SUCCEEDED = "partial_succeeded"


class RunNodeType(str, Enum):
    AGENT_TURN = "agent_turn"
    MODEL_CALL = "model_call"
    TOOL_CALL = "tool_call"
    SUBAGENT = "subagent"
    ARTIFACT = "artifact"
    DECISION = "decision"
    HUMAN_INPUT = "human_input"
    CRON_JOB = "cron_job"
    BENCHMARK_CASE = "benchmark_case"


class RunEventType(str, Enum):
    RUN_STARTED = "run_started"
    RUN_SUCCEEDED = "run_succeeded"
    RUN_FAILED = "run_failed"
    RUN_PAUSED = "run_paused"
    RUN_STOPPED = "run_stopped"
    NODE_STARTED = "node_started"
    NODE_SUCCEEDED = "node_succeeded"
    NODE_FAILED = "node_failed"
    NODE_RETRY = "node_retry"
    MODEL_REQUEST = "model_request"
    MODEL_RESPONSE = "model_response"
    TOOL_INVOCATION = "tool_invocation"
    TOOL_RESULT = "tool_result"
    SUBAGENT_SPAWNED = "subagent_spawned"
    SUBAGENT_COMPLETED = "subagent_completed"
    ARTIFACT_CREATED = "artifact_created"
    ARTIFACT_UPDATED = "artifact_updated"
    DECISION_RECORDED = "decision_recorded"
    ORACLE_RESULT = "oracle_result"
    HUMAN_INPUT_REQUESTED = "human_input_requested"
    HUMAN_INPUT_RECEIVED = "human_input_received"


@dataclass(slots=True)
class RunRecord:
    run_id: str
    session_id: str | None
    source: str
    root_goal: str
    status: RunStatus
    started_at: float
    ended_at: float | None = None
    parent_run_id: str | None = None
    model: str | None = None
    provider: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def new(cls, *, session_id: str | None, source: str, root_goal: str, **kwargs: Any) -> "RunRecord":
        return cls(
            run_id=_id("run"),
            session_id=session_id,
            source=source,
            root_goal=root_goal,
            status=RunStatus.RUNNING,
            started_at=_now(),
            **kwargs,
        )

    def to_dict(self, *, max_string_length: int = 8192) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["metadata"] = sanitize_payload(data["metadata"], max_string_length=max_string_length)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunRecord":
        payload = dict(data)
        payload["status"] = RunStatus(payload["status"])
        return cls(**payload)


@dataclass(slots=True)
class RunNodeRecord:
    node_id: str
    run_id: str
    node_type: RunNodeType
    title: str
    status: RunStatus
    started_at: float
    parent_node_id: str | None = None
    ended_at: float | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def new(
        cls,
        *,
        run_id: str,
        node_type: RunNodeType,
        title: str,
        parent_node_id: str | None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> "RunNodeRecord":
        return cls(
            node_id=_id("node"),
            run_id=run_id,
            node_type=node_type,
            title=title,
            parent_node_id=parent_node_id,
            status=RunStatus.RUNNING,
            started_at=_now(),
            inputs=inputs or {},
            **kwargs,
        )

    def to_dict(self, *, max_string_length: int = 8192) -> dict[str, Any]:
        data = asdict(self)
        data["node_type"] = self.node_type.value
        data["status"] = self.status.value
        data["inputs"] = sanitize_payload(data["inputs"], max_string_length=max_string_length)
        data["outputs"] = sanitize_payload(data["outputs"], max_string_length=max_string_length)
        data["metadata"] = sanitize_payload(data["metadata"], max_string_length=max_string_length)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunNodeRecord":
        payload = dict(data)
        payload["node_type"] = RunNodeType(payload["node_type"])
        payload["status"] = RunStatus(payload["status"])
        return cls(**payload)


@dataclass(slots=True)
class RunEventRecord:
    event_id: str
    run_id: str
    event_type: RunEventType
    timestamp: float
    node_id: str | None = None
    sequence: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def new(
        cls,
        *,
        run_id: str,
        event_type: RunEventType,
        node_id: str | None = None,
        payload: dict[str, Any] | None = None,
        sequence: int | None = None,
    ) -> "RunEventRecord":
        return cls(
            event_id=_id("evt"),
            run_id=run_id,
            node_id=node_id,
            event_type=event_type,
            timestamp=_now(),
            sequence=sequence,
            payload=payload or {},
        )

    def to_dict(self, *, max_string_length: int = 8192) -> dict[str, Any]:
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["payload"] = sanitize_payload(data["payload"], max_string_length=max_string_length)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunEventRecord":
        payload = dict(data)
        payload["event_type"] = RunEventType(payload["event_type"])
        return cls(**payload)
