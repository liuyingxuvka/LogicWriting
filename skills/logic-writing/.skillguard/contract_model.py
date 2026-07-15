"""Portable FlowGuard export for Logic Writing's SkillGuard contract."""

from __future__ import annotations

import flowguard


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"


def _preserved_route(route_id: str, label: str) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    execute = f"step:logic-writing:{label}:execute"
    passed = f"terminal:logic-writing:{label}:pass"
    blocked = f"terminal:logic-writing:{label}:blocked"
    steps: list[dict[str, object]] = [
        {
            "step_id": execute,
            "route_id": route_id,
            "owner_id": "logic-writing",
            "action_kind": "native",
            "prerequisite_step_ids": [],
            "required": True,
            "terminal_kind": "",
        },
        {
            "step_id": passed,
            "route_id": route_id,
            "owner_id": "logic-writing",
            "action_kind": "terminal",
            "prerequisite_step_ids": [execute],
            "required": True,
            "terminal_kind": "success",
        },
        {
            "step_id": blocked,
            "route_id": route_id,
            "owner_id": "logic-writing",
            "action_kind": "terminal",
            "prerequisite_step_ids": [],
            "required": True,
            "terminal_kind": "blocked",
        },
    ]
    function_id = f"logic_writing_{label.replace('-', '_')}"
    return (
        {
            "function_id": function_id,
            "business_intent": f"preserve the native {label} route",
            "owner_id": "logic-writing",
            "route_ids": [route_id],
            "composable_with": [],
        },
        {
            "route_id": route_id,
            "function_id": function_id,
            "owner_id": "logic-writing",
            "start_step_id": execute,
            "step_ids": [row["step_id"] for row in steps],
            "success_terminal_step_id": passed,
            "blocked_terminal_step_id": blocked,
            "handoffs": [],
        },
        steps,
    )


def export_contract_model() -> dict[str, object]:
    route_id = "route:logic-writing:router"
    main_steps: list[dict[str, object]] = [
        {
            "step_id": "step:logic-writing:route",
            "route_id": route_id,
            "owner_id": "logic-writing",
            "action_kind": "native",
            "prerequisite_step_ids": [],
            "required": True,
            "terminal_kind": "",
        },
        {
            "step_id": "step:logic-writing:evidence",
            "route_id": route_id,
            "owner_id": "logic-writing",
            "action_kind": "native",
            "prerequisite_step_ids": ["step:logic-writing:route"],
            "required": True,
            "terminal_kind": "",
        },
        {
            "step_id": "step:logic-writing:reader-artifact",
            "route_id": route_id,
            "owner_id": "logic-writing",
            "action_kind": "native",
            "prerequisite_step_ids": ["step:logic-writing:evidence"],
            "required": True,
            "terminal_kind": "",
        },
        {
            "step_id": "step:logic-writing:closure",
            "route_id": route_id,
            "owner_id": "logic-writing",
            "action_kind": "verifier",
            "prerequisite_step_ids": ["step:logic-writing:reader-artifact"],
            "required": True,
            "terminal_kind": "",
        },
        {
            "step_id": "step:logic-writing:maintenance",
            "route_id": route_id,
            "owner_id": "logic-writing",
            "action_kind": "verifier",
            "prerequisite_step_ids": ["step:logic-writing:closure"],
            "required": True,
            "terminal_kind": "",
        },
        {
            "step_id": "terminal:logic-writing:pass",
            "route_id": route_id,
            "owner_id": "logic-writing",
            "action_kind": "terminal",
            "prerequisite_step_ids": ["step:logic-writing:maintenance"],
            "required": True,
            "terminal_kind": "success",
        },
        {
            "step_id": "terminal:logic-writing:blocked",
            "route_id": route_id,
            "owner_id": "logic-writing",
            "action_kind": "terminal",
            "prerequisite_step_ids": [],
            "required": True,
            "terminal_kind": "blocked",
        },
    ]
    functions: list[dict[str, object]] = [
        {
            "function_id": "logic_writing_orchestration",
            "business_intent": "produce a reader-ready investigation or academic artifact through one final owner",
            "owner_id": "logic-writing",
            "route_ids": [route_id],
            "composable_with": [
                "logic_writing_investigation",
                "logic_writing_academic_writing",
            ],
        }
    ]
    routes: list[dict[str, object]] = [
        {
            "route_id": route_id,
            "function_id": "logic_writing_orchestration",
            "owner_id": "logic-writing",
            "start_step_id": "step:logic-writing:route",
            "step_ids": [row["step_id"] for row in main_steps],
            "success_terminal_step_id": "terminal:logic-writing:pass",
            "blocked_terminal_step_id": "terminal:logic-writing:blocked",
            "handoffs": [],
        }
    ]
    steps = list(main_steps)
    for child_route, label in (
        ("route:logic-writing:investigation", "investigation"),
        ("route:logic-writing:academic-writing", "academic-writing"),
    ):
        function, route, route_steps = _preserved_route(child_route, label)
        functions.append(function)
        routes.append(route)
        steps.extend(route_steps)

    rows = (
        ("obligation:logic-writing:routing", "logic_writing_selects_one_final_owner", ("step:logic-writing:route",)),
        ("obligation:logic-writing:specialist-authority", "logic_writing_preserves_specialist_authority", ("step:logic-writing:route",)),
        ("obligation:logic-writing:investigation-evidence", "investigation_requires_current_content_evidence", ("step:logic-writing:evidence",)),
        ("obligation:logic-writing:academic-provenance", "academic_requires_current_revision_provenance", ("step:logic-writing:evidence",)),
        ("obligation:logic-writing:reader-actual-artifact", "reader_quality_binds_actual_artifact", ("step:logic-writing:reader-artifact",)),
        ("obligation:logic-writing:final-closure", "final_closure_requires_minimum_content_chain", ("step:logic-writing:closure",)),
        ("obligation:logic-writing:release-integrity", "release_requires_current_validation_and_installation", ("step:logic-writing:maintenance",)),
    )
    return {
        "schema_version": "skillguard.flowguard_model_export.v2",
        "flowguard_schema_version": str(flowguard.SCHEMA_VERSION),
        "model_id": "logic-writing.skill-contract.v2",
        "parent_model_id": "logic-writing-lifecycle",
        "functions": functions,
        "routes": routes,
        "steps": steps,
        "obligations": [
            {
                "obligation_id": obligation_id,
                "invariant_id": invariant_id,
                "owner_step_ids": list(owner_steps),
                "required": True,
            }
            for obligation_id, invariant_id, owner_steps in rows
        ],
        "invariant_ids": [invariant_id for _obligation_id, invariant_id, _owner_steps in rows],
        "claim_boundary": (
            "The export preserves Logic Writing's native router and both final routes. "
            "SkillGuard consumes their checks and does not execute research or writing."
        ),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(export_contract_model(), indent=2, sort_keys=True))
