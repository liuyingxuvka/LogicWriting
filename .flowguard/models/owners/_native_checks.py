"""Direct native model checks; no subprocess tests, hierarchy receipts or persistent PASS."""
from __future__ import annotations
import importlib
from flowguard.explorer import Explorer
from flowguard.scenario import run_exact_sequence

FACTORY_IDS = (
    "route_and_guard_model", "research_packet_model", "reader_artifact_model",
    "fiction_route_model", "travel_route_model", "investigation_route_model", "academic_route_model",
    "execution_binding", "operation_freshness_closure_model", "release_retirement_model",
)


def check_plan(model_id):
    module = importlib.import_module(f"models.owners.{model_id}.model")
    plan = module.build_plan()
    explored = Explorer(workflow=plan.workflow, initial_states=plan.initial_states,
        external_inputs=plan.external_inputs, invariants=plan.invariants,
        max_sequence_length=plan.max_sequence_length, progress_steps=0).explore()
    scenarios = [run_exact_sequence(case.workflow or plan.workflow, case.initial_state,
        case.external_input_sequence, case.invariants or plan.invariants, case) for case in plan.scenarios]
    broken = {name: explorer.explore() for name, explorer in (module.broken_variants() if hasattr(module, "broken_variants") else {}).items()}
    return {"ok": explored.ok and all(not report.ok and bool(report.violations) for report in broken.values()) and all(case.model_report.ok and case.observed_status == case.scenario.expected.expected_status for case in scenarios), "model_id": model_id, "known_bad": {name: not report.ok for name, report in broken.items()},
            "transitions": explored.transition_count, "sequences": explored.explored_sequence_count,
            "scenarios": [{"name": case.scenario.name, "ok": case.model_report.ok and case.observed_status == case.scenario.expected.expected_status} for case in scenarios],
            "claim_boundary": "Finite native state model; real code behavior is checked separately by ordinary pytest."}


def check_optional(model_id):
    module = importlib.import_module(f"models.owners.{model_id}.model")
    if model_id == "development_process_flow":
        good, bad = module.run_checks()
        return {"ok": good.ok and not bad.ok, "good": good.to_dict(), "known_bad": bad.to_dict()}
    if model_id == "behavior_commitment_ledger":
        from flowguard import review_behavior_commitment_ledger
        return review_behavior_commitment_ledger(module.build_behavior_commitment_ledger())
    if model_id == "primary_path_authority":
        from flowguard import review_primary_path_authority
        good = [review_primary_path_authority(plan) for plan in (module.design_plan(), module.researchguard_member_plan())]
        bad = [review_primary_path_authority(plan) for plan in (module.broken_old_skill_masks_primary_failure(), module.broken_alias_unknown_disposition(), module.broken_manual_recovery_auto_invoked())]
        return {"ok": all(row.ok for row in good) and all(not row.ok for row in bad)}
    if model_id == "model_test_alignment":
        from flowguard import review_model_test_alignment
        return {"ok": review_model_test_alignment(module.aligned_plan()).ok and not review_model_test_alignment(module.broken_missing_actual_artifact_plan()).ok}
    if model_id == "plan_detailing":
        details, intake, process, contracts = module.run_checks()
        return {"ok": details[0].ok and all(not row.ok for row in details[1:]) and intake.ok and bool(contracts)}
    if model_id == "test_mesh":
        from flowguard import review_test_mesh
        # This optional view reports pending final evidence honestly.
        return review_test_mesh(module.release_plan())
    raise ValueError(f"unknown model: {model_id}")
