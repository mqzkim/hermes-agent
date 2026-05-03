from agent.run_controls import build_run_operator_controls


def test_build_run_operator_controls_is_read_only_with_failed_node_signal():
    snapshot = {
        "run": {"run_id": "run_1", "status": "failed"},
        "nodes": [
            {"node_id": "n1", "node_type": "model_call", "status": "failed"},
            {"node_id": "n2", "node_type": "tool_call", "status": "succeeded"},
        ],
    }

    controls = build_run_operator_controls(snapshot)

    assert controls["run_id"] == "run_1"
    assert controls["read_only"] is True
    assert controls["failed_node_count"] == 1
    assert controls["failed_node_ids"] == ["n1"]
    assert controls["actions"]["retry_failed_nodes"]["enabled"] is False
    assert controls["actions"]["retry_failed_nodes"]["eligible_node_count"] == 1
    assert controls["actions"]["retry_failed_nodes"]["reason"] == "rungraph_controls_read_only_contract"
    assert controls["actions"]["replay_run"]["enabled"] is False
    assert controls["actions"]["pause_run"]["enabled"] is False
    assert controls["actions"]["resume_run"]["enabled"] is False
    assert controls["actions"]["cancel_run"]["enabled"] is False
