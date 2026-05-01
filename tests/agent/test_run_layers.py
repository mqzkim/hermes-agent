import logging

from agent.run_events import RunEventType, RunNodeType
from agent.run_graph import RunGraph
from agent.run_layers import InMemoryEventSink, PersistenceLayer, RunLayerDispatcher, current_run_graph, run_graph_context
from hermes_state import SessionDB


class RecordingLayer:
    def __init__(self):
        self.calls = []

    def on_run_start(self, graph, run):
        self.calls.append(("run_start", run.run_id))

    def on_node_start(self, graph, node):
        self.calls.append(("node_start", node.node_id))

    def on_event(self, graph, event):
        self.calls.append(("event", event.event_type.value))

    def on_node_end(self, graph, node):
        self.calls.append(("node_end", node.node_id))

    def on_run_end(self, graph, run):
        self.calls.append(("run_end", run.run_id))


class FailingLayer:
    def on_run_start(self, graph, run):
        raise RuntimeError("boom")

    def on_node_start(self, graph, node):
        raise RuntimeError("boom")

    def on_event(self, graph, event):
        raise RuntimeError("boom")

    def on_node_end(self, graph, node):
        raise RuntimeError("boom")

    def on_run_end(self, graph, run):
        raise RuntimeError("boom")


def test_run_layer_dispatcher_preserves_order_and_isolates_layer_errors(caplog):
    graph = RunGraph.start(session_id="s1", source="cli", root_goal="layers")
    node = graph.start_node(RunNodeType.TOOL_CALL, title="terminal")
    event = graph.events[-1]
    good = RecordingLayer()
    dispatcher = RunLayerDispatcher([FailingLayer(), good])

    with caplog.at_level(logging.WARNING):
        dispatcher.on_run_start(graph, graph.run)
        dispatcher.on_node_start(graph, node)
        dispatcher.on_event(graph, event)
        graph.finish_node(node.node_id)
        dispatcher.on_node_end(graph, graph.nodes[node.node_id])
        graph.finish_run()
        dispatcher.on_run_end(graph, graph.run)

    assert [call[0] for call in good.calls] == ["run_start", "node_start", "event", "node_end", "run_end"]
    assert "Run graph layer FailingLayer failed during on_run_start" in caplog.text


def test_persistence_layer_saves_run_node_and_events(tmp_path):
    db = SessionDB(tmp_path / "state.db")
    try:
        graph = RunGraph.start(session_id=None, source="cli", root_goal="persist")
        node = graph.start_node(RunNodeType.TOOL_CALL, title="terminal", inputs={"command": "pwd"})
        layer = PersistenceLayer(db)

        layer.on_run_start(graph, graph.run)
        layer.on_node_start(graph, node)
        layer.on_event(graph, graph.events[0])
        layer.on_event(graph, graph.events[1])
        graph.finish_node(node.node_id, outputs={"stdout": "/tmp"})
        layer.on_node_end(graph, graph.nodes[node.node_id])
        layer.on_event(graph, graph.events[-1])
        graph.finish_run(outputs={"answer": "done"})
        layer.on_run_end(graph, graph.run)
        layer.on_event(graph, graph.events[-1])

        assert db.get_run_record(graph.run.run_id).status == graph.run.status
        assert db.list_run_node_records(graph.run.run_id)[0].outputs == {"stdout": "/tmp"}
        assert [event.event_type for event in db.list_run_event_records(graph.run.run_id)] == [
            RunEventType.RUN_STARTED,
            RunEventType.NODE_STARTED,
            RunEventType.NODE_SUCCEEDED,
            RunEventType.RUN_SUCCEEDED,
        ]
    finally:
        db.close()


def test_in_memory_event_sink_keeps_bounded_tail_per_run():
    graph = RunGraph.start(session_id=None, source="cli", root_goal="sink")
    sink = InMemoryEventSink(max_events_per_run=2)

    for event in graph.events:
        sink.on_event(graph, event)
    node = graph.start_node(RunNodeType.TOOL_CALL, title="terminal")
    sink.on_event(graph, graph.events[-1])
    graph.finish_node(node.node_id)
    sink.on_event(graph, graph.events[-1])

    assert [event.event_type for event in sink.tail(graph.run.run_id)] == [
        RunEventType.NODE_STARTED,
        RunEventType.NODE_SUCCEEDED,
    ]


def test_run_graph_context_sets_and_restores_current_graph():
    graph = RunGraph.start(session_id=None, source="cli", root_goal="ctx")

    assert current_run_graph() is None
    with run_graph_context(graph):
        assert current_run_graph() is graph
    assert current_run_graph() is None
