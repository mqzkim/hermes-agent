from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from agent.run_events import sanitize_payload

SCHEMA_VERSION = 1


def _now() -> float:
    return time.time()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class ArtifactType(str, Enum):
    DOCUMENT = "document"
    TABLE = "table"
    CHECKLIST = "checklist"
    DECISION_LOG = "decision_log"
    TASK_TREE = "task_tree"
    BENCHMARK_REPORT = "benchmark_report"
    CODE_PATCH = "code_patch"
    FILE_REFERENCE = "file_reference"


@dataclass(slots=True)
class ArtifactRecord:
    artifact_id: str
    run_id: str
    artifact_type: ArtifactType
    title: str
    content_type: str
    created_at: float
    updated_at: float
    producer_node_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def new(
        cls,
        *,
        run_id: str,
        artifact_type: ArtifactType,
        title: str,
        content_type: str,
        producer_node_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> "ArtifactRecord":
        now = _now()
        return cls(
            artifact_id=_id("art"),
            run_id=run_id,
            artifact_type=artifact_type,
            title=title,
            content_type=content_type,
            producer_node_id=producer_node_id,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
            **kwargs,
        )

    def to_dict(self, *, max_string_length: int = 8192) -> dict[str, Any]:
        data = asdict(self)
        data["artifact_type"] = self.artifact_type.value
        data["metadata"] = sanitize_payload(data["metadata"], max_string_length=max_string_length)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArtifactRecord":
        payload = dict(data)
        payload["artifact_type"] = ArtifactType(payload["artifact_type"])
        return cls(**payload)


@dataclass(slots=True)
class ArtifactVersionRecord:
    version_id: str
    artifact_id: str
    run_id: str
    version: int
    content: dict[str, Any]
    created_at: float
    producer_node_id: str | None = None
    summary: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def new(
        cls,
        *,
        artifact_id: str,
        run_id: str,
        version: int,
        content: dict[str, Any],
        producer_node_id: str | None = None,
        summary: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> "ArtifactVersionRecord":
        return cls(
            version_id=_id("artv"),
            artifact_id=artifact_id,
            run_id=run_id,
            producer_node_id=producer_node_id,
            version=version,
            content=content,
            created_at=_now(),
            summary=summary,
            metadata=metadata or {},
            **kwargs,
        )

    def to_dict(self, *, max_string_length: int = 8192) -> dict[str, Any]:
        data = asdict(self)
        data["content"] = sanitize_payload(data["content"], max_string_length=max_string_length)
        data["metadata"] = sanitize_payload(data["metadata"], max_string_length=max_string_length)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArtifactVersionRecord":
        return cls(**dict(data))


def create_decision_log_artifact(
    *,
    run_id: str,
    producer_node_id: str | None,
    title: str,
    rationale: str,
    alternatives: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[ArtifactRecord, ArtifactVersionRecord]:
    artifact = ArtifactRecord.new(
        run_id=run_id,
        producer_node_id=producer_node_id,
        artifact_type=ArtifactType.DECISION_LOG,
        title=title,
        content_type="application/json",
        metadata=metadata,
    )
    version = ArtifactVersionRecord.new(
        artifact_id=artifact.artifact_id,
        run_id=run_id,
        producer_node_id=producer_node_id,
        version=1,
        content={
            "title": title,
            "rationale": rationale,
            "alternatives": alternatives or [],
        },
        summary="decision recorded",
    )
    return artifact, version


def create_benchmark_report_artifact(
    *,
    run_id: str,
    producer_node_id: str | None,
    case_id: str,
    oracle_name: str,
    passed: bool,
    score: float | None = None,
    failures: list[str] | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[ArtifactRecord, ArtifactVersionRecord]:
    title = f"Benchmark {case_id}"
    artifact = ArtifactRecord.new(
        run_id=run_id,
        producer_node_id=producer_node_id,
        artifact_type=ArtifactType.BENCHMARK_REPORT,
        title=title,
        content_type="application/json",
        metadata=metadata,
    )
    version = ArtifactVersionRecord.new(
        artifact_id=artifact.artifact_id,
        run_id=run_id,
        producer_node_id=producer_node_id,
        version=1,
        content={
            "case_id": case_id,
            "oracle_result": {
                "oracle_name": oracle_name,
                "passed": passed,
                "score": score,
                "failures": failures or [],
                "evidence_refs": evidence_refs or [],
            },
        },
        summary="passed" if passed else "failed",
    )
    return artifact, version
