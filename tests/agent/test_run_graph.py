from agent.run_events import RunEventType, RunNodeType, RunStatus
from agent.run_graph import NoopRunGraph, RunGraph


def test_run_graph_records_lifecycle_events_and_node_tree():
    graph = RunGraph.start(session_id="s1", source="cli", root_goal="inspect repo")
    node = graph.start_node(RunNodeType.TOOL_CALL, title="terminal", inputs={"command": "pwd"})

    graph.finish_node(node.node_id, outputs={"stdout": "/tmp"})
    graph.finish_run(outputs={"answer": "done"})

    assert graph.run is not None
    assert graph.run.status == RunStatus.SUCCEEDED
    assert graph.nodes[node.node_id].status == RunStatus.SUCCEEDED
    assert graph.nodes[node.node_id].outputs["stdout"] == "/tmp"
    assert [event.sequence for event in graph.events] == [1, 2, 3, 4]
    assert [event.event_type for event in graph.events] == [
        RunEventType.RUN_STARTED,
        RunEventType.NODE_STARTED,
        RunEventType.NODE_SUCCEEDED,
        RunEventType.RUN_SUCCEEDED,
    ]
    assert graph.node_tree()[0].node_id == node.node_id


def test_run_graph_supports_parent_child_nodes():
    graph = RunGraph.start(session_id="s1", source="cli", root_goal="delegate")
    parent = graph.start_node(RunNodeType.SUBAGENT, title="reviewer")
    child = graph.start_node(RunNodeType.TOOL_CALL, title="read_file", parent_node_id=parent.node_id)

    tree = graph.node_tree()

    assert tree[0].node_id == parent.node_id
    assert tree[0].children[0].node_id == child.node_id


def test_noop_run_graph_accepts_calls_without_recording():
    graph = NoopRunGraph()

    node = graph.start_node(RunNodeType.TOOL_CALL, title="terminal")
    graph.finish_node(node.node_id, outputs={"stdout": "ignored"})
    graph.finish_run()

    assert graph.run is None
    assert graph.nodes == {}
    assert graph.events == []
