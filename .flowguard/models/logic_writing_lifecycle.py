"""Parent model exposing the two deliberately separate execution planes."""

from __future__ import annotations

from .operation_freshness_closure_model import build_plan as build_operation_plan
from .release_retirement_model import build_plan as build_development_plan


MODEL_ID = "logic_writing_lifecycle"
PLANES = {
    "agent_operation": {
        "owner": "Logic Writing final route",
        "plan_factory": build_operation_plan,
        "terminal_claim": "reader artifact closure",
    },
    "development_process": {
        "owner": "single validation/release/retirement owner",
        "plan_factory": build_development_plan,
        "terminal_claim": "published replacement and sequential predecessor retirement",
    },
}

CROSS_PLANE_RELATIONS = (
    ("development_process.active_install", "governs", "agent_operation.entrypoint"),
    ("development_process.release_receipt", "validates", "installed Logic Writing source"),
    ("agent_operation.artifact", "does_not_invalidate", "development_process.release_receipt"),
)


def build_plans():
    return tuple(details["plan_factory"]() for details in PLANES.values())
