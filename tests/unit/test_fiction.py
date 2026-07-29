from __future__ import annotations

from pathlib import Path

from select_route import select_route
from tests.v2_support import route_request


ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "skills" / "logic-writing" / "routes" / "fiction"


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
