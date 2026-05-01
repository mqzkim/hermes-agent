import json

from agent.run_artifacts import ArtifactRecord, ArtifactType, ArtifactVersionRecord
from agent.run_events import RunEventRecord, RunEventType, RunNodeRecord, RunNodeType, RunRecord
from hermes_state import SessionDB


def test_run_graph_tables_created(tmp_path):
    db = SessionDB(tmp_path / "state.db")
    try:
        rows = db._conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        names = {row[0] for row in rows}
        assert "runs" in names
        assert "run_nodes" in names
        assert "run_events" in names
        assert "artifacts" in names
        assert "artifact_versions" in names
    finally:
        db.close()


def test_run_node_and_event_records_round_trip(tmp_path):
    db = SessionDB(tmp_path / "state.db")
    try:
        db.create_session(session_id="s1", source="discord")
        run = RunRecord.new(session_id="s1", source="discord", root_goal="analyze", metadata={"api_key": "secret"})
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
            event_type=RunEventType.TOOL_RESULT,
            payload={"stdout": "/tmp"},
            sequence=1,
        )

        db.save_run_record(run)
        db.save_run_node_record(node)
        db.append_run_event_record(event)

        loaded_run = db.get_run_record(run.run_id)
        loaded_nodes = db.list_run_node_records(run.run_id)
        loaded_events = db.list_run_event_records(run.run_id)

        assert loaded_run == RunRecord.from_dict({**run.to_dict(), "metadata": {"api_key": "[REDACTED]"}})
        assert db.list_recent_runs(limit=1)[0].run_id == run.run_id
        assert loaded_nodes == [node]
        assert loaded_events == [event]
    finally:
        db.close()


def test_run_event_tail_filters_after_sequence_and_redacts_payload(tmp_path):
    db = SessionDB(tmp_path / "state.db")
    try:
        run = RunRecord.new(session_id=None, source="cli", root_goal="tail")
        db.save_run_record(run)
        first = RunEventRecord.new(
            run_id=run.run_id,
            event_type=RunEventType.MODEL_REQUEST,
            payload={"api_key": "secret", "prompt": "hello"},
            sequence=1,
        )
        second = RunEventRecord.new(
            run_id=run.run_id,
            event_type=RunEventType.MODEL_RESPONSE,
            payload={"text": "world"},
            sequence=2,
        )
        db.append_run_event_record(first)
        db.append_run_event_record(second)

        all_events = db.list_run_event_records(run.run_id)
        tail = db.list_run_event_records(run.run_id, after_sequence=1)

        assert all_events[0].payload == {"api_key": "[REDACTED]", "prompt": "hello"}
        assert tail == [second]
    finally:
        db.close()


def test_run_graph_snapshot_returns_json_contract_with_tree_and_limited_events(tmp_path):
    db = SessionDB(tmp_path / "state.db")
    try:
        db.create_session(session_id="session-1", source="test")
        run = RunRecord.new(
            session_id="session-1",
            source="test",
            root_goal="inspect orchestration",
            model="model-a",
            provider="provider-a",
        )
        parent = RunNodeRecord.new(
            run_id=run.run_id,
            node_type=RunNodeType.AGENT_TURN,
            title="parent",
            parent_node_id=None,
            inputs={"password": "secret"},
        )
        child = RunNodeRecord.new(
            run_id=run.run_id,
            node_type=RunNodeType.TOOL_CALL,
            title="child",
            parent_node_id=parent.node_id,
            inputs={"tool": "terminal"},
        )
        db.save_run_record(run)
        db.save_run_node_record(parent)
        db.save_run_node_record(child)
        db.append_run_event_record(
            RunEventRecord.new(
                run_id=run.run_id,
                event_type=RunEventType.RUN_STARTED,
                sequence=1,
                payload={"step": 1},
            )
        )
        db.append_run_event_record(
            RunEventRecord.new(
                run_id=run.run_id,
                node_id=parent.node_id,
                event_type=RunEventType.NODE_STARTED,
                sequence=2,
                payload={"token": "secret"},
            )
        )

        snapshot = db.get_run_graph_snapshot(run.run_id, events_limit=1)

        assert snapshot is not None
        assert snapshot["run"]["run_id"] == run.run_id
        assert [node["node_id"] for node in snapshot["nodes"]] == [parent.node_id, child.node_id]
        assert snapshot["node_tree"][0]["node_id"] == parent.node_id
        assert snapshot["node_tree"][0]["children"][0]["node_id"] == child.node_id
        assert snapshot["events_tail"][0]["sequence"] == 2
        assert snapshot["events_tail"][0]["payload"]["token"] == "[REDACTED]"
        assert snapshot["artifacts"] == []
        json.dumps(snapshot)
    finally:
        db.close()


def test_run_graph_snapshot_returns_none_for_missing_run(tmp_path):
    db = SessionDB(tmp_path / "state.db")
    try:
        assert db.get_run_graph_snapshot("missing-run") is None
    finally:
        db.close()


def test_artifact_records_round_trip_and_snapshot_includes_latest_versions(tmp_path):
    db = SessionDB(tmp_path / "state.db")
    try:
        run = RunRecord.new(session_id=None, source="cli", root_goal="artifacts")
        db.save_run_record(run)
        artifact = ArtifactRecord.new(
            run_id=run.run_id,
            producer_node_id=None,
            artifact_type=ArtifactType.DOCUMENT,
            title="Plan",
            content_type="text/markdown",
            metadata={"token": "secret"},
        )
        v1 = ArtifactVersionRecord.new(
            artifact_id=artifact.artifact_id,
            run_id=run.run_id,
            producer_node_id=None,
            version=1,
            content={"body": "draft"},
            summary="draft",
        )
        v2 = ArtifactVersionRecord.new(
            artifact_id=artifact.artifact_id,
            run_id=run.run_id,
            producer_node_id=None,
            version=2,
            content={"body": "final", "password": "secret"},
            summary="final",
        )

        db.save_artifact_record(artifact)
        db.append_artifact_version_record(v1)
        db.append_artifact_version_record(v2)

        loaded_artifacts = db.list_artifact_records(run.run_id)
        loaded_versions = db.list_artifact_version_records(artifact.artifact_id)
        latest = db.get_latest_artifact_version_record(artifact.artifact_id)
        snapshot = db.get_run_graph_snapshot(run.run_id)

        assert len(loaded_artifacts) == 1
        assert loaded_artifacts[0].artifact_id == artifact.artifact_id
        assert loaded_artifacts[0].metadata["token"] == "[REDACTED]"
        assert loaded_artifacts[0].updated_at >= artifact.updated_at
        assert [version.version for version in loaded_versions] == [1, 2]
        assert latest.version == 2
        assert latest.content["password"] == "[REDACTED]"
        assert snapshot["artifacts"][0]["artifact_id"] == artifact.artifact_id
        assert snapshot["artifacts"][0]["latest_version"]["version"] == 2
        assert snapshot["artifacts"][0]["latest_version"]["content"]["body"] == "final"
        json.dumps(snapshot)
    finally:
        db.close()


def test_run_graph_schema_is_idempotent(tmp_path):
    db_path = tmp_path / "state.db"
    first = SessionDB(db_path)
    first.close()

    second = SessionDB(db_path)
    try:
        version = second._conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()[0]
        assert version >= 10
        rows = second._conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        names = {row[0] for row in rows}
        assert {"runs", "run_nodes", "run_events", "artifacts", "artifact_versions"}.issubset(names)
    finally:
        second.close()
