"""Run the Logic Writing FlowGuard model mesh and persist one current receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLOWGUARD_ROOT = ROOT / ".flowguard"
if str(FLOWGUARD_ROOT) not in sys.path:
    sys.path.insert(0, str(FLOWGUARD_ROOT))

from flowguard import (  # noqa: E402
    ConformanceReport,
    GraphEdge,
    LoopCheckConfig,
    ProgressCheckConfig,
    ReplayObservation,
    check_loops,
    check_progress,
    contract_exhaustion_to_composite_handoff_acceptance_ids,
    contract_exhaustion_to_model_obligations,
    contract_exhaustion_to_risk_gate_ids,
    contract_exhaustion_to_test_mesh_cell_ids,
    review_model_test_alignment,
)

from models.owners.model_test_alignment.model import (  # noqa: E402
    aligned_plan as model_test_alignment_plan,
    broken_missing_actual_artifact_plan,
)

from models.common import (  # noqa: E402
    DevelopmentEvent,
    DevelopmentState,
    OperationEvent,
    OperationState,
    development_workflow,
    operation_workflow,
)
from models.known_bad import run_known_bad_proofs  # noqa: E402
from models.frozen_source_contract_exhaustion import (  # noqa: E402
    review_frozen_execution_boundary,
    review_frozen_source_name_family,
)
from models.retirement_field_lifecycle import review_retirement_visibility_fields  # noqa: E402
from models.reader_contract_field_lifecycle import review_reader_contract_fields  # noqa: E402
from models.owners._mesh_support import (  # noqa: E402
    MODEL_PATHS,
    _current_hashes_match,
    load_child_receipt,
    run_logic_writing_parent,
)


def _one_successor(workflow, state, event):
    run = workflow.execute(state, event)
    if len(run.completed_paths) != 1 or run.dead_branches or run.exception_branches:
        return None
    return run.completed_paths[0].state


def _operation_progress_transition(state: OperationState):
    if state.terminal or state.closure_status == "blocked":
        return ()
    event = OperationEvent("close_operation")
    new_state = _one_successor(operation_workflow("operation_no_progress_graph"), state, event)
    if new_state is None:
        return ()
    return (GraphEdge(state, new_state, "close_operation"),)


def _next_development_event(state: DevelopmentState):
    if not state.validation_current:
        return DevelopmentEvent("freeze_validation", fingerprint="release:abc", status="current_pass")
    if state.stage_status != "current_pass":
        return DevelopmentEvent("stage_install", fingerprint="release:abc")
    if state.install_status != "current_pass":
        return DevelopmentEvent("activate_install", fingerprint="release:abc")
    if state.global_route_status != "current_pass":
        return DevelopmentEvent("project_global_route", fingerprint="release:abc")
    if state.release_status != "current_pass":
        return DevelopmentEvent("publish_release", fingerprint="release:abc")
    if not state.backups_verified:
        return DevelopmentEvent("verify_backups", status="current_pass")
    if "travel" not in state.retired_local:
        return DevelopmentEvent("quarantine_legacy_local", target="travel")
    if "storyline" not in state.retired_local:
        return DevelopmentEvent("quarantine_legacy_local", target="storyline")
    if not state.privatized_remote:
        return DevelopmentEvent("privatize_legacy_remote", fingerprint="private+anon404:travel", target="travel")
    if not state.first_privatization_health_rechecked:
        return DevelopmentEvent("recheck_after_first_privatization", status="current_pass")
    if state.privatized_remote == ("travel",):
        return DevelopmentEvent("privatize_legacy_remote", fingerprint="private+anon404:storyline", target="storyline")
    if state.user_deletion_handoff_status != "current_pass":
        return DevelopmentEvent("record_remote_deletion_handoff", status="current_pass")
    return None


def _development_progress_transition(state: DevelopmentState):
    if state.terminal:
        return ()
    event = _next_development_event(state)
    if event is None:
        return ()
    new_state = _one_successor(development_workflow("development_progress_graph"), state, event)
    if new_state is None:
        return ()
    return (GraphEdge(state, new_state, event.action),)


def _loop_and_progress_reports():
    operation_initial = OperationState(route_owner="academic-writing", route_status="current_pass")
    operation_loop = check_loops(
        LoopCheckConfig(
            initial_states=(operation_initial,),
            transition_fn=_operation_progress_transition,
            is_terminal=lambda state: state.terminal or state.closure_status == "blocked",
            max_states=8,
            max_depth=8,
        )
    )
    operation_progress = check_progress(
        ProgressCheckConfig(
            initial_states=(operation_initial,),
            transition_fn=_operation_progress_transition,
            is_terminal=lambda state: state.terminal or state.closure_status == "blocked",
            max_states=8,
            max_depth=8,
        )
    )
    development_loop = check_loops(
        LoopCheckConfig(
            initial_states=(DevelopmentState(),),
            transition_fn=_development_progress_transition,
            is_terminal=lambda state: state.terminal,
            is_success=lambda state: state.user_deletion_handoff_status == "current_pass",
            required_success=True,
            max_states=24,
            max_depth=24,
        )
    )
    development_progress = check_progress(
        ProgressCheckConfig(
            initial_states=(DevelopmentState(),),
            transition_fn=_development_progress_transition,
            is_terminal=lambda state: state.terminal,
            is_success=lambda state: state.user_deletion_handoff_status == "current_pass",
            max_states=24,
            max_depth=24,
        )
    )
    return {
        "operation_loop": operation_loop,
        "operation_progress": operation_progress,
        "development_loop": development_loop,
        "development_progress": development_progress,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_identity():
    files = (
        sorted((FLOWGUARD_ROOT / "models" / "owners").glob("**/*.py"))
        + sorted((FLOWGUARD_ROOT / "models").glob("*.py"))
        + sorted((FLOWGUARD_ROOT / "verification").glob("**/*.py"))
        + [ROOT / "tests" / "flowguard" / "test_model_contracts.py"]
    )
    return {str(path.relative_to(ROOT.parent)).replace("\\", "/"): _sha256(path) for path in files}


def _compact_summary(summary):
    return {
        "overall_status": summary.overall_status,
        "summary": summary.summary,
        "sections": [
            {
                "name": section.name,
                "status": section.status,
                "summary": section.summary,
                "findings": list(section.findings[:20]),
                "finding_count": len(section.findings),
            }
            for section in summary.sections
        ],
        "finding_ledger": {
            "entry_count": len(summary.finding_ledger.entries),
            "categories": sorted({entry.category for entry in summary.finding_ledger.entries}),
            "maintenance_obligation_count": len(summary.maintenance_obligations.obligations),
            "required_open_count": len(summary.maintenance_obligations.open_required_obligation_ids),
        },
    }


def _compact_check_report(report):
    return {
        "ok": report.ok,
        "trace_count": len(report.traces),
        "violation_names": sorted({item.invariant_name for item in report.violations}),
        "violation_count": len(report.violations),
        "dead_branch_count": len(report.dead_branches),
        "exception_count": len(report.exception_branches),
    }


def _compact_graph_report(report):
    payload = {
        "ok": report.ok,
        "graph_summary": dict(report.graph_summary),
        "finding_names": list(report.finding_names()) if hasattr(report, "finding_names") else [],
    }
    if hasattr(report, "stuck_states"):
        payload.update(
            {
                "stuck_state_count": len(report.stuck_states),
                "non_terminating_component_count": len(report.non_terminating_components),
                "unreachable_success": report.unreachable_success,
                "terminal_outgoing_count": len(report.terminal_with_outgoing_edges),
                "scc_count": len(report.sccs),
            }
        )
    else:
        payload.update({"finding_count": len(report.findings), "scc_count": len(report.sccs)})
    return payload


def _full_summary_ok(summary) -> bool:
    """Accept only the one non-applicable minimization gap in a clean model.

    FlowGuard records counterexample minimization as ``not_run`` when the
    explorer found no invariant violation to minimize.  That is not a skipped
    production check.  Every other section must pass and no required
    maintenance obligation may remain open.
    """

    allowed_non_applicable = {
        ("counterexample_minimization", "not_run"),
    }
    return (
        not summary.maintenance_obligations.open_required_obligation_ids
        and all(
            section.status == "pass"
            or (section.name, section.status) in allowed_non_applicable
            for section in summary.sections
        )
    )


def _current_conformance_report(aligned, alignment_known_bad) -> ConformanceReport:
    source_identity = _source_identity()
    model_fingerprint = "sha256:" + hashlib.sha256(
        json.dumps(
            source_identity,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return ConformanceReport(
        ok=aligned.ok and not alignment_known_bad.ok,
        replayed_steps=(
            ReplayObservation(
                function_name="review_model_test_alignment",
                observed_output=aligned.decision,
                observed_state={
                    "binding_row_count": len(aligned.binding_rows),
                    "finding_count": len(aligned.findings),
                },
                label="current-model-code-test-alignment",
                reason="Replayed the exact current structural alignment plan.",
            ),
            ReplayObservation(
                function_name="review_model_test_alignment",
                observed_output=alignment_known_bad.decision,
                observed_state={
                    "known_bad_rejected": not alignment_known_bad.ok,
                    "finding_count": len(alignment_known_bad.findings),
                },
                label="known-bad-missing-artifact-rejected",
                reason="Replayed the declared broken plan against the current checker.",
            ),
        ),
        summary=(
            "Current structural model-code-test alignment passed and the "
            "declared missing-artifact known-bad plan was rejected."
        ),
        prediction_id="logic-writing:model-test-alignment:current",
        prediction_fingerprint=model_fingerprint,
        model_fingerprint=model_fingerprint,
        observation_boundary_id="logic-writing:model-test-alignment:current",
    )


def _current_receipt_inventory() -> tuple[dict[str, object], bool]:
    """Read the already-produced owner receipts without rerunning children."""

    rows: list[dict[str, object]] = []
    all_current = True
    for model_id in sorted(MODEL_PATHS):
        try:
            payload = load_child_receipt(model_id, ROOT)
            current = _current_hashes_match(payload, ROOT)
            status = str(payload.get("status", "blocked"))
            row = {
                "model_id": model_id,
                "status": status,
                "current": current,
                "receipt_id": payload.get("receipt_id", ""),
                "receipt_fingerprint": payload.get("receipt_fingerprint", ""),
                "source_hash_count": len(payload.get("source_hashes", {})),
            }
            if not current or status not in {"pass", "pass_with_gaps"}:
                all_current = False
        except Exception as exc:  # keep the aggregate fail-closed and inspectable
            all_current = False
            row = {
                "model_id": model_id,
                "status": "failed",
                "current": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        rows.append(row)
    return {"models": rows, "count": len(rows)}, all_current


def run(profile: str):
    """Aggregate current child receipts and one parent closure.

    The old aggregate relaunched every factory, which produced duplicate full
    executions and let a parent appear green independently of its children.
    This entry point now consumes the immutable current child receipts and
    executes only the parent closure; it never invokes a child factory itself.
    """

    receipt_inventory, receipts_current = _current_receipt_inventory()
    parent = run_logic_writing_parent()
    parent_status = str(parent.get("status", "failed"))

    known_bad = run_known_bad_proofs()
    graph_reports = _loop_and_progress_reports()
    retirement_field_lifecycle = review_retirement_visibility_fields()
    reader_field_lifecycle = review_reader_contract_fields()
    field_lifecycle_ok = retirement_field_lifecycle.ok and reader_field_lifecycle.ok
    source_name_exhaustion = review_frozen_source_name_family()
    execution_boundary_exhaustion = review_frozen_execution_boundary()
    bad_ok = all(not report.ok for report in known_bad.values())
    graph_ok = all(report.ok for report in graph_reports.values())

    mesh_ok = receipts_current and parent_status in {"pass", "pass_with_gaps"}
    support_ok = bad_ok and graph_ok and field_lifecycle_ok
    strict_ok = mesh_ok and support_ok and source_name_exhaustion.ok and execution_boundary_exhaustion.ok
    status = "pass" if strict_ok and profile == "full" else ("pass_with_gaps" if mesh_ok else "failed")
    payload = {
        "artifact_type": "logic_writing_flowguard_model_receipt",
        "schema_version": "2.0",
        "profile": profile,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_identity": _source_identity(),
        "model_mesh": {
            "parent_model_id": "logic_writing_models",
            "parent_status": parent_status,
            "parent_receipt_id": parent.get("receipt_id", ""),
            "parent_receipt_fingerprint": parent.get("receipt_fingerprint", ""),
            "receipts_current": receipts_current,
            "receipt_inventory": receipt_inventory,
        },
        "known_bad": {name: _compact_check_report(report) for name, report in known_bad.items()},
        "graph_checks": {name: _compact_graph_report(report) for name, report in graph_reports.items()},
        "field_lifecycle": {
            "ok": field_lifecycle_ok,
            "decision": "field_lifecycle_full" if field_lifecycle_ok else "field_lifecycle_blocked",
            "finding_count": len(retirement_field_lifecycle.findings) + len(reader_field_lifecycle.findings),
            "projection_count": len(retirement_field_lifecycle.projections) + len(reader_field_lifecycle.projections),
        },
        "frozen_source_contract_exhaustion": {
            "ok": source_name_exhaustion.ok,
            "decision": source_name_exhaustion.decision,
            "confidence": source_name_exhaustion.confidence,
            "finding_count": len(source_name_exhaustion.findings),
            "generated_case_ids": [case.case_id for case in source_name_exhaustion.generated_cases],
            "coverage_receipt_ids": [receipt.receipt_id for receipt in source_name_exhaustion.coverage_receipts],
            "model_obligation_ids": [obligation.obligation_id for obligation in contract_exhaustion_to_model_obligations(source_name_exhaustion)],
            "test_mesh_case_ids": list(contract_exhaustion_to_test_mesh_cell_ids(source_name_exhaustion)),
            "risk_gate_ids": list(contract_exhaustion_to_risk_gate_ids(source_name_exhaustion)),
            "composite_handoff_acceptance_ids": list(contract_exhaustion_to_composite_handoff_acceptance_ids(source_name_exhaustion)),
        },
        "frozen_execution_contract_exhaustion": {
            "ok": execution_boundary_exhaustion.ok,
            "decision": execution_boundary_exhaustion.decision,
            "confidence": execution_boundary_exhaustion.confidence,
            "finding_count": len(execution_boundary_exhaustion.findings),
            "generated_case_ids": [case.case_id for case in execution_boundary_exhaustion.generated_cases],
            "coverage_receipt_ids": [receipt.receipt_id for receipt in execution_boundary_exhaustion.coverage_receipts],
            "model_obligation_ids": [obligation.obligation_id for obligation in contract_exhaustion_to_model_obligations(execution_boundary_exhaustion)],
            "test_mesh_case_ids": list(contract_exhaustion_to_test_mesh_cell_ids(execution_boundary_exhaustion)),
            "risk_gate_ids": list(contract_exhaustion_to_risk_gate_ids(execution_boundary_exhaustion)),
            "composite_handoff_acceptance_ids": list(contract_exhaustion_to_composite_handoff_acceptance_ids(execution_boundary_exhaustion)),
        },
        "checks": {
            "mesh": mesh_ok,
            "support": support_ok,
            "strict": strict_ok,
            "known_bad_rejected": bad_ok,
            "graphs": graph_ok,
            "field_lifecycle": field_lifecycle_ok,
        },
        "claim_boundary": "Current Logic Writing model-mesh receipt aggregation only; child receipts and parent closure are separate execution owners, and this report does not prove future AI prose quality, installation, publication, or authority activation.",
        "status": status,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("model-phase", "full"), default="model-phase")
    parser.add_argument("--json", action="store_true")
    isolated_output = os.environ.get("FLOWGUARD_OUTPUT_DIR")
    default_output = (
        Path(isolated_output) / "model-report.json"
        if isolated_output
        else FLOWGUARD_ROOT / "evidence" / "models" / "model-report.json"
    )
    parser.add_argument("--output", type=Path, default=default_output)
    args = parser.parse_args()
    payload = run(args.profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Logic Writing FlowGuard models: {payload['status']}")
        for name, summary in payload["models"].items():
            print(f"- {name}: {summary['overall_status']}")
        print(f"receipt: {args.output}")
    return 0 if payload["status"] in {"pass", "pass_with_gaps"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
