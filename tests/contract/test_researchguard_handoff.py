from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys

import pytest

from _common import ValidationError, fingerprint, fingerprint_without
from schema_validation import SchemaValidationError, assert_schema_valid
from researchguard_handoff import (
    bind_handoff_consumption,
    build_researchguard_handoff,
    validate_handoff_consumption,
    validate_researchguard_handoff,
)


def _native_researchguard_ready_plan(tmp_path: Path) -> tuple[dict, str, str]:
    """Run the real local ResearchGuard native synthesizer for the bridge test.

    The consumer test deliberately imports the formal local source tree instead
    of an installed compatibility package.  This keeps the bridge bound to the
    exact source under audit and fails loudly when that local dependency is not
    available; it never substitutes a fixture or a caller-authored pass.
    """

    configured = os.environ.get("RESEARCHGUARD_SOURCE_ROOT") or os.environ.get("RESEARCHGUARD_ROOT")
    candidates = []
    if configured:
        candidates.append(Path(configured))
    candidates.append(Path(r"D:\Documents_Archive_20260824\workflow-state-projects\ResearchGuard"))
    rg_root = next(
        (candidate.resolve() for candidate in candidates if (candidate / "src" / "researchguard").is_dir()),
        None,
    )
    if rg_root is None:
        pytest.fail(
            "local ResearchGuard source is required for the native bridge test; "
            "set RESEARCHGUARD_SOURCE_ROOT to the formal repository"
        )

    # Ensure this test loads the selected source tree even if a stale installed
    # distribution was imported by another test, then restore the interpreter
    # state so the consumer suite keeps its own module boundary.
    saved_modules = {
        key: value
        for key, value in sys.modules.items()
        if key == "researchguard" or key.startswith("researchguard.")
    }
    saved_path = list(sys.path)
    for key in list(saved_modules):
        sys.modules.pop(key, None)
    sys.path.insert(0, str(rg_root / "src"))
    try:
        from researchguard.logic import load_model_from_dict, model_fingerprint, synthesize_artifact_plan
        from researchguard.logic.execution_depth import _build_native_depth_analysis

        nodes: dict[str, dict[str, object]] = {}
        edges: list[dict[str, str]] = []
        for claim_id, importance in (("C0", 1.0), ("O1", 0.2)):
            nodes[claim_id] = {
                "type": "Claim",
                "text": f"Native bridge conclusion {claim_id}",
                "importance": importance,
            }
            for prefix, node_type, edge_type in (
                ("E", "Evidence", "supports"),
                ("W", "Warrant", "supports"),
                ("A", "Assumption", "depends_on"),
                ("L", "Limitation", "qualifies"),
                ("R", "Rebuttal", "attacks"),
            ):
                node_id = f"{prefix}{claim_id}"
                nodes[node_id] = {
                    "type": node_type,
                    "text": f"Native bridge {node_type} {claim_id}",
                    "importance": 0.7 if claim_id == "C0" else 0.2,
                }
                edges.append({"source": node_id, "target": claim_id, "type": edge_type})
        model = load_model_from_dict(
            {
                "model": {
                    "id": "logic-writing-native-bridge",
                    "root_claim": "C0",
                    "target_units": [{"unit_id": "unit:delivery", "node_ids": list(nodes)}],
                    "model_cards": [{"card_id": "card:delivery", "node_ids": list(nodes)}],
                    "role_dispositions": {"competition": "not_applicable"},
                },
                "nodes": nodes,
                "edges": edges,
            }
        )
        request = {
            "schema": "researchguard.logic.synthesis-request.v1",
            "request_id": "logic-writing-native-bridge-request",
            "target_id": "logic-writing-native-bridge-artifact",
            "target_goal": "Explain the bounded conclusion in reader order.",
            "artifact_kind": "report",
            "reader_id": "logic-writing-reader",
            "model_id": model.id,
            "model_fingerprint": model_fingerprint(model),
            "body_unit_order": ["u0"],
            "max_body_units": 1,
            "units": [{
                "unit_id": "u0",
                "parent_unit_id": None,
                "reader_question": "Why does the conclusion hold?",
                "unit_job": "Establish the bounded conclusion and its direct support.",
                "claim_ids": ["C0"],
                "predecessor_unit_ids": [],
                "progression_relation": "concludes",
                "editorial_prominence": "lead",
                "placement": "body",
                "placement_reason": "This is the central reader unit.",
                "required": True,
            }],
            "source_branch_bindings": [],
        }
        native_receipt = _build_native_depth_analysis(model, budget=20)
        native_plan = synthesize_artifact_plan(
            model,
            selection_request=request,
            native_depth_receipt=native_receipt,
        ).to_dict()
        assert native_plan["status"] == "research_handoff_ready", native_plan.get("open_gaps")
        receipt_payload = native_receipt.to_dict()
    finally:
        for key in list(sys.modules):
            if key == "researchguard" or key.startswith("researchguard."):
                sys.modules.pop(key, None)
        sys.path[:] = saved_path
        sys.modules.update(saved_modules)

    plan_path = tmp_path / "researchguard-native-plan.json"
    receipt_path = tmp_path / "researchguard-native-depth-receipt.json"
    plan_path.write_text(json.dumps(native_plan, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    receipt_path.write_text(json.dumps(receipt_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return native_plan, str(plan_path.resolve()), str(receipt_path.resolve())


def _plan(*, status: str = "research_handoff_ready", gaps: list[str] | None = None) -> dict:
    return {
        "schema": "researchguard.logic.synthesis-plan.v1",
        "model_id": "logicguard-model-v1",
        "target_goal": "Explain the bounded conclusion in reader order.",
        "profile": "report",
        "units": [{
            "unit_id": "unit:root",
            "parent_unit_id": None,
            "reader_question": "Why does the conclusion hold?",
            "unit_job": "Establish the conclusion and its direct support.",
            "claim_ids": ["claim:root"],
            "predecessor_unit_ids": [],
            "progression_relation": "establishes",
            "editorial_prominence": "lead",
            "placement": "body",
            "placement_reason": "The reader needs this as the central body unit.",
            "required": True,
            "argument_closure": ["claim:root", "evidence:root"],
            "role_bindings": {"evidence": ["evidence:root"]},
            "source_branch_ids": [],
            "research_importance": {"claim:root": 0.95},
        }],
        "body_unit_order": ["unit:root"],
        "candidate_dispositions": [
            {
                "candidate_id": "claim:root",
                "candidate_kind": "Claim",
                "placement": "body",
                "reason": "Selected by the reader unit.",
                "selected_unit_ids": ["unit:root"],
            },
            {
                "candidate_id": "candidate:optional",
                "candidate_kind": "Context",
                "placement": "omit",
                "reason": "Outside the requested scope.",
                "selected_unit_ids": [],
            },
        ],
        "open_gaps": list(gaps or []),
        "status": status,
        "claim_boundary": "The handoff does not license factual certainty or prose quality.",
        "model_fingerprint": fingerprint({"model": "logicguard-model-v1"}),
        "selection_request_fingerprint": fingerprint({"request": "selection-1"}),
        "request_schema": "researchguard.logic.synthesis-request.v1",
    }


def _inputs() -> dict[str, str]:
    return {
        "reader_intent_fingerprint": fingerprint({"intent": "intent-1"}),
        "composition_plan_fingerprint": fingerprint({"plan": "plan-1"}),
        "writer_input_fingerprint": fingerprint({"writer": "writer-1"}),
        "native_receipt_fingerprint": fingerprint({"receipt": "receipt-1"}),
        "native_receipt_locator": "fixture://researchguard/logic/receipt-1",
    }


def test_ready_native_plan_maps_to_reader_projection_and_round_trips():
    plan = _plan()
    inputs = _inputs()
    handoff = build_researchguard_handoff(
        plan,
        **inputs,
        native_result_locator="fixture://researchguard/logic/synthesis-plan-1",
    )

    assert handoff["status"] == "current_pass"
    assert handoff["native_result_schema_version"] == "researchguard.logic.synthesis-plan.v1"
    assert handoff["body_unit_order"] == ["unit:root"]
    assert handoff["units"][0]["argument_closure"] == ["claim:root", "evidence:root"]
    assert validate_researchguard_handoff(handoff, plan, **inputs) == handoff


def test_native_raw_fingerprints_are_normalized_without_rehashing_native_payload():
    plan = _plan()
    raw_model = plan["model_fingerprint"].removeprefix("sha256:")
    raw_request = plan["selection_request_fingerprint"].removeprefix("sha256:")
    plan["model_fingerprint"] = raw_model
    plan["selection_request_fingerprint"] = raw_request
    inputs = _inputs()

    handoff = build_researchguard_handoff(
        plan,
        **inputs,
        native_result_locator="fixture://researchguard/logic/synthesis-plan-raw-fingerprints",
    )

    assert handoff["model_fingerprint"] == f"sha256:{raw_model}"
    assert handoff["native_request_fingerprint"] == f"sha256:{raw_request}"
    assert handoff["native_result_fingerprint"] == fingerprint(plan)
    assert validate_researchguard_handoff(handoff, plan, **inputs) == handoff


def test_support_gap_stays_blocked_and_cannot_enter_writer_projection():
    plan = _plan(status="blocked_support_gap", gaps=["unit:root:support_gap:claim:root:warrant"])
    handoff = build_researchguard_handoff(
        plan,
        **_inputs(),
        native_result_locator="fixture://researchguard/logic/synthesis-plan-gap",
    )

    assert handoff["status"] == "blocked"
    assert handoff["native_status"] == "blocked_support_gap"
    assert handoff["blocking_gaps"] == ["unit:root:support_gap:claim:root:warrant"]
    assert handoff["units"] == []
    assert handoff["body_unit_order"] == []


def test_handoff_rejects_a_caller_authored_order_even_after_refingerprinting():
    plan = _plan()
    inputs = _inputs()
    handoff = build_researchguard_handoff(
        plan,
        **inputs,
        native_result_locator="fixture://researchguard/logic/synthesis-plan-2",
    )
    forged = copy.deepcopy(handoff)
    forged["body_unit_order"] = []
    forged["handoff_fingerprint"] = fingerprint_without(forged, "handoff_fingerprint")

    with pytest.raises(ValidationError, match="stale or foreign"):
        validate_researchguard_handoff(forged, plan, **inputs)


def test_ready_native_plan_with_gaps_is_rejected_before_mapping():
    plan = _plan(status="research_handoff_ready", gaps=["unit:root:support_gap:claim:root:warrant"])

    with pytest.raises(ValidationError, match="ready ResearchGuard handoff"):
        build_researchguard_handoff(
            plan,
            **_inputs(),
            native_result_locator="fixture://researchguard/logic/synthesis-plan-invalid",
        )


@pytest.mark.parametrize("parent", ["unit:missing", "unit:root"])
def test_native_parent_hierarchy_rejects_dangling_or_cyclic_links(parent):
    plan = _plan()
    plan["units"][0]["parent_unit_id"] = parent
    with pytest.raises(ValidationError, match="parent"):
        build_researchguard_handoff(
            plan,
            **_inputs(),
            native_result_locator="fixture://researchguard/logic/synthesis-plan-parent-invalid",
        )


def test_native_predecessor_graph_rejects_cycles_outside_body_order():
    plan = _plan()
    note = copy.deepcopy(plan["units"][0])
    note.update({
        "unit_id": "unit:note",
        "parent_unit_id": None,
        "predecessor_unit_ids": ["unit:root"],
        "progression_relation": "background",
        "editorial_prominence": "brief",
        "placement": "note",
        "required": False,
    })
    plan["units"][0]["predecessor_unit_ids"] = ["unit:note"]
    plan["units"] = [plan["units"][0], note]
    with pytest.raises(ValidationError, match="predecessor graph"):
        build_researchguard_handoff(
            plan,
            **_inputs(),
            native_result_locator="fixture://researchguard/logic/synthesis-plan-predecessor-cycle",
        )


def test_current_pass_requires_non_null_native_receipt_identity_in_schema():
    handoff = build_researchguard_handoff(
        _plan(),
        **_inputs(),
        native_result_locator="fixture://researchguard/logic/synthesis-plan-schema",
    )
    forged = copy.deepcopy(handoff)
    forged["native_receipt_fingerprint"] = None
    with pytest.raises(SchemaValidationError, match="native_receipt_fingerprint"):
        assert_schema_valid("researchguard-logic-handoff.schema.json", forged)


def test_semantic_handoff_can_be_joined_only_by_an_exhaustive_reader_mapping():
    plan = _plan()
    native_inputs = {
        "reader_intent_fingerprint": fingerprint({"intent": "intent-1"}),
        "native_receipt_fingerprint": fingerprint({"receipt": "receipt-1"}),
        "native_receipt_locator": "fixture://researchguard/logic/receipt-1",
    }
    handoff = build_researchguard_handoff(
        plan,
        **native_inputs,
        native_result_locator="fixture://researchguard/logic/synthesis-plan-semantic",
    )
    assert handoff["stage"] == "semantic"
    composition = {
        "planned_units": [{"planned_unit_id": "planned:root"}],
    }
    brief = {
        "brief_fingerprint": "",
        "reader_intent_fingerprint": native_inputs["reader_intent_fingerprint"],
        "writer_input_fingerprint": fingerprint({"writer": "current"}),
        "composition_plan": composition,
    }
    brief["brief_fingerprint"] = fingerprint_without(brief, "brief_fingerprint")
    mapping = [{
        "native_unit_id": "unit:root",
        "planned_unit_ids": ["planned:root"],
        "disposition": "body",
        "reason": "The selected native unit is the central reader unit.",
    }]
    binding = bind_handoff_consumption(handoff, brief, mapping)
    assert binding["schema_version"] == "researchguard.logic.consumption-binding.v1"
    assert_schema_valid("researchguard-consumption-binding.schema.json", binding)
    assert validate_handoff_consumption(binding, handoff, brief, mapping) == binding
    forged = copy.deepcopy(binding)
    forged.pop("unit_mapping")
    with pytest.raises(SchemaValidationError, match="unit_mapping"):
        assert_schema_valid("researchguard-consumption-binding.schema.json", forged)
    with pytest.raises(ValidationError, match="unit_mapping"):
        bind_handoff_consumption(handoff, brief, [])


def test_consumption_binding_rejects_partial_planned_unit_coverage():
    plan = _plan()
    native_inputs = {
        "reader_intent_fingerprint": fingerprint({"intent": "intent-1"}),
        "native_receipt_fingerprint": fingerprint({"receipt": "receipt-1"}),
        "native_receipt_locator": "fixture://researchguard/logic/receipt-1",
    }
    handoff = build_researchguard_handoff(
        plan,
        **native_inputs,
        native_result_locator="fixture://researchguard/logic/synthesis-plan-partial",
    )
    brief = {
        "brief_fingerprint": "",
        "reader_intent_fingerprint": native_inputs["reader_intent_fingerprint"],
        "writer_input_fingerprint": fingerprint({"writer": "current"}),
        "composition_plan": {
            "planned_units": [
                {"planned_unit_id": "planned:root"},
                {"planned_unit_id": "planned:descendant"},
            ],
        },
    }
    brief["brief_fingerprint"] = fingerprint_without(brief, "brief_fingerprint")
    mapping = [{
        "native_unit_id": "unit:root",
        "planned_unit_ids": ["planned:root"],
        "disposition": "body",
        "reason": "The central native unit is mapped to the lead planned unit.",
    }]
    with pytest.raises(ValidationError, match="every planned unit"):
        bind_handoff_consumption(handoff, brief, mapping)


def test_real_native_researchguard_plan_round_trips_into_reader_brief(tmp_path):
    """Prove the local provider-to-consumer path with native bytes and joins."""

    native_plan, native_plan_path, native_receipt_path = _native_researchguard_ready_plan(tmp_path)
    from reader_pipeline import build_reader_brief, validate_writer_input
    from tests.v2_support import make_reader_chain

    chain = make_reader_chain(tmp_path / "reader-chain", owner="investigation")
    base_brief = chain["reader_brief"]
    native_receipt = json.loads(Path(native_receipt_path).read_text(encoding="utf-8"))
    native_receipt_fingerprint = fingerprint(native_receipt)
    mapping = [{
        "native_unit_id": "u0",
        "planned_unit_ids": [chain["plan"]["planned_units"][0]["planned_unit_id"]],
        "disposition": "body",
        "reason": "The native conclusion is the central reader unit.",
    }]
    handoff = build_researchguard_handoff(
        native_plan,
        reader_intent_fingerprint=base_brief["reader_intent_fingerprint"],
        native_result_locator=native_plan_path,
        native_receipt_fingerprint=native_receipt_fingerprint,
        native_receipt_locator=native_receipt_path,
    )
    brief = build_reader_brief(
        route_decision=chain["route_decision"],
        content_boundaries=base_brief["content_boundaries"],
        composition_plan=chain["plan"],
        route_composition=chain["route_composition"],
        native_dependency_receipt_fingerprints=[native_receipt_fingerprint],
        content_authority_fingerprints=base_brief["content_authority_fingerprints"],
        brief_id="brief:logic-writing-native-bridge",
        native_handoff=handoff,
        native_plan=native_plan,
        native_handoff_mapping=mapping,
    )
    validate_writer_input(brief["writer_input"], reader_brief=brief, composition_plan=chain["plan"])
    binding = bind_handoff_consumption(handoff, brief, mapping)
    assert validate_handoff_consumption(binding, handoff, brief, mapping) == binding
    assert brief["writer_input"]["native_handoff"]["native_result_fingerprint"] == fingerprint(native_plan)
    assert binding["native_unit_ids"] == ["u0"]
    assert binding["planned_unit_ids"] == ["unit:answer"]
