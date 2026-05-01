# Agent Board Run Graph UI Contract

Date: 2026-04-25
Status: MVP contract for Phase F

## 1. Purpose

This document fixes the minimal JSON contract that Agent Board, TUI, and gateway views can use to render Hermes Run Graph data without knowing internal Python dataclasses.

The contract is intentionally read-only for Phase F. Control actions such as pause, resume, retry, or node replay are future extensions.

## 2. RPC / Query Surface

### 2.1 `runs.list_recent`

Request:

```json
{
  "limit": 20
}
```

Response:

```json
{
  "runs": [
    {
      "run_id": "run_...",
      "session_id": "...",
      "source": "discord",
      "root_goal": "short goal preview",
      "status": "running",
      "started_at": 1760000000.0,
      "ended_at": null,
      "parent_run_id": null,
      "model": "...",
      "provider": "...",
      "metadata": {},
      "schema_version": 1
    }
  ]
}
```

### 2.2 `runs.get_snapshot`

Request:

```json
{
  "run_id": "run_...",
  "limit": 200
}
```

Response:

```json
{
  "run": {},
  "nodes": [],
  "node_tree": [],
  "events_tail": [],
  "artifacts": []
}
```

Missing run error:

```json
{
  "code": 4041,
  "message": "run not found: run_..."
}
```

### 2.3 `runs.events_tail`

Request:

```json
{
  "run_id": "run_...",
  "limit": 200,
  "after_sequence": 42
}
```

Response:

```json
{
  "events": []
}
```

`after_sequence` is optional. When present, the server returns events with sequence greater than the supplied value.

## 3. Panel Contracts

### 3.1 Run Tree Panel

Source field: `node_tree`

Each tree item is a `RunNodeRecord` dictionary plus `children`:

```json
{
  "node_id": "node_...",
  "run_id": "run_...",
  "parent_node_id": null,
  "node_type": "model_call",
  "title": "model call #1",
  "status": "succeeded",
  "started_at": 1760000000.0,
  "ended_at": 1760000001.0,
  "inputs": {},
  "outputs": {},
  "error": null,
  "metadata": {},
  "schema_version": 1,
  "children": []
}
```

Required UI behavior:

- Render `status` as the primary state badge.
- Render `node_type` as the structural category.
- Preserve child order as supplied.
- Do not assume every node has a parent; orphaned nodes are roots.

### 3.2 Event Timeline Panel

Source field: `events_tail`

Each event is a `RunEventRecord` dictionary:

```json
{
  "event_id": "evt_...",
  "run_id": "run_...",
  "node_id": "node_...",
  "event_type": "tool_result",
  "timestamp": 1760000001.0,
  "sequence": 12,
  "payload": {},
  "schema_version": 1
}
```

Required UI behavior:

- Use `sequence` as the primary ordering key.
- Incremental refresh should call `runs.events_tail` with the latest seen `sequence`.
- Display payload only in an inspector/detail area, not as the primary row label.

### 3.3 Artifact Pane

Source field: `artifacts`

Each artifact item is an `ArtifactRecord` dictionary plus `latest_version`:

```json
{
  "artifact_id": "art_...",
  "run_id": "run_...",
  "producer_node_id": "node_...",
  "artifact_type": "decision_log",
  "title": "Use RunGraph",
  "content_type": "application/json",
  "created_at": 1760000000.0,
  "updated_at": 1760000001.0,
  "metadata": {},
  "schema_version": 1,
  "latest_version": {
    "version_id": "artv_...",
    "artifact_id": "art_...",
    "run_id": "run_...",
    "producer_node_id": "node_...",
    "version": 2,
    "content": {},
    "created_at": 1760000001.0,
    "summary": "final",
    "metadata": {},
    "schema_version": 1
  }
}
```

MVP UI behavior:

- Show an empty-state message when `artifacts` is empty.
- Do not treat missing artifacts as an error.
- Select artifact rows by `artifact_type`, `title`, and `latest_version.summary`.
- Render `latest_version.content` in the inspector pane.

### 3.4 Inspector Panel

Source fields:

- selected run: `run`
- selected node: item from `nodes` or `node_tree`
- selected event: item from `events_tail`

Required UI behavior:

- Render raw JSON after redaction already applied by backend.
- Do not attempt client-side secret recovery or hidden raw payload expansion.
- Display `error` fields prominently for failed nodes/runs.

## 4. Controls Matrix

Phase F controls are display-only.

| Control | Enabled in Phase F | Reason |
| --- | --- | --- |
| Run list refresh | Yes | Read-only |
| Snapshot refresh | Yes | Read-only |
| Event tail refresh | Yes | Read-only |
| Pause run | No | Pause state not wired yet |
| Resume run | No | Command channel not wired yet |
| Retry node | No | Replay contract not implemented |
| Stop subagent | Existing delegation UI only | Separate existing flow |

## 5. Safety / Stability Requirements

- All payloads must be JSON serializable.
- Secret-like keys are redacted before persistence and before UI delivery.
- Snapshot event tail is bounded by `limit`.
- TUI bridge clamps `limit` to prevent oversized responses.
- Missing run must return a stable explicit error, not an empty successful snapshot.
