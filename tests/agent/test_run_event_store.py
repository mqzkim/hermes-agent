from agent.run_event_store import RunEventStore
from agent.run_events import RunEventRecord, RunEventType, RunNodeRecord, RunNodeType, RunRecord


def test_run_event_store_appends_and_replays_run_aggregate(tmp_path):
    store = RunEventStore(tmp_path / "run_events.db")
    run = RunRecord.new(session_id="s1", source="discord", root_goal="전사 ledger 구축")
    node = RunNodeRecord.new(
        run_id=run.run_id,
        node_type=RunNodeType.TOOL_CALL,
        title="pytest",
        parent_node_id=None,
        inputs={"command": "pytest", "api_token": "secret-value"},
    )
    started = RunEventRecord.new(
        run_id=run.run_id,
        node_id=node.node_id,
        event_type=RunEventType.NODE_STARTED,
        payload={"authorization": "Bearer secret", "phase": "execute"},
    )

    store.append_run(run)
    store.append_node(node)
    store.append_event(started)

    loaded_run = store.get_run(run.run_id)
    loaded_nodes = store.list_nodes(run.run_id)
    loaded_events = store.list_events(run.run_id)

    assert loaded_run is not None
    assert loaded_run.root_goal == "전사 ledger 구축"
    assert loaded_nodes[0].node_id == node.node_id
    assert loaded_nodes[0].inputs["api_token"] == "[REDACTED]"
    assert loaded_events[0].event_type == RunEventType.NODE_STARTED
    assert loaded_events[0].payload["authorization"] == "[REDACTED]"


def test_run_event_store_replay_orders_events_by_sequence_then_timestamp(tmp_path):
    store = RunEventStore(tmp_path / "run_events.db")
    run = RunRecord.new(session_id="s1", source="cron", root_goal="nightly check")
    later = RunEventRecord.new(
        run_id=run.run_id,
        event_type=RunEventType.RUN_SUCCEEDED,
        sequence=2,
    )
    earlier = RunEventRecord.new(
        run_id=run.run_id,
        event_type=RunEventType.RUN_STARTED,
        sequence=1,
    )

    store.append_run(run)
    store.append_event(later)
    store.append_event(earlier)

    assert [event.event_type for event in store.list_events(run.run_id)] == [
        RunEventType.RUN_STARTED,
        RunEventType.RUN_SUCCEEDED,
    ]
