from agent.run_events import (
    RunEventRecord,
    RunEventType,
    RunNodeRecord,
    RunNodeType,
    RunRecord,
    RunStatus,
)


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
    assert RunEventType.ORACLE_RESULT.value == "oracle_result"


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


def test_record_to_dict_sanitizes_secrets_and_non_json_values_without_mutating_input():
    secret_payload = {
        "api_key": "sk-test",
        "nested": {"authorization": "Bearer token"},
        "raw": b"bytes-value",
        "long": "x" * 20,
    }
    node = RunNodeRecord.new(
        run_id="run_1",
        node_type=RunNodeType.TOOL_CALL,
        title="secret tool",
        parent_node_id=None,
        inputs=secret_payload,
    )

    data = node.to_dict(max_string_length=12)

    assert data["inputs"]["api_key"] == "[REDACTED]"
    assert data["inputs"]["nested"]["authorization"] == "[REDACTED]"
    assert data["inputs"]["raw"] == "bytes-value"
    assert data["inputs"]["long"] == "xxxxxxxxxxxx...[truncated]"
    assert secret_payload["api_key"] == "sk-test"
