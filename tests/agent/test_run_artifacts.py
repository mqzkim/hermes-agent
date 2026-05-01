import json

from agent.run_artifacts import (
    ArtifactRecord,
    ArtifactType,
    ArtifactVersionRecord,
    create_benchmark_report_artifact,
    create_decision_log_artifact,
)


def test_artifact_records_round_trip_and_sanitize_payloads():
    artifact = ArtifactRecord.new(
        run_id="run-1",
        producer_node_id="node-1",
        artifact_type=ArtifactType.DECISION_LOG,
        title="Decision Log",
        content_type="application/json",
        metadata={"api_key": "secret", "safe": "ok"},
    )
    version = ArtifactVersionRecord.new(
        artifact_id=artifact.artifact_id,
        run_id="run-1",
        producer_node_id="node-1",
        version=1,
        content={"token": "secret", "items": [object()]},
        summary="initial",
    )

    artifact_dict = artifact.to_dict()
    version_dict = version.to_dict()

    assert artifact_dict["artifact_type"] == "decision_log"
    assert artifact_dict["metadata"]["api_key"] == "[REDACTED]"
    assert version_dict["content"]["token"] == "[REDACTED]"
    assert isinstance(version_dict["content"]["items"][0], str)
    json.dumps(artifact_dict)
    json.dumps(version_dict)
    assert ArtifactRecord.from_dict(artifact_dict) == ArtifactRecord.from_dict(artifact_dict)
    assert ArtifactVersionRecord.from_dict(version_dict) == ArtifactVersionRecord.from_dict(version_dict)


def test_decision_log_helper_builds_artifact_and_initial_version():
    artifact, version = create_decision_log_artifact(
        run_id="run-1",
        producer_node_id="node-1",
        title="Use RunGraph",
        rationale="Need structured evidence",
        alternatives=["plain transcript", "logs only"],
        metadata={"source": "test"},
    )

    assert artifact.artifact_type == ArtifactType.DECISION_LOG
    assert artifact.title == "Use RunGraph"
    assert version.version == 1
    assert version.content["title"] == "Use RunGraph"
    assert version.content["rationale"] == "Need structured evidence"
    assert version.content["alternatives"] == ["plain transcript", "logs only"]


def test_benchmark_report_helper_builds_artifact_and_initial_version():
    artifact, version = create_benchmark_report_artifact(
        run_id="run-1",
        producer_node_id="node-1",
        case_id="case-1",
        oracle_name="pytest",
        passed=False,
        score=0.5,
        failures=["missing artifact"],
        evidence_refs=[{"node_id": "node-1"}],
    )

    assert artifact.artifact_type == ArtifactType.BENCHMARK_REPORT
    assert artifact.title == "Benchmark case-1"
    assert version.content["case_id"] == "case-1"
    assert version.content["oracle_result"]["passed"] is False
    assert version.content["oracle_result"]["failures"] == ["missing artifact"]
