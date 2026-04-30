#!/usr/bin/env python3
"""Fast pre-commit gate for cron/gateway memory availability regressions."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
PERFORMANCE_BUDGET_SECONDS = float(os.environ.get("HERMES_PRECOMMIT_MEMORY_GATE_BUDGET", "40"))


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
            "run_agent.py",
            "cron/scheduler.py",
            "gateway/run.py",
            "tests/agent/test_memory_prompt_suppression.py",
            "tests/gateway/test_agent_cache_memory_config.py",
            "tests/cron/test_scheduler.py",
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
            "tests/agent/test_memory_prompt_suppression.py",
            "tests/gateway/test_agent_cache_memory_config.py",
            "tests/cron/test_scheduler.py::TestRunJobSessionPersistence::test_run_job_passes_session_db_and_cron_platform",
            "-q",
        ],
        label="unit/regression/e2e",
    )
    elapsed = time.perf_counter() - started
    print(f"\npre-commit memory gate elapsed: {elapsed:.2f}s")
    if elapsed > PERFORMANCE_BUDGET_SECONDS:
        print(
            f"Memory gate exceeded performance budget: {elapsed:.2f}s > "
            f"{PERFORMANCE_BUDGET_SECONDS:.2f}s",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
