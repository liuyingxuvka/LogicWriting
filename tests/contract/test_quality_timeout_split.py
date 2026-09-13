from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_writing_quality_benchmark as benchmark


def test_job_timeout_is_distinct_from_backend_timeout(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": "logic-writing.local-backend-plan.v1",
                "backend_id": "local-codex:0.154.0:gpt-6-astra:xhigh",
                "model_id": "gpt-6-astra",
                "reasoning_effort": "xhigh",
                "cli_version": "0.154.0",
                "cli_sha256": benchmark.DEFAULT_CLI_SHA256,
                "timeout_seconds": 900,
                "job_timeout_seconds": 1800,
                "max_attempts": 1,
                "concurrency": 2,
                "startup_timeout_seconds": 60,
                "no_progress_seconds": 0,
            }
        ),
        encoding="utf-8",
    )

    plan = benchmark._load_plan(plan_path, source_manifest_fp="sha256:test")

    assert plan["timeout_seconds"] == 900
    assert plan["job_timeout_seconds"] == 1800
    policy = benchmark._execution_policy(plan)
    assert policy["timeout_seconds"] == 900
    assert policy["job_timeout_seconds"] == 1800
    assert benchmark._orchestration_timeout(plan, 3) == 3600


def test_legacy_plan_falls_back_without_changing_current_semantics() -> None:
    legacy = {"timeout_seconds": 7, "concurrency": 2}
    assert benchmark._orchestration_timeout(legacy, 3) == 14
