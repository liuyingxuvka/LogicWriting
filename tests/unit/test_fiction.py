from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

from select_route import select_route
from tests.v2_support import route_request


ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "skills" / "logic-writing" / "routes" / "fiction"


def _fiction_regression_module():
    path = ROOT / "scripts" / "run_fiction_regression.py"
    spec = importlib.util.spec_from_file_location("logic_writing_fiction_regression", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fiction_route_pack_is_internal_not_installable():
    assert ROUTE.is_dir()
    assert not (ROUTE / "SKILL.md").exists()
    assert not (ROUTE / "agents").exists()
    assert not (ROUTE / ".skillguard").exists()


def test_fiction_route_keeps_final_ownership_over_bounded_research():
    decision = select_route(route_request("novel", research=True))
    assert decision["final_owner"] == "fiction-writing"
    assert decision["child_routes"] == ["investigation"]


def test_named_binding_failure_family_is_preserved():
    failure_root = ROUTE / "examples" / "longform_failure_cases"
    required = {
        "unbound-prose-span.json",
        "unrealized-model-ref.json",
        "duplicate-binding-without-delta.json",
        "smooth-reveal-without-resistance.json",
        "premature-hypothesis-collapse.json",
        "term-register-owner-drift.json",
        "length-outlier-without-binding-review.json",
    }
    assert required.issubset({path.name for path in failure_root.glob("*.json")})


def test_fiction_regression_uses_bounded_budgets_for_slow_matrices():
    module = _fiction_regression_module()
    assert module.CASE_TIMEOUT_SECONDS["model-mesh"] == 900
    assert module.CASE_TIMEOUT_SECONDS["guard-lifecycle"] == 600
    assert all(0 < value <= 900 for value in module.CASE_TIMEOUT_SECONDS.values())


def test_fiction_regression_timeout_is_recorded_after_tree_cleanup(monkeypatch, tmp_path: Path):
    module = _fiction_regression_module()

    class FakeProcess:
        pid = 321
        returncode = -9

        def __init__(self):
            self.communicate_calls: list[int] = []

        def communicate(self, timeout=None):
            self.communicate_calls.append(timeout)
            if len(self.communicate_calls) == 1:
                raise subprocess.TimeoutExpired(["fake-owner"], timeout, output="partial", stderr="diagnostic")
            return "tail", "tail-diagnostic"

    process = FakeProcess()
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(
        module,
        "_load_cleanup_helpers",
        lambda: (lambda _process: {"confirmed": True, "root_pid": 321}, lambda _pid: []),
    )

    result = module._run_case(["fake-owner"], tmp_path, 1)

    assert result["timed_out"] is True
    assert result["cleanup_confirmed"] is True
    assert result["cleanup_evidence"]["root_pid"] == 321
    assert result["stdout"] == "partialtail"
    assert result["stderr"] == "diagnostictail-diagnostic"
    assert process.communicate_calls == [1, 30]
