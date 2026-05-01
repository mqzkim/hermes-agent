# Dify 기반 Hermes Run Graph Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Hermes의 모든 agent/model/tool/subagent 실행을 `Run → Node → Event → Artifact` 그래프로 기록·조회·제어할 수 있는 production orchestration substrate를 구축한다.

**Architecture:** Dify의 GraphEngine/Layer/Event 패턴을 Hermes-native thin contracts로 이식한다. `run_agent.py`와 `tools/delegate_tool.py`에는 최소 instrumentation만 추가하고, 핵심 계약은 `agent/run_events.py`, `agent/run_graph.py`, `agent/run_layers.py`, `hermes_state.py` 확장으로 분리한다.

**Tech Stack:** Python 3, dataclasses/typing, SQLite WAL via `hermes_state.SessionDB`, pytest, existing Hermes tool registry/subagent/gateway/TUI infrastructure.

---

## 0. 실행 원칙

- TDD 우선: 새 core behavior는 실패 테스트 → 최소 구현 → 통과 확인 순서로 진행한다.
- 작은 PR 단위: 각 task는 가능하면 2~5분 단위의 작은 commit으로 끝낸다.
- 호환성 우선: 기존 `sessions`, `messages`, FTS 동작을 깨지 않는다.
- Best-effort instrumentation: run graph 기록 실패가 agent 실행 실패로 번지면 안 된다.
- UI보다 schema 먼저: Agent Board는 P0 schema/persistence가 안정된 뒤 붙인다.
- Dify의 `graphon`은 도입하지 않는다. 계약만 가져온다.

---

## 1. Index

### 1.1 문서 Index

- [0. 실행 원칙](#0-실행-원칙)
- [1. Index](#1-index)
- [2. 전체 작업 Index](#2-전체-작업-index)
- [3. 파일/모듈 Index](#3-파일모듈-index)
- [4. 테스트 Index](#4-테스트-index)
- [5. Phase A: Core Schema](#5-phase-a-core-schema)
- [6. Phase B: Persistence](#6-phase-b-persistence)
- [7. Phase C: Layer/Event Bus](#7-phase-c-layerevent-bus)
- [8. Phase D: Agent Loop Instrumentation](#8-phase-d-agent-loop-instrumentation)
- [9. Phase E: Delegate/Subagent Integration](#9-phase-e-delegatesubagent-integration)
- [10. Phase F: Read API / UI Bridge](#10-phase-f-read-api--ui-bridge)
- [11. Phase G: Artifact MVP](#11-phase-g-artifact-mvp)
- [12. Phase H: Benchmark Harness Hook](#12-phase-h-benchmark-harness-hook)
- [13. Global Verification](#13-global-verification)
- [14. Rollout / Rollback](#14-rollout--rollback)
- [15. Master Checklist](#15-master-checklist)

### 1.2 PRD 매핑 Index

| PRD 항목 | 구현 Phase | 핵심 파일 |
|---|---|---|
| FR-01 Run 생성 | A, B, D | `agent/run_events.py`, `hermes_state.py`, `run_agent.py` |
| FR-02 Node lifecycle | A, B, D, E | `agent/run_graph.py`, `run_agent.py`, `tools/delegate_tool.py` |
| FR-03 Event append-only | A, B, C | `agent/run_events.py`, `hermes_state.py`, `agent/run_layers.py` |
| FR-04 Layer hook | C | `agent/run_layers.py` |
| FR-05 Subagent graph 연결 | E | `tools/delegate_tool.py` |
| FR-06 Artifact update | G | `agent/run_artifacts.py`, `hermes_state.py` |
| FR-07 조회 API | F | `hermes_state.py`, `tui_gateway/`, `gateway/` |
| FR-08 Replay 준비 | D, E, H | `run_agent.py`, `tools/delegate_tool.py`, `environments/` |

---

## 2. 전체 작업 Index

### 2.1 Phase별 수행 Index

| Phase | 이름 | 선행 조건 | 산출물 | 완료 체크 |
|---|---|---|---|---|
| A | Core Schema | 없음 | event/node/run dataclass | unit test 통과 |
| B | Persistence | A | SQLite schema/API | migration/idempotency 통과 |
| C | Layer/Event Bus | A, B | RunLayer/EventEmitter | layer 예외 격리 통과 |
| D | Agent Loop Instrumentation | C | model/tool call events | mocked loop test 통과 |
| E | Delegate Integration | C, D | subagent node | delegate tests 통과 |
| F | Read API/UI Bridge | B | run tree/event tail API | JSON snapshot test 통과 |
| G | Artifact MVP | B, C | artifact/version | artifact tests 통과 |
| H | Benchmark Hook | F, G | oracle result 연결 | sample harness test 통과 |

### 2.2 우선순위 Index

#### P0 필수

- A1~A5 Core Schema
- B1~B6 Persistence
- C1~C4 Layer/Event Bus
- D1~D5 Agent Loop model/tool instrumentation
- E1~E4 Delegate subagent node
- F1~F3 최소 조회 API

#### P1 권장

- G1~G5 Artifact MVP
- F4 TUI/Gateway bridge
- H1~H3 Benchmark hook skeleton

#### P2 이후

- full replay
- human input pause/resume
- trigger node 통합
- OTel exporter

---

## 3. 파일/모듈 Index

### 3.1 새 파일

| 파일 | 목적 |
|---|---|
| `agent/run_events.py` | Run/Node/Event enum 및 dataclass |
| `agent/run_graph.py` | in-memory run graph/runtime state |
| `agent/run_layers.py` | RunLayer protocol, event emitter, 기본 layer |
| `agent/run_artifacts.py` | Artifact/ArtifactVersion 모델과 helper |
| `tests/agent/test_run_events.py` | schema serialization tests |
| `tests/agent/test_run_graph.py` | graph lifecycle tests |
| `tests/agent/test_run_layers.py` | layer dispatch/error isolation tests |
| `tests/test_run_graph_persistence.py` | SessionDB migration/persistence tests |
| `tests/agent/test_run_agent_instrumentation.py` | model/tool instrumentation tests |
| `tests/tools/test_delegate_run_graph.py` | subagent node tests |

### 3.2 수정 파일

| 파일 | 수정 목적 |
|---|---|
| `hermes_state.py` | schema version 증가, run graph tables/API 추가 |
| `run_agent.py` | run context 생성, model/tool call node event emit |
| `model_tools.py` | tool invocation metadata 반환 또는 hook 위치 제공 |
| `tools/delegate_tool.py` | subagent node/event emit |
| `tui_gateway/server.py` 또는 관련 RPC 파일 | run graph 조회 endpoint 추가 |
| `gateway/session.py` 또는 관련 session bridge | gateway source/session 연결 |
| `tests/test_hermes_state.py` | 기존 schema regression 보강 |

---

## 4. 테스트 Index

### 4.1 Unit Test

- `pytest tests/agent/test_run_events.py -v`
- `pytest tests/agent/test_run_graph.py -v`
- `pytest tests/agent/test_run_layers.py -v`
- `pytest tests/test_run_graph_persistence.py -v`

### 4.2 Integration-ish Test

- `pytest tests/agent/test_run_agent_instrumentation.py -v`
- `pytest tests/tools/test_delegate_run_graph.py -v`
- `pytest tests/test_hermes_state.py -v`
- `pytest tests/tools/test_registry.py -v`

### 4.3 Full Regression

```bash
source venv/bin/activate || source .venv/bin/activate
scripts/run_tests.sh
```

기대: 기존 test regression 없음. 시간이 과도하면 변경 영역 중심 test 먼저 실행 후 CI/full suite에서 확인한다.

---

## 5. Phase A: Core Schema

### Task A1: Run/Event enum 정의 테스트 작성

**Objective:** Run graph의 status/type enum 계약을 고정한다.

**Files:**

- Create: `tests/agent/test_run_events.py`
- Create later: `agent/run_events.py`

**Step 1: Write failing test**

```python
from agent.run_events import RunStatus, RunNodeType, RunEventType


def test_run_status_values_are_stable():
    assert RunStatus.RUNNING.value == "running"
    assert RunStatus.SUCCEEDED.value == "succeeded"
    assert RunStatus.FAILED.value == "failed"
    assert RunStatus.PAUSED.value == "paused"


def test_node_and_event_type_values_are_stable():
    assert RunNodeType.TOOL_CALL.value == "tool_call"
    assert RunNodeType.SUBAGENT.value == "subagent"
    assert RunEventType.NODE_STARTED.value == "node_started"
    assert RunEventType.TOOL_RESULT.value == "tool_result"
```

**Step 2: Run test to verify failure**

```bash
pytest tests/agent/test_run_events.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'agent.run_events'`.

**Step 3: Implement minimal enum file**

Create `agent/run_events.py`:

```python
from __future__ import annotations

from enum import Enum


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
    HUMAN_INPUT_REQUESTED = "human_input_requested"
    HUMAN_INPUT_RECEIVED = "human_input_received"
```

**Step 4: Run test**

```bash
pytest tests/agent/test_run_events.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add agent/run_events.py tests/agent/test_run_events.py
git commit -m "feat: add run graph event enums"
```

### Task A2: RunRecord/RunNodeRecord/RunEventRecord serialization 테스트

**Objective:** DB/API에 저장 가능한 JSON-safe record 모델을 만든다.

**Files:**

- Modify: `tests/agent/test_run_events.py`
- Modify: `agent/run_events.py`

**Step 1: Write failing test**

```python
from agent.run_events import RunEventRecord, RunEventType, RunNodeRecord, RunNodeType, RunRecord, RunStatus


def test_run_records_round_trip_dict():
    run = RunRecord.new(session_id="s1", source="discord", root_goal="analyze repo")
    node = RunNodeRecord.new(
        run_id=run.run_id,
        node_type=RunNodeType.TOOL_CALL,
        title="terminal",
        parent_node_id=None,
        inputs={"command": "pwd"},
    )
    event = RunEventRecord.new(
        run_id=run.run_id,
        node_id=node.node_id,
        event_type=RunEventType.NODE_STARTED,
        payload={"status": "running"},
    )

    assert RunRecord.from_dict(run.to_dict()).run_id == run.run_id
    assert RunNodeRecord.from_dict(node.to_dict()).inputs["command"] == "pwd"
    assert RunEventRecord.from_dict(event.to_dict()).event_type == RunEventType.NODE_STARTED
```

**Step 2: Run failure**

```bash
pytest tests/agent/test_run_events.py::test_run_records_round_trip_dict -v
```

Expected: FAIL — classes missing.

**Step 3: Implement dataclasses**

Add to `agent/run_events.py`:

```python
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = 1


def _now() -> float:
    return time.time()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


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

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
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
    def new(cls, *, run_id: str, node_type: RunNodeType, title: str, parent_node_id: str | None, inputs: dict[str, Any] | None = None, **kwargs: Any) -> "RunNodeRecord":
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

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["node_type"] = self.node_type.value
        data["status"] = self.status.value
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
    def new(cls, *, run_id: str, event_type: RunEventType, node_id: str | None = None, payload: dict[str, Any] | None = None, sequence: int | None = None) -> "RunEventRecord":
        return cls(
            event_id=_id("evt"),
            run_id=run_id,
            node_id=node_id,
            event_type=event_type,
            timestamp=_now(),
            sequence=sequence,
            payload=payload or {},
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["event_type"] = self.event_type.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunEventRecord":
        payload = dict(data)
        payload["event_type"] = RunEventType(payload["event_type"])
        return cls(**payload)
```

**Step 4: Run test**

```bash
pytest tests/agent/test_run_events.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add agent/run_events.py tests/agent/test_run_events.py
git commit -m "feat: add serializable run graph records"
```

### Task A3: JSON safety/redaction utility 테스트

**Objective:** event payload가 DB에 안전하게 저장되도록 non-serializable 값과 secrets를 처리한다.

**Files:**

- Modify: `agent/run_events.py`
- Modify: `tests/agent/test_run_events.py`

**Checklist:**

- [ ] `api_key`, `token`, `authorization`, `password`, `secret` key redaction
- [ ] bytes/object fallback stringification
- [ ] max string length cap
- [ ] 원본 dict mutation 없음

**Implementation hint:** `sanitize_payload(value, max_string=8192)` helper 추가.

### Task A4: RunGraph in-memory lifecycle 테스트

**Objective:** run/node/event를 메모리에서 순서대로 관리하는 runtime state를 만든다.

**Files:**

- Create: `agent/run_graph.py`
- Create: `tests/agent/test_run_graph.py`

**Checklist:**

- [ ] `RunGraph.start_run()`
- [ ] `RunGraph.start_node()`
- [ ] `RunGraph.finish_node()`
- [ ] `RunGraph.finish_run()`
- [ ] event sequence 증가
- [ ] parent-child node tree 조회

### Task A5: RunGraph disabled/no-op mode 테스트

**Objective:** config나 환경에서 run graph가 꺼져도 기존 실행이 영향받지 않게 한다.

**Files:**

- Modify: `agent/run_graph.py`
- Modify: `tests/agent/test_run_graph.py`

**Checklist:**

- [ ] `NoopRunGraph` 또는 `RunGraph(enabled=False)`
- [ ] 모든 method가 예외 없이 no-op
- [ ] caller code가 if문 없이 호출 가능

---

## 6. Phase B: Persistence

### Task B1: SessionDB schema version 증가 테스트

**Objective:** 새 테이블을 additive migration으로 추가한다.

**Files:**

- Modify: `hermes_state.py`
- Create: `tests/test_run_graph_persistence.py`

**Step 1: Write failing test**

```python
from hermes_state import SessionDB


def test_run_graph_tables_created(tmp_path):
    db = SessionDB(tmp_path / "state.db")
    rows = db._conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = {row[0] for row in rows}
    assert "runs" in names
    assert "run_nodes" in names
    assert "run_events" in names
```

**Step 2: Implement schema**

Modify `SCHEMA_VERSION = 9` and append tables:

```sql
CREATE TABLE IF NOT EXISTS runs (...);
CREATE TABLE IF NOT EXISTS run_nodes (...);
CREATE TABLE IF NOT EXISTS run_events (...);
CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_run_nodes_run ON run_nodes(run_id, started_at);
CREATE INDEX IF NOT EXISTS idx_run_events_run ON run_events(run_id, sequence, timestamp);
```

**Acceptance checklist:**

- [ ] 기존 DB migration path 통과
- [ ] fresh DB 생성 통과
- [ ] `tests/test_hermes_state.py` 통과

### Task B2: save_run/get_run API

**Objective:** `RunRecord`를 SQLite에 저장/조회한다.

**Files:**

- Modify: `hermes_state.py`
- Modify: `tests/test_run_graph_persistence.py`

**Methods:**

- `save_run_record(record: RunRecord) -> None`
- `get_run_record(run_id: str) -> RunRecord | None`
- `list_recent_runs(limit: int = 20) -> list[RunRecord]`

**Checklist:**

- [ ] JSON metadata round-trip
- [ ] session_id nullable
- [ ] parent_run_id nullable
- [ ] ordered recent list

### Task B3: save_node/get_nodes API

**Objective:** run node lifecycle를 저장/조회한다.

**Methods:**

- `save_run_node_record(record: RunNodeRecord) -> None`
- `get_run_node_record(node_id: str) -> RunNodeRecord | None`
- `list_run_node_records(run_id: str) -> list[RunNodeRecord]`

**Checklist:**

- [ ] parent_node_id 보존
- [ ] inputs/outputs JSON round-trip
- [ ] error/status update 가능

### Task B4: append_event/list_events API

**Objective:** event append-only log를 저장/조회한다.

**Methods:**

- `append_run_event_record(record: RunEventRecord) -> None`
- `list_run_event_records(run_id: str, limit: int = 200, after_sequence: int | None = None) -> list[RunEventRecord]`

**Checklist:**

- [ ] sequence ordering
- [ ] after_sequence tail query
- [ ] payload JSON round-trip

### Task B5: Persistence payload cap/redaction 테스트

**Objective:** 큰 payload와 secret이 DB에 직접 누출되지 않게 한다.

**Checklist:**

- [ ] secret keys redacted
- [ ] long string truncated marker 포함
- [ ] invalid JSON fallback 저장 가능

### Task B6: Migration idempotency/regression

**Objective:** 기존 SessionDB 기능이 깨지지 않는다.

**Commands:**

```bash
pytest tests/test_hermes_state.py tests/test_run_graph_persistence.py -v
```

Expected: PASS.

---

## 7. Phase C: Layer/Event Bus

### Task C1: RunLayer protocol 테스트

**Objective:** Dify `GraphEngineLayer`에 해당하는 Hermes lifecycle hook을 만든다.

**Files:**

- Create: `agent/run_layers.py`
- Create: `tests/agent/test_run_layers.py`

**Protocol:**

```python
class RunLayer(Protocol):
    def on_run_start(self, graph: RunGraph, run: RunRecord) -> None: ...
    def on_node_start(self, graph: RunGraph, node: RunNodeRecord) -> None: ...
    def on_event(self, graph: RunGraph, event: RunEventRecord) -> None: ...
    def on_node_end(self, graph: RunGraph, node: RunNodeRecord) -> None: ...
    def on_run_end(self, graph: RunGraph, run: RunRecord) -> None: ...
```

**Checklist:**

- [ ] order 보장
- [ ] layer 예외 격리
- [ ] warning log

### Task C2: PersistenceLayer 구현

**Objective:** RunGraph event를 SessionDB에 저장한다.

**Files:**

- Modify: `agent/run_layers.py`
- Modify: `tests/agent/test_run_layers.py`

**Checklist:**

- [ ] run start 저장
- [ ] node start/end 저장
- [ ] event append 저장
- [ ] DB 실패 시 agent execution으로 예외 전파 없음

### Task C3: InMemoryEventSink 구현

**Objective:** UI/tail 조회를 위한 process-local event buffer를 둔다.

**Checklist:**

- [ ] run_id별 최근 N events
- [ ] thread-safe
- [ ] max size cap

### Task C4: RunGraphManager singleton/context helper

**Objective:** `run_agent.py`와 tools에서 쉽게 현재 run graph를 얻는다.

**Files:**

- Modify: `agent/run_graph.py`
- Create tests

**API 후보:**

- `get_current_run_graph() -> RunGraph | None`
- `set_current_run_graph(graph: RunGraph | None)` using `contextvars`
- `current_run_context(...)` context manager

**Checklist:**

- [ ] nested context 동작
- [ ] thread/subagent 전파 방식 문서화
- [ ] no-op fallback

---

## 8. Phase D: Agent Loop Instrumentation

### Task D1: run_agent에 root Run 생성 위치 찾기

**Objective:** `AIAgent.run_conversation()` 시작/종료에 run lifecycle을 붙일 정확한 위치를 정한다.

**Files:**

- Inspect: `run_agent.py`
- Modify later: `run_agent.py`
- Test: `tests/agent/test_run_agent_instrumentation.py`

**Checklist:**

- [ ] `session_id`, `platform`, `provider`, `model` 접근 위치 확인
- [ ] early return/failure path 확인
- [ ] interrupt path 확인
- [ ] budget grace path 확인

### Task D2: mocked run_conversation root run test

**Objective:** 실제 API 호출 없이 run start/end event를 검증한다.

**Checklist:**

- [ ] fake client/model response 사용
- [ ] final response path에서 run_succeeded
- [ ] exception path에서 run_failed
- [ ] graph disabled path에서 기존 return 동일

### Task D3: model_call node instrumentation

**Objective:** 각 provider API 호출을 `model_call` node로 기록한다.

**Checklist:**

- [ ] model/provider/base_url metadata
- [ ] request token estimate 가능하면 metadata
- [ ] response usage/cost 가능하면 metadata
- [ ] API error 시 node_failed

### Task D4: tool_call node instrumentation

**Objective:** tool call start/result/error를 node/event로 기록한다.

**Files:**

- Modify: `run_agent.py` 또는 `model_tools.py`
- Tests: `tests/agent/test_run_agent_instrumentation.py`

**Checklist:**

- [ ] tool name 저장
- [ ] sanitized arguments 저장
- [ ] result preview 저장
- [ ] error detection 저장
- [ ] tool_call_id 연결

### Task D5: instrumentation regression tests

**Commands:**

```bash
pytest tests/agent/test_run_agent_instrumentation.py -v
pytest tests/test_model_tools_async_bridge.py -v
pytest tests/tools/test_registry.py -v
```

Expected: PASS.

---

## 9. Phase E: Delegate/Subagent Integration

### Task E1: delegate_task subagent node test 작성

**Objective:** child agent spawn/completion이 parent run graph에 남는다.

**Files:**

- Modify: `tools/delegate_tool.py`
- Create: `tests/tools/test_delegate_run_graph.py`

**Checklist:**

- [ ] `subagent_spawned` event
- [ ] `subagent_completed` event
- [ ] depth/parent_id/model/goal metadata
- [ ] output tail 저장

### Task E2: active_subagents registry와 node id 연결

**Objective:** `list_active_subagents()` snapshot에 `run_id`, `node_id`를 추가한다.

**Files:**

- Modify: `tools/delegate_tool.py`

**Checklist:**

- [ ] 기존 consumers 깨지 않게 additive key
- [ ] interrupt_subagent 후 status update 가능
- [ ] unregister 시 completion event 발생

### Task E3: child run parent_run_id 연결

**Objective:** child AIAgent가 별도 run을 만들 경우 parent_run_id를 보존한다.

**Checklist:**

- [ ] contextvars 또는 explicit constructor metadata 전달
- [ ] child run 조회 시 parent 관계 확인
- [ ] nested orchestrator depth cap과 충돌 없음

### Task E4: delegate regression

**Commands:**

```bash
pytest tests/tools/test_delegate_run_graph.py -v
pytest tests/agent/test_subagent_stop_hook.py -v
```

Expected: PASS.

---

## 10. Phase F: Read API / UI Bridge

### Task F1: SessionDB run detail query

**Objective:** UI가 한 번에 run tree를 가져오게 한다.

**Methods:**

- `get_run_graph_snapshot(run_id: str) -> dict`

**Snapshot shape:**

```json
{
  "run": {},
  "nodes": [],
  "events_tail": [],
  "artifacts": []
}
```

**Checklist:**

- [ ] JSON serializable
- [ ] nodes ordered
- [ ] events limited
- [ ] missing run returns None or explicit error

### Task F2: TUI gateway RPC 추가

**Objective:** TUI/Agent Board가 run graph를 조회한다.

**Files:**

- Inspect/Modify: `tui_gateway/`
- Tests: existing `tests/test_tui_gateway_server.py` 또는 새 test

**RPC 후보:**

- `runs.list_recent`
- `runs.get_snapshot`
- `runs.events_tail`

**Checklist:**

- [ ] 기존 RPC와 auth/transport 패턴 일치
- [ ] missing run error shape 안정화
- [ ] snapshot size cap

### Task F3: gateway/API bridge 추가

**Objective:** Discord/web gateway에서 run link/status를 보여줄 수 있게 한다.

**Files:**

- Inspect/Modify: `gateway/`
- Optional: `hermes_cli/web_server.py`

**Checklist:**

- [ ] run_id가 response metadata 또는 logs에 노출
- [ ] home/channel thread context와 session_id 연결
- [ ] Discord API 직접 조작은 하지 않음

### Task F4: minimal Agent Board panel plan

**Objective:** 실제 UI 구현 전 필요한 JSON contract를 고정한다.

**Files:**

- Create: `plans/agent-board-run-graph-ui-contract.md`

**Checklist:**

- [ ] Run tree panel data
- [ ] Event timeline data
- [ ] Artifact pane data
- [ ] Inspector data
- [ ] Controls disabled/enabled matrix

---

## 11. Phase G: Artifact MVP

### Task G1: Artifact dataclass 테스트

**Files:**

- Create: `agent/run_artifacts.py`
- Create: `tests/agent/test_run_artifacts.py`

**Artifact types:**

- `document`
- `table`
- `checklist`
- `decision_log`
- `task_tree`
- `benchmark_report`
- `code_patch`
- `file_reference`

**Checklist:**

- [ ] artifact id/version id
- [ ] content type
- [ ] producer node id
- [ ] version timestamp

### Task G2: artifact tables/API

**Files:**

- Modify: `hermes_state.py`
- Test: `tests/test_run_graph_persistence.py`

**Tables:**

- `artifacts`
- `artifact_versions`

**Checklist:**

- [ ] list by run
- [ ] latest version
- [ ] version history

### Task G3: decision log artifact helper

**Objective:** model/tool/retry 선택 이유를 구조화해 남긴다.

**Checklist:**

- [ ] `record_decision(title, rationale, alternatives, node_id)` helper
- [ ] event `decision_recorded`
- [ ] artifact type `decision_log`

### Task G4: benchmark report artifact helper

**Objective:** benchmark/harness 결과를 artifact로 저장한다.

**Checklist:**

- [ ] case id
- [ ] oracle result
- [ ] pass/fail
- [ ] evidence node/artifact references

---

## 12. Phase H: Benchmark Harness Hook

### Task H1: benchmark case node skeleton

**Objective:** benchmark 실행을 run graph에 연결할 수 있는 최소 helper를 만든다.

**Candidate files:**

- `environments/agent_loop.py`
- `environments/hermes_base_env.py`
- `batch_runner.py`

**Checklist:**

- [ ] benchmark case start node
- [ ] oracle event
- [ ] artifact snapshot link

### Task H2: oracle result schema

**Objective:** 평가 결과를 transcript가 아니라 structured payload로 저장한다.

**Payload fields:**

- `oracle_name`
- `passed`
- `score`
- `failures[]`
- `evidence_refs[]`

### Task H3: sample harness test

**Checklist:**

- [ ] fake benchmark case 실행
- [ ] run graph snapshot에 oracle result 포함
- [ ] failure evidence가 node/artifact ref로 연결됨

---

## 13. Global Verification

### 13.1 변경 영역 테스트

```bash
pytest \
  tests/agent/test_run_events.py \
  tests/agent/test_run_graph.py \
  tests/agent/test_run_layers.py \
  tests/test_run_graph_persistence.py \
  tests/agent/test_run_agent_instrumentation.py \
  tests/tools/test_delegate_run_graph.py \
  -v
```

### 13.2 기존 회귀 테스트

```bash
pytest tests/test_hermes_state.py -v
pytest tests/test_model_tools_async_bridge.py -v
pytest tests/tools/test_registry.py -v
pytest tests/agent/test_subagent_stop_hook.py -v
pytest tests/test_tui_gateway_server.py -v
```

### 13.3 Manual smoke

```bash
hermes-agent "간단히 pwd를 실행하고 결과를 말해줘" --enabled-toolsets terminal
```

확인:

- [ ] agent 응답 정상
- [ ] `~/.hermes/state.db`에 run 저장
- [ ] run_nodes에 model/tool node 저장
- [ ] run_events에 start/end event 저장
- [ ] session search 기능 정상

---

## 14. Rollout / Rollback

### 14.1 Feature flag

권장 config:

```yaml
run_graph:
  enabled: true
  persist: true
  max_payload_chars: 8192
  redact_secrets: true
```

환경 변수 override 후보:

```bash
HERMES_RUN_GRAPH_ENABLED=0
```

### 14.2 Rollback

- 코드 rollback 없이 config로 instrumentation no-op 가능해야 한다.
- DB schema는 additive이므로 rollback 시 테이블을 제거하지 않는다.
- 조회 API는 새 테이블이 없어도 graceful error를 반환한다.

---

## 15. Master Checklist

### 15.1 Phase A Checklist

- [ ] enum values stable
- [ ] dataclass serialization round-trip
- [ ] payload sanitize/redaction
- [ ] in-memory RunGraph lifecycle
- [ ] no-op mode

### 15.2 Phase B Checklist

- [ ] schema version 증가
- [ ] `runs` table
- [ ] `run_nodes` table
- [ ] `run_events` table
- [ ] save/get/list API
- [ ] migration idempotency
- [ ] existing SessionDB tests pass

### 15.3 Phase C Checklist

- [ ] RunLayer protocol
- [ ] layer dispatch order
- [ ] layer exception isolation
- [ ] PersistenceLayer
- [ ] InMemoryEventSink
- [ ] contextvars current graph

### 15.4 Phase D Checklist

- [ ] root run lifecycle in `run_agent.py`
- [ ] model_call node
- [ ] tool_call node
- [ ] error/interrupt path
- [ ] graph disabled path

### 15.5 Phase E Checklist

- [ ] subagent node
- [ ] subagent spawn/completion events
- [ ] active registry includes run/node ids
- [ ] child parent_run_id
- [ ] delegate regression tests

### 15.6 Phase F Checklist

- [ ] run snapshot query
- [ ] recent runs query
- [ ] event tail query
- [ ] TUI gateway RPC
- [ ] snapshot size cap

### 15.7 Phase G Checklist

- [ ] artifact dataclass
- [ ] artifact tables
- [ ] artifact versioning
- [ ] decision log helper
- [ ] benchmark report helper

### 15.8 Phase H Checklist

- [ ] benchmark case node
- [ ] oracle result schema
- [ ] evidence refs
- [ ] sample harness test

### 15.9 Release Checklist

- [ ] P0 tests pass
- [ ] core regression tests pass
- [ ] manual smoke pass
- [ ] feature flag documented
- [ ] PRD acceptance criteria mapped
- [ ] Agent Board UI contract drafted

---

## 16. 구현 순서 추천

1. A1~A5를 한 PR로 완료한다.
2. B1~B6를 두 번째 PR로 완료한다.
3. C1~C4를 세 번째 PR로 완료한다.
4. D1~D5는 `run_agent.py` 회귀 위험이 크므로 가장 작은 diff로 진행한다.
5. E1~E4는 delegate 관련 기존 테스트를 먼저 고정한 뒤 진행한다.
6. F/G/H는 P0가 안정된 후 병렬 subagent 작업으로 나눠도 된다.

## 17. 완료 정의

P0 완료는 다음 문장이 참일 때다.

> “Hermes가 Discord 또는 CLI에서 하나의 요청을 처리하면, 그 실행은 `runs`, `run_nodes`, `run_events`에 저장되고, model call/tool call/subagent 실행의 상태·입력·출력·오류를 조회할 수 있으며, 기존 session/message 기능은 깨지지 않는다.”
