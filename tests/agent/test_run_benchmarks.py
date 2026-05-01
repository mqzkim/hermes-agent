import json

from agent.run_artifacts import ArtifactType
from agent.run_benchmarks import OracleResult, record_benchmark_case
from agent.run_events import RunEventType, RunNodeType, RunStatus
from agent.run_graph import RunGraph
from hermes_state import SessionDB


def test_oracle_result_round_trip_sanitizes_and_is_json_safe():
    result = OracleResult.new(
        oracle_name="pytest",
        passed=False,
        score=0.25,
        failures=["coverage below target"],
        evidence_refs=[{"node_id": "node-1", "api_key": "secret"}],
        metadata={"token": "secret", "obj": object()},
    )

    data = result.to_dict()

    assert data["oracle_name"] == "pytest"
    assert data["passed"] is False
    assert data["evidence_refs"][0]["api_key"] == "[REDACTED]"
    assert data["metadata"]["token"] == "[REDACTED]"
    assert isinstance(data["metadata"]["obj"], str)
    json.dumps(data)
    assert OracleResult.from_dict(data).oracle_name == "pytest"


def test_record_benchmark_case_creates_node_oracle_event_and_report_artifact():
    graph = RunGraph.start(session_id=None, source="test", root_goal="benchmark")
    oracle = OracleResult.new(
        oracle_name="unit-oracle",
        passed=False,
        score=0.0,
        failures=["expected artifact missing"],
        evidence_refs=[{"node_id": "node-evidence"}],
    )

    result = record_benchmark_case(graph, case_id="case-1", oracle_result=oracle)

    assert result.node.node_type == RunNodeType.BENCHMARK_CASE
    assert result.node.status == RunStatus.FAILED
    assert result.node.outputs["oracle_result"]["passed"] is False
    assert result.artifact.artifact_type == ArtifactType.BENCHMARK_REPORT
    assert result.version.content["case_id"] == "case-1"
    assert result.version.content["oracle_result"]["evidence_refs"] == [{"node_id": "node-evidence"}]
    event_types = [event.event_type for event in graph.events]
    assert RunEventType.ORACLE_RESULT in event_types
    assert RunEventType.ARTIFACT_CREATED in event_types


def test_record_benchmark_case_persists_snapshot_evidence_refs(tmp_path):
    graph = RunGraph.start(session_id=None, source="test", root_goal="benchmark")
    db = SessionDB(tmp_path / "state.db")
    try:
        oracle = OracleResult.new(
            oracle_name="pytest",
            passed=True,
            score=1.0,
            failures=[],
            evidence_refs=[{"run_id": graph.run.run_id}],
        )

        result = record_benchmark_case(
            graph,
            case_id="case-pass",
            oracle_result=oracle,
            session_db=db,
        )
        snapshot = db.get_run_graph_snapshot(graph.run.run_id)

        assert snapshot["nodes"][0]["node_type"] == "benchmark_case"
        assert snapshot["nodes"][0]["status"] == "succeeded"
        assert any(event["event_type"] == "oracle_result" for event in snapshot["events_tail"])
        assert snapshot["artifacts"][0]["artifact_id"] == result.artifact.artifact_id
        assert snapshot["artifacts"][0]["latest_version"]["content"]["oracle_result"]["passed"] is True
        assert snapshot["artifacts"][0]["latest_version"]["content"]["oracle_result"]["evidence_refs"] == [
            {"run_id": graph.run.run_id}
        ]
    finally:
        db.close()
