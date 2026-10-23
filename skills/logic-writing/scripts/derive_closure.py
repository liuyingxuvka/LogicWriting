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
)
from reader_pipeline import (
    validate_artifact_map,
    _compare_reader_audit,
    _build_reader_audit_from_current,
    fill_closure_fingerprints,
    _reader_judgment_from_current,
    validate_revision_provenance,
    _route_review_from_current,
    validate_route_composition,
    _shared_writing_from_current,
)


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
    "sourceguard": ("status", "stop_sufficient"),
    "logicguard": ("wording_license", "assert"),
    "worldguard": ("status", "PASS"),
}


def required_providers(owner, brief, route_composition):
    live = any(row.get("status") == "live" for row in
               brief.get("content_boundaries", {}).get("alternatives", []))
    required = {"sourceguard"} if owner == "investigation" else set()
    if live and owner in {"investigation", "academic-writing"}:
        required.add("logicguard")
    if owner == "travel-guide" or (
        owner == "fiction-writing" and route_composition.get("world_check_required", False)
    ):
        required.add("worldguard")
    return required


def provider_checks(owner, brief, route_composition, reports):
    """Copy saved native statuses; never execute a provider or certify its evidence."""
    required = required_providers(owner, brief, route_composition)
    if not isinstance(reports, list):
        raise ValidationError("provider_reports must be a list")
    checks, risks = [], []
    for report in reports:
        report = require_mapping(report, "provider report")
        provider, path = report.get("provider"), report.get("path")
        if not isinstance(provider, str) or provider not in PROVIDER_STATUS_FIELDS or not isinstance(path, str) or not path:
            raise ValidationError("provider report needs a known provider and a nonempty path")
        field, passing = PROVIDER_STATUS_FIELDS[provider]
        document, status = {}, "unreadable"
        try:
            document = load_json(path)
            if isinstance(document, dict) and field in document:
                status = document[field]
        except (OSError, ValueError, UnicodeError):
            pass
        passed = status == passing
        checks.append(dict(provider=provider, path=path, status=status,
                           passed=passed, required=provider in required))
        if not passed:
            reason = f"{provider} report {path}: {status}"
            if provider == "logicguard" and isinstance(document, dict) and "reason" in document:
                reason += f"; {document['reason']}"
            risks.append(dict(defect_id=f"provider:{provider}", owner=owner, reason=reason))
    supplied = {row["provider"] for row in checks}
    for provider in sorted(required - supplied):
        checks.append(dict(provider=provider, path=None, status="not_run", passed=False, required=True))
        risks.append(dict(defect_id=f"provider:{provider}", owner=owner,
                          reason=f"{provider} report is missing: not_run"))
    return checks, risks, all(row["passed"] for row in checks)


def derive_closure(
    value: Any,
) -> dict[str, Any]:
    request = copy.deepcopy(require_mapping(value, "closure input"))
    required = (
        "closure_id", "route_decision", "reader_brief", "route_composition",
        "artifact_map", "shared_writing", "deterministic_audit", "route_review",
        "judgment", "revision_provenance",
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
    shared = _shared_writing_from_current(request["shared_writing"], amap=amap, reader_brief=brief)
    audit = require_mapping(request["deterministic_audit"], "ReaderAudit")
    require_schema("reader-audit.schema.json", audit, label="ReaderAudit")
    current_audit = _build_reader_audit_from_current(
        audit_id=audit["audit_id"], amap=amap, brief=brief, contract=shared, audited_at=audit.get("audited_at"))
    audit = _compare_reader_audit(audit, current_audit)
    route_review = _route_review_from_current(
        request["route_review"],
        owner=owner,
        route=route,
        amap=amap,
        required_dimensions=REQUIRED_DIMENSIONS[owner],
    )
    judgment = _reader_judgment_from_current(
        request["judgment"],
        amap=amap,
        brief=brief,
        contract=shared,
        audit=audit,
        route_review=route_review,
    )
    provenance = validate_revision_provenance(
        request["revision_provenance"],
        target_artifact_fingerprint=amap["artifact_fingerprint"],
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
    if self_review:
        residual.append({
            "defect_id": "reader.self-review",
            "owner": owner,
            "reason": "The reader judgment was a self-review by the writer, not an independent read.",
        })
    checks, provider_risks, providers_passed = provider_checks(
        owner, brief, route, request.get("provider_reports", []))
    residual.extend(provider_risks)
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
    # current. Re-read once before emitting or committing any closure receipt.
    try:
        final_bytes = Path(amap["artifact_path"]).read_bytes()
    except OSError as exc:
        raise ValidationError("ArtifactMap artifact is missing before closure") from exc
    if "sha256:" + hashlib.sha256(final_bytes).hexdigest() != amap["artifact_fingerprint"]:
        raise ValidationError("ArtifactMap became stale during closure")
    closure = {
        "schema_version": "2.0",
        "closure_id": request["closure_id"],
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = derive_closure(fill_closure_fingerprints(load_request(args.input)))
    except (OSError, ValueError, ValidationError) as exc:
        print(f"ERROR: {exc}")
        return 2
    dump_json(result, args.output)
    return 0 if result["closure"]["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["REQUIRED_DIMENSIONS", "derive_closure"]
