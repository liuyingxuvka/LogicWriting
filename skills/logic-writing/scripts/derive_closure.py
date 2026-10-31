#!/usr/bin/env python3
"""Derive the only current reader-facing closure from the complete v2 chain."""

from __future__ import annotations

import argparse
import copy
import hashlib
from pathlib import Path
from typing import Any, Mapping

from _common import (
    ValidationError,
    dump_json,
    fingerprint,
    load_json,
    load_request,
    require_mapping,
    require_schema,
    validation_result,
)
from researchguard_status import assess_research_verdict, research_report_identity_problems, research_wording_boundary, validate_anchor_authority
from _common import read_worldguard_report, worldguard_report_identity_problems
from route_inputs import route_extension_fingerprint
from world_refs import world_ref_unquoted
from known_bad import check_known_bad
from artifact_map import validate_artifact_map
from reader_checks import compare_reader_audit, build_reader_audit_from_current, reader_judgment_from_current, route_review_from_current
from reader_fill import fill_closure_fingerprints
from reader_plan import validate_evidence_boundaries, validate_request_sources, validate_revision_provenance, writer_added_units
from reader_plan_core import validate_route_composition
from reader_binding import shared_writing_from_current


REQUIRED_DIMENSIONS = {
    "investigation": (
        "recoverable_question", "bounded_answer", "evidence_strength",
        "negative_evidence", "alternatives", "conditions", "limitations",
        "fallback_recheck", "conclusion_scope",
    ),
    "academic-writing": (
        "research_question", "central_contribution", "hierarchy_progression",
        "paragraph_contribution", "evidence_citation", "method_depth",
        "figure_table_jobs", "qualification_implication",
    ),
    "fiction-writing": (
        "output_room", "story_movement", "resistance_cost", "promise_reveal",
        "continuity", "pov_voice", "reader_state", "actual_spans",
    ),
    "travel-guide": (
        "guide_kind", "traveler_fit", "unit_responsibility", "handoffs",
        "narrative_body", "operational_appendix", "risk_fallback",
        "source_recheck", "local_texture",
    ),
}


def _exact(value: Mapping[str, Any], field: str, label: str) -> str:
    actual = value.get(field)
    if not isinstance(actual, str):
        raise ValidationError(f"{label}.{field} is required")
    return actual


PROVIDER_STATUS_FIELDS = {
    "researchguard": ("verdict", "passed"),
    "worldguard": ("status", "PASS"),
}


def required_providers(owner, brief, route_composition):
    live = any(row.get("status") == "live" for row in brief.get("content_boundaries", {}).get("alternatives", []))
    required = {"researchguard"} if owner == "investigation" else set()
    if owner == "academic-writing" and (live or brief.get("research_folder")):
        required.add("researchguard")
    if owner == "travel-guide" or (owner == "fiction-writing" and route_composition.get("world_check_required", False)):
        required.add("worldguard")
    return required


IDENTITY_PROBLEMS = ("research_report_stale:", "research_report_unbound:",
                     "world_report_mismatch:", "world_report_unbound:", "world_report_stale:")


def provider_checks(owner, brief, route_composition, reports):
    """Read saved native results only; never invoke a provider from closure."""
    required = required_providers(owner, brief, route_composition)
    if not isinstance(reports, list):
        raise ValidationError("provider_reports must be a list")
    checks, risks = [], []
    for report in reports:
        report = require_mapping(report, "provider report")
        provider, path = report.get("provider"), report.get("path")
        if (
            not isinstance(provider, str)
            or provider not in PROVIDER_STATUS_FIELDS
            or not isinstance(path, str)
            or not path
        ):
            raise ValidationError("provider report needs a known provider and a nonempty path")
        if provider == "researchguard":
            try:
                document = load_json(path)
            except (OSError, ValueError, UnicodeError):
                document = {}
            assessment = assess_research_verdict(
                document, brief.get("content_boundaries", {}).get("alternatives", [])
            )
            status, passed, reason = (
                assessment["status"],
                assessment["passed"],
                assessment["reason"],
            )
            risks.extend(dict(row, owner=owner) for row in assessment["residual_risk"])
            # The report counts only for the research folder the brief names.
            problems = research_report_identity_problems(document, brief.get("research_folder"))
        else:
            status = read_worldguard_report(path)
            passed = status == "PASS"
            reason = f"{provider} report {path}: {status}"
            problems = worldguard_report_identity_problems(
                path, route_composition.get("world_contract")
            )
        if problems and status != "unreadable":  # an unreadable report already fails
            status, passed, reason = "failed", False, "; ".join(problems)
        checks.append(
            dict(
                provider=provider,
                path=path,
                status=status,
                passed=passed,
                reason=reason,
                required=provider in required,
            )
        )
        if not passed:
            risks.append(dict(defect_id=f"provider:{provider}", owner=owner, reason=reason))
    supplied = {row["provider"] for row in checks}
    for provider in sorted(required - supplied):
        reason = f"{provider} report is missing: not_run"
        checks.append(
            dict(
                provider=provider,
                path=None,
                status="not_run",
                passed=False,
                required=True,
                reason=reason,
            )
        )
        risks.append(dict(defect_id=f"provider:{provider}", owner=owner, reason=reason))
    return checks, risks, all(row["passed"] for row in checks)


def derive_closure(
    value: Any,
) -> dict[str, Any]:
    request = copy.deepcopy(require_mapping(value, "closure input"))
    required = (
        "closure_id", "route_decision", "reader_brief", "route_composition",
        "artifact_map", "shared_writing", "deterministic_audit", "route_review",
        "judgment",
    )
    missing = [field for field in required if field not in request]
    if missing:
        raise ValidationError(f"closure input is missing current v2 fields: {missing}")

    decision = require_mapping(request["route_decision"], "RouteDecision")
    require_schema("route-decision.schema.json", decision, label="RouteDecision")
    owner = decision["final_owner"]
    if decision["schema_version"] != "2.0" or decision["status"] != "current":
        raise ValidationError("closure requires one current v2 RouteDecision")
    brief = require_mapping(request["reader_brief"], "ReaderBrief")
    require_schema("reader-brief.schema.json", brief, label="ReaderBrief")
    validate_request_sources(brief['request'], brief['content_boundaries'])
    evidence_risks = validate_evidence_boundaries(brief)
    authority_risks = validate_anchor_authority(brief)
    if brief["route_decision_fingerprint"] != decision["decision_fingerprint"]:
        raise ValidationError("ReaderBrief is stale for RouteDecision")
    if brief["final_owner"] != owner:
        raise ValidationError("ReaderBrief belongs to a sibling route")

    route = validate_route_composition(
        request["route_composition"],
        owner=owner,
        reader_intent_fingerprint=brief["reader_intent_fingerprint"],
        composition_plan_fingerprint=brief["composition_plan"]["plan_fingerprint"],
        composition_plan=brief["composition_plan"],
        content_boundaries=brief["content_boundaries"],
    )
    amap = validate_artifact_map(request["artifact_map"])
    shared = shared_writing_from_current(request["shared_writing"], amap=amap, reader_brief=brief)
    audit = require_mapping(request["deterministic_audit"], "ReaderAudit")
    require_schema("reader-audit.schema.json", audit, label="ReaderAudit")
    current_audit = build_reader_audit_from_current(
        audit_id=audit["audit_id"], amap=amap, brief=brief, contract=shared, audited_at=audit.get("audited_at"))
    audit = compare_reader_audit(audit, current_audit)
    route_review = route_review_from_current(
        request["route_review"],
        owner=owner,
        route=route,
        amap=amap,
        required_dimensions=(*REQUIRED_DIMENSIONS[owner], *( ("explanation_pressure", "variation", "register_ownership") if owner == "fiction-writing" and route.get("longform_project") else ())),
        brief=brief, shared=shared,
    )
    judgment = reader_judgment_from_current(
        request["judgment"],
        amap=amap,
        brief=brief,
        contract=shared,
        audit=audit,
        route_review=route_review,
    )
    provenance = validate_revision_provenance(
        request.get("revision_provenance"),
        target_artifact_fingerprint=amap["artifact_fingerprint"],
        artifact_mode=brief["reader_intent"]["artifact_mode"], artifact_map=amap,
        reader_intent_fingerprint=brief["reader_intent_fingerprint"], final_owner=owner,
        recorded_at=judgment.get("judged_at"),
    )
    if provenance["reader_intent_fingerprint"] != brief["reader_intent_fingerprint"]:
        raise ValidationError("revision provenance is stale for ReaderIntent")
    if provenance["final_owner"] != owner:
        raise ValidationError("revision provenance belongs to a sibling route")


    all_passed = audit["status"] == route_review["status"] == judgment["status"] == "passed"
    status = "passed" if all_passed else "needs_repair"
    judge_kind = judgment["judge_kind"]
    self_review = judge_kind == "self_review"

    defect_ids = [
        *(row["finding_id"] for row in audit["findings"]),
        *(row["finding_id"] for row in route_review["findings"]),
        *(row["observation_id"] for row in judgment["defects"]),
    ]
    if not defect_ids and status != "passed":
        defect_ids = ["reader.quality-gate"]
    residual = [
        {
            "defect_id": defect_id,
            "owner": owner,
            "reason": "The current actual-artifact quality chain has not passed.",
        }
        for defect_id in dict.fromkeys(defect_ids)
    ]
    if status == "passed":
        residual = []
    residual.extend(dict(row, owner=owner) for row in evidence_risks)
    # In-process domain closure contributes real failed surfaces to the same quality gate.
    if owner == "fiction-writing" and route.get("longform_project"):
        import sys
        fiction_scripts = Path(__file__).resolve().parents[1] / "routes/fiction/scripts"
        if str(fiction_scripts) not in sys.path:
            sys.path.insert(0, str(fiction_scripts))
        from longform_closure_check import validate as validate_longform
        project_path = route["longform_project"]
        longform = validate_longform(load_json(project_path), project_path)
        if not longform["passed"]:
            status = "needs_repair"
            for surface, report in longform["surface_checks"].items():
                if not report["passed"]:
                    errors = [row for row in report["issues"] if row.get("severity", "error") == "error"]
                    for issue in errors or [{"code": "not_passed", "message": "Surface validation failed."}]:
                        residual.append(dict(defect_id=f"longform:{surface}:{issue['code']}", owner=owner, reason=issue.get("message", "Surface validation failed.")))
            if not residual:
                residual.append(dict(defect_id="longform:project:invalid", owner=owner, reason="The current longform project has not passed."))
    units = {row["artifact_unit_id"]: row for row in amap["units"]}
    for code in world_ref_unquoted(brief["composition_plan"], route_review, shared, lambda span: None):
        residual.append(dict(defect_id=code, owner=owner, reason="A planned world reference lacks a quotation in its bound current text."))
    try:
        bad = check_known_bad(request, _baseline_result=dict(caught=status != "passed", step="baseline", error="The current quality chain needs repair."))
    except ValidationError:
        current = Path(amap["artifact_path"]).read_bytes()
        if "sha256:" + hashlib.sha256(current).hexdigest() != amap["artifact_fingerprint"]:
            raise ValidationError("ArtifactMap became stale during closure")
        raise
    if bad.get("status") == "baseline_not_passed":
        residual.append(dict(defect_id="known-bad:baseline-not-passed", owner=owner, reason="The current baseline quality chain has not passed; mutation detection is not claimed."))
    else:
        for row in bad.get("variants", bad.get("results", [])):
            if not row["caught"]:
                residual.append(dict(defect_id=f"toothless:{row['kind']}:{row.get('unit') or row['name']}", owner=owner, reason="A declared known-bad mutation was not caught by the actual quality chain."))
    if self_review:
        residual.append({
            "defect_id": "reader.self-review",
            "owner": owner,
            "reason": "The reader judgment was a self-review by the writer, not an independent read.",
        })
    checks, provider_risks, providers_passed = provider_checks(
        owner, brief, route, request.get("provider_reports", []))
    for check in checks:
        if (check['provider'] != 'researchguard' or check['status'] in ('not_run', 'unreadable')
                or check['reason'].startswith(IDENTITY_PROBLEMS)):
            continue
        boundary = research_wording_boundary(load_json(check['path']))
        if boundary is None:
            continue
        root_id, wording, support = boundary
        boundaries = brief['content_boundaries']
        relations = {row['anchor_id']: row['relation'] for row in boundaries['evidence_anchors']}
        for unit in boundaries['content_units']:
            if (unit['required'] and support.intersection(unit['evidence_anchor_ids'])
                    and not any(relations.get(anchor) == 'limit' for anchor in unit['evidence_anchor_ids'])
                    and not unit['limitation_ids']):
                raise ValidationError(f"wording_exceeds_license:{unit['content_unit_id']}:{root_id} (the saved research report licenses {root_id} only as {wording}; cite a limit anchor or a limitation in this unit)")
    residual.extend(provider_risks)
    residual.extend(dict(row, owner=owner) for row in authority_risks)
    if any(row["reason"].startswith(IDENTITY_PROBLEMS) for row in checks):
        # Foreign or stale provider evidence is a defect of this closure's inputs.
        status = "needs_repair"
    reader_basis = "a self-review by the writer" if self_review else "independent reader judgment"
    if status == "passed":
        safe_claim = (
            "The exact current artifact passed composition coverage, deterministic checks, "
            f"route-semantic review, and {reader_basis}."
        )
    else:
        safe_claim = "The exact current artifact is preserved with explicit unresolved reader-facing defects."
        if self_review:
            safe_claim += " The reader judgment was a self-review by the writer."
    next_actions = [] if status == "passed" else [{"owner": owner, "action": "repair_and_rerun"}]
    if checks:
        safe_claim += "; provider reports: " + ", ".join(
            f"{row['provider']} {row['status']}" for row in checks)
    # A same-call snapshot is useful only while the underlying bytes remain
    # current. Re-read once before emitting or committing any closure result.
    try:
        final_bytes = Path(amap["artifact_path"]).read_bytes()
    except OSError as exc:
        raise ValidationError("ArtifactMap artifact is missing before closure") from exc
    if "sha256:" + hashlib.sha256(final_bytes).hexdigest() != amap["artifact_fingerprint"]:
        raise ValidationError("ArtifactMap became stale during closure")
    if route_extension_fingerprint(route) != route["extension_fingerprint"]:
        raise ValidationError("route composition inputs became stale during closure")
    closure = {
        "schema_version": "2.0",
        "closure_id": request["closure_id"],
        "added_by_writer": writer_added_units(brief),
        "final_owner": owner,
        "judge_kind": judge_kind,
        "artifact_fingerprint": amap["artifact_fingerprint"],
        "reader_intent_fingerprint": brief["reader_intent_fingerprint"],
        "composition_plan_fingerprint": brief["composition_plan"]["plan_fingerprint"],
        "route_extension_fingerprint": route["extension_fingerprint"],
        "artifact_map_fingerprint": amap["map_fingerprint"],
        "shared_writing_contract_fingerprint": shared["contract_fingerprint"],
        "deterministic_audit_fingerprint": audit["audit_fingerprint"],
        "route_audit_fingerprint": route_review["review_fingerprint"],
        "judgment_fingerprint": judgment["judgment_fingerprint"],
        "revision_provenance_fingerprint": provenance["provenance_fingerprint"],
        "status": status,
        "residual_risk": residual,
        "next_actions": next_actions,
        "safe_claim": safe_claim,
        "unsafe_claim_boundary": (
            "Structural licensing and actual-artifact review do not establish universal factual or aesthetic truth."
        ),
        "provider_checks": checks,
        "broad_claim_allowed": status == "passed" and not self_review and providers_passed,
    }
    closure["closure_fingerprint"] = fingerprint(closure)
    require_schema("closure.schema.json", closure, label="closure")

    return {"closure": closure}


CLOSURE_INPUT_FILES = {
    "route_decision": "route-decision.json", "reader_brief": "reader-brief.json",
    "route_composition": "reader-brief.json", "artifact_map": "artifact-map.json",
    "shared_writing": "shared-writing-result.json", "deterministic_audit": "audit.json",
    "route_review": "route-review-result.json",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = derive_closure(fill_closure_fingerprints(load_request(args.input, defaults=CLOSURE_INPUT_FILES)))
    except (OSError, ValueError, ValidationError) as exc:
        dump_json(validation_result(status="blocked", errors=[str(exc)]), args.output)
        return 2
    dump_json(validation_result(status=result["closure"]["status"], **result), args.output)
    return 0 if result["closure"]["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["REQUIRED_DIMENSIONS", "derive_closure"]
