#!/usr/bin/env python3
"""Fast pre-commit gate for Claude/Codex local-cli delegation changes.

Runs the targeted unit/regression/e2e suite plus a 100% coverage check for the
local CLI adapter. The hook is scoped by .pre-commit-config.yaml `files:` so it
only runs when the local-cli delegation surface changes.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
PERFORMANCE_BUDGET_SECONDS = float(os.environ.get("HERMES_PRECOMMIT_LOCAL_CLI_BUDGET", "45"))


def run(cmd: list[str], *, label: str) -> None:
    print(f"\n== {label} ==")
    print(" ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    started = time.perf_counter()
    run(
        [
            PY,
            "-m",
            "py_compile",
            "agent/local_cli_client.py",
            "tools/delegate_tool.py",
            "run_agent.py",
            "agent/auxiliary_client.py",
            "tests/agent/test_local_cli_client.py",
            "tests/tools/test_delegate.py",
        ],
        label="syntax",
    )
    run(
        [
            PY,
            "-m",
            "pytest",
            "-o",
            "addopts=",
            "tests/agent/test_local_cli_client.py",
            "tests/tools/test_delegate.py::TestExplicitCommandTransport",
            "tests/tools/test_delegate.py::TestDelegationProviderIntegration::test_explicit_claude_command_reaches_child_as_local_cli",
            "tests/tools/test_delegate.py::TestDelegationProviderIntegration::test_explicit_claude_local_cli_delegate_e2e",
            "-q",
        ],
        label="unit/regression/e2e",
    )
    run(
        [
            PY,
            "-m",
            "coverage",
            "run",
            "--source=agent.local_cli_client",
            "-m",
            "pytest",
            "-o",
            "addopts=",
            "tests/agent/test_local_cli_client.py",
            "-q",
        ],
        label="coverage run",
    )
    run(
        [
            PY,
            "-m",
            "coverage",
            "report",
            "--include=agent/local_cli_client.py",
            "--fail-under=100",
            "--show-missing",
        ],
        label="coverage 100%",
    )
    elapsed = time.perf_counter() - started
    print(f"\npre-commit local-cli gate elapsed: {elapsed:.2f}s")
    if elapsed > PERFORMANCE_BUDGET_SECONDS:
        print(
            f"Local-cli gate exceeded performance budget: {elapsed:.2f}s > "
            f"{PERFORMANCE_BUDGET_SECONDS:.2f}s",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
