from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from agent.run_artifacts import ArtifactRecord, ArtifactVersionRecord, create_benchmark_report_artifact
from agent.run_events import RunEventType, RunNodeRecord, RunNodeType, RunStatus, sanitize_payload
from agent.run_graph import RunGraph


@dataclass(slots=True)
class OracleResult:
    oracle_name: str
    passed: bool
    score: float | None = None
    failures: list[str] = field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(
        cls,
        *,
        oracle_name: str,
        passed: bool,
        score: float | None = None,
        failures: list[str] | None = None,
        evidence_refs: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "OracleResult":
        return cls(
            oracle_name=oracle_name,
            passed=passed,
            score=score,
            failures=failures or [],
            evidence_refs=evidence_refs or [],
            metadata=metadata or {},
        )

    def to_dict(self, *, max_string_length: int = 8192) -> dict[str, Any]:
        return sanitize_payload(asdict(self), max_string_length=max_string_length)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OracleResult":
        payload = dict(data)
        payload["failures"] = list(payload.get("failures") or [])
        payload["evidence_refs"] = list(payload.get("evidence_refs") or [])
        payload["metadata"] = dict(payload.get("metadata") or {})
        return cls(**payload)


@dataclass(slots=True)
class BenchmarkCaseRecord:
    node: RunNodeRecord
    oracle_result: OracleResult
    artifact: ArtifactRecord
    version: ArtifactVersionRecord


def _as_oracle_result(value: OracleResult | dict[str, Any]) -> OracleResult:
    if isinstance(value, OracleResult):
        return value
    return OracleResult.from_dict(value)


def record_benchmark_case(
    graph: RunGraph,
    *,
    case_id: str,
    oracle_result: OracleResult | dict[str, Any],
    title: str | None = None,
    parent_node_id: str | None = None,
    inputs: dict[str, Any] | None = None,
    session_db: Any | None = None,
) -> BenchmarkCaseRecord:
    """Record a benchmark case as a RunGraph node plus oracle/report artifact.

    This helper is deliberately thin: benchmark runners keep their own execution
    logic, while Hermes gets a stable RunGraph shape for Agent Board and later
    harness analysis.
    """
    if graph.run is None:
        raise ValueError("record_benchmark_case requires an active RunGraph run")

    oracle = _as_oracle_result(oracle_result)
    event_start = len(graph.events)
    node = graph.start_node(
        RunNodeType.BENCHMARK_CASE,
        title=title or f"Benchmark {case_id}",
        parent_node_id=parent_node_id,
        inputs={"case_id": case_id, **(inputs or {})},
        metadata={"oracle_name": oracle.oracle_name},
    )
    oracle_payload = {"case_id": case_id, **oracle.to_dict()}
    graph.emit(RunEventType.ORACLE_RESULT, node_id=node.node_id, payload=oracle_payload)

    artifact, version = create_benchmark_report_artifact(
        run_id=graph.run.run_id,
        producer_node_id=node.node_id,
        case_id=case_id,
        oracle_name=oracle.oracle_name,
        passed=oracle.passed,
        score=oracle.score,
        failures=oracle.failures,
        evidence_refs=oracle.evidence_refs,
        metadata={"benchmark_case_node_id": node.node_id},
    )
    graph.emit(
        RunEventType.ARTIFACT_CREATED,
        node_id=node.node_id,
        payload={
            "artifact_id": artifact.artifact_id,
            "version_id": version.version_id,
            "artifact_type": artifact.artifact_type.value,
            "case_id": case_id,
        },
    )

    graph.finish_node(
        node.node_id,
        status=RunStatus.SUCCEEDED if oracle.passed else RunStatus.FAILED,
        error=None if oracle.passed else "; ".join(oracle.failures or ["benchmark oracle failed"]),
        outputs={
            "case_id": case_id,
            "oracle_result": oracle.to_dict(),
            "benchmark_report_artifact_id": artifact.artifact_id,
            "benchmark_report_version_id": version.version_id,
        },
    )

    if session_db is not None:
        session_db.save_run_record(graph.run)
        session_db.save_run_node_record(node)
        for event in graph.events[event_start:]:
            session_db.append_run_event_record(event)
        session_db.save_artifact_record(artifact)
        session_db.append_artifact_version_record(version)

    return BenchmarkCaseRecord(node=node, oracle_result=oracle, artifact=artifact, version=version)
