from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"


def _load(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"lw_{name}_opt_in", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_execution_requires_a_positive_finite_budget(tmp_path):
    benchmark = _load("run_writing_quality_benchmark")
    for value in (None, 0, -1):
        with pytest.raises(ValueError, match="positive --max-model-calls"):
            benchmark.run_benchmark(
                ROOT,
                output_dir=tmp_path / f"run-{value}",
                execute_live=True,
                max_model_calls=value,
            )


def test_default_and_explicit_stage_runs_do_not_dispatch_without_execute_live(tmp_path):
    benchmark = _load("run_writing_quality_benchmark")
    calls: list[dict] = []

    def spy(_request):
        calls.append(_request)
        raise AssertionError("live backend must not be called without --execute-live")

    result = benchmark.run_benchmark(
        ROOT,
        output_dir=tmp_path / "default",
        backend=spy,
        run_writers=True,
        run_judges=True,
        execute_live=False,
    )
    assert result["status"] == "not_run"
    assert result["terminal_reason"] == "live_execution_not_authorized"
    assert calls == []


def test_budget_counts_failed_attempts_and_is_thread_safe():
    benchmark = _load("run_writing_quality_benchmark")
    budget = benchmark.ModelCallBudget(1)
    budget.consume("writer", "writer:test")
    with pytest.raises(benchmark.ValidationError, match="model_call_budget_exhausted"):
        budget.consume("judge", "judge:test")
    snapshot = budget.snapshot()
    assert snapshot["used"] == 1
    assert snapshot["remaining"] == 0
    assert [row["request_id"] for row in snapshot["attempts"]] == ["writer:test"]


def test_nested_planner_path_uses_the_same_budget_before_backend_dispatch():
    benchmark = _load("run_writing_quality_benchmark")

    class Backend:
        def __init__(self):
            self.calls = 0

        def run(self, *_args, **_kwargs):
            self.calls += 1
            raise AssertionError("planner backend must not be called after budget exhaustion")

    backend = Backend()
    budget = benchmark.ModelCallBudget(1)
    budget.consume("writer", "writer:reserved")
    planner = benchmark._production_planner_backend(
        backend,
        token="nested",
        call_budget=budget,
    )
    inputs = {
        "writing_request": {"reader_intent": {}},
        "content_boundaries": {"content_units": [{"safe_meaning": "冻结材料"}]},
    }
    with pytest.raises(benchmark.ValidationError, match="model_call_budget_exhausted"):
        planner(stage="research", inputs=inputs, evidence_root=ROOT / "tests")
    assert backend.calls == 0
