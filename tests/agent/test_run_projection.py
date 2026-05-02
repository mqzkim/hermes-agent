from agent.run_events import RunEventType, RunNodeType, RunStatus
from agent.run_graph import RunGraph
from agent.run_projection import RunProjection


def test_run_projection_summarizes_running_active_node_and_evidence():
    graph = RunGraph.start(
        session_id="s1",
        source="discord:#ceo-office",
        root_goal="전사 RunGraph 적용",
        metadata={"origin": {"platform": "discord", "thread_id": "t1"}},
    )
    node = graph.start_node(
        RunNodeType.TOOL_CALL,
        title="schema gate",
        inputs={"command": "pytest"},
    )
    graph.emit(
        RunEventType.TOOL_RESULT,
        node_id=node.node_id,
        payload={"artifact_path": "/tmp/result.json", "verification": "schema"},
    )

    projection = RunProjection.from_graph(graph)

    assert projection.run_id == graph.run.run_id
    assert projection.status == "running"
    assert projection.phase == "execute"
    assert projection.active_node_ids == [node.node_id]
    assert projection.evidence_count == 1
    assert projection.evidence_paths == ["/tmp/result.json"]
    assert projection.blocked_reason is None
    assert projection.next_action == "wait_for_active_nodes"


def test_run_projection_marks_failed_run_as_blocked_with_reason():
    graph = RunGraph.start(session_id="s1", source="cron", root_goal="worker probe")
    node = graph.start_node(RunNodeType.SUBAGENT, title="worker")
    graph.finish_node(node.node_id, error="worker heartbeat stale")
    graph.finish_run(error="worker heartbeat stale", status=RunStatus.FAILED)

    projection = RunProjection.from_graph(graph)

    assert projection.status == "failed"
    assert projection.phase == "recover"
    assert projection.active_node_ids == []
    assert projection.blocked_reason == "worker heartbeat stale"
    assert projection.next_action == "recover_or_escalate"


def test_run_projection_round_trips_to_dict():
    graph = RunGraph.start(session_id="s1", source="cli", root_goal="inspect")

    data = RunProjection.from_graph(graph).to_dict()

    assert data["run_id"] == graph.run.run_id
    assert data["goal"] == "inspect"
    assert data["schema_version"] == 1
