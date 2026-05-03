from __future__ import annotations

from typing import Any

_READ_ONLY_REASON = "rungraph_controls_read_only_contract"


def _disabled_action(label: str, *, eligible_node_count: int = 0) -> dict[str, Any]:
    return {
        "label": label,
        "enabled": False,
        "reason": _READ_ONLY_REASON,
        "eligible_node_count": eligible_node_count,
    }


def build_run_operator_controls(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return the explicit read-only RunGraph operator control contract.

    The current RunGraph API is observational. Exposing a stable disabled
    matrix lets TUI/Board clients render retry/replay/pause affordances without
    implying that unsafe mutation contracts already exist.
    """

    run = snapshot.get("run") or {}
    nodes = snapshot.get("nodes") or []
    failed_nodes = [node for node in nodes if (node.get("status") or "").lower() == "failed"]
    failed_node_ids = [node.get("node_id") for node in failed_nodes if node.get("node_id")]

    return {
        "run_id": run.get("run_id"),
        "run_status": run.get("status"),
        "read_only": True,
        "reason": _READ_ONLY_REASON,
        "failed_node_count": len(failed_nodes),
        "failed_node_ids": failed_node_ids,
        "actions": {
            "retry_failed_nodes": _disabled_action(
                "Retry failed nodes",
                eligible_node_count=len(failed_nodes),
            ),
            "replay_run": _disabled_action("Replay run"),
            "pause_run": _disabled_action("Pause run"),
            "resume_run": _disabled_action("Resume run"),
            "cancel_run": _disabled_action("Cancel run"),
        },
    }
