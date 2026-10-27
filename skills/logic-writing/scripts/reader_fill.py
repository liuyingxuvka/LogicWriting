"""Reader fill: current reader-chain responsibilities."""
from __future__ import annotations

from route_inputs import route_extension_fingerprint

from researchguard_status import fill_anchors_from_research

from _common import ValidationError, fill_fingerprint, fill_missing, fingerprint, fingerprint_text, require_mapping
from copy import deepcopy
from pathlib import Path
from reader_binding import quote_binding_units
from reader_plan import validate_revision_provenance
from typing import Any, Mapping


def fill_plan_defaults(request: dict[str, Any]) -> dict[str, Any]:
    """Fill only repeated visible placements and fiction fields, before identity."""
    plan = request.get("composition_plan")
    boundaries = request.get("content_boundaries")
    if not isinstance(plan, dict) or not isinstance(boundaries, Mapping):
        return request
    planned = plan.get("planned_units", [])
    if not isinstance(planned, list):
        return request
    units = [unit for unit in planned if isinstance(unit, Mapping) and isinstance(unit.get("planned_unit_id"), str)]
    for collection, identity_field, references in (
        ("content_dispositions", "content_unit_id", "content_unit_ids"),
        ("limitation_dispositions", "limitation_id", "limitation_ids"),
    ):
        rows = plan.get(collection, [])
        if collection == "content_dispositions":
            plan.setdefault(collection, rows)
        if not isinstance(rows, list):
            continue
        existing = {row[identity_field] for row in rows if isinstance(row, Mapping) and isinstance(row.get(identity_field), str)}
        native = boundaries.get("content_units" if collection == "content_dispositions" else "limitations", [])
        for item in native if isinstance(native, list) else []:
            if not isinstance(item, Mapping):
                continue
            identity = item.get(identity_field)
            if not isinstance(identity, str):
                continue
            owners = [unit["planned_unit_id"] for unit in units if isinstance(unit.get(references), list) and identity in unit[references]]
            if identity in existing or not owners:
                continue
            if collection == "content_dispositions":
                rows.append({"content_unit_id": identity, "disposition": "body", "planned_unit_ids": owners,
                             "reason": "placed in planned unit(s) " + ", ".join(owners)})
            else:
                rows.append({"limitation_id": identity, "affected_claim_ids": deepcopy(item.get("affected_content_unit_ids", [])),
                    "materiality": "changes_strength", "materiality_reason": "default for a limitation placed in the body",
                    "disposition": "body", "destination_unit_ids": owners, "merged_into_id": None,
                    "realization_requirement": item.get("required_placement", ""), "native_boundary_refs": []})
            plan[collection] = rows
            existing.add(identity)
    route = request.get("route_composition")
    if isinstance(route, dict) and route.get("final_owner") == "fiction-writing":
        by_id = {unit.get("planned_unit_id"): unit for unit in units}
        for row in route.get("unit_plans", []) if isinstance(route.get("unit_plans"), list) else []:
            if not isinstance(row, dict) or not isinstance(row.get("unit_id"), str) or row["unit_id"] not in by_id:
                continue
            unit = by_id[row["unit_id"]]
            for target, source in (("contribution", "reader_job"), ("reader_state_before", "incoming_reader_state"),
                                   ("reader_state_after", "outgoing_reader_state"), ("downstream_unit_ids", "downstream_unit_ids")):
                if target not in row:
                    row[target] = deepcopy(unit.get(source))
            for key in ("open_questions_in", "open_questions_out", "prohibited_reveals"):
                row.setdefault(key, [])
    return request




def fill_brief_fingerprints(request: dict[str, Any]) -> dict[str, Any]:
    """Fill the fingerprints a caller left out of a ReaderBrief build request.

    The CompositionPlan and route composition get their own fingerprints and the
    references they share with the RouteDecision; a ResearchGuard synthesis plan
    given without a handoff is turned into the handoff.  Values the caller gives
    are kept and checked by build_reader_brief as before.
    """
    fill_anchors_from_research(request)
    fill_plan_defaults(request)
    decision = request.get("route_decision")
    intent_fp = decision.get("reader_intent_fingerprint") if isinstance(decision, Mapping) else None
    plan = request.get("composition_plan")
    fill_missing(plan, "reader_intent_fingerprint", intent_fp)
    fill_fingerprint(plan, "plan_fingerprint")
    route = request.get("route_composition")
    fill_missing(route, "reader_intent_fingerprint", intent_fp)
    fill_missing(route, "composition_plan_fingerprint", plan.get("plan_fingerprint") if isinstance(plan, Mapping) else None)
    if isinstance(route, dict) and route.get("extension_fingerprint") is None:
        route["extension_fingerprint"] = route_extension_fingerprint(route)
    if request.get("native_plan") is not None and request.get("native_handoff") is None and intent_fp:
        from researchguard_handoff import build_researchguard_handoff

        request["native_handoff"] = build_researchguard_handoff(
            request["native_plan"],
            reader_intent_fingerprint=intent_fp,
            native_result_locator=request.get("native_result_locator"),
        )
    return request


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _fill_evidence(evidence: Any, units: Mapping[str, Mapping[str, Any]]) -> None:
    if not isinstance(evidence, dict):
        return
    fill_missing(evidence, "locator", _mapping(units.get(evidence.get("artifact_unit_id"))).get("locator"))
    if isinstance(evidence.get("excerpt"), str):
        fill_missing(evidence, "excerpt_fingerprint", fingerprint_text(evidence["excerpt"]))


def _check_artifact_unit_membership(request, units):
    unit_ids = list(units)
    bounds = f"{unit_ids[0]} … {unit_ids[-1]}" if unit_ids else "no units"

    def check(unit_id, prefix):
        if isinstance(unit_id, str) and unit_id not in units:
            raise ValidationError(
                f"{prefix} names artifact unit {unit_id}, which is not in the current ArtifactMap (it has {bounds})"
            )

    def rows(value):
        return value if isinstance(value, list) else ()

    for key in ("contract", "shared_writing"):
        contract = request.get(key)
        if not isinstance(contract, dict):
            continue
        for binding in rows(contract.get("unit_bindings")):
            binding = _mapping(binding)
            if not isinstance(binding.get("binding_id"), str):
                continue
            prefix = f"binding {binding['binding_id']}"
            for span in rows(binding.get("artifact_spans")):
                check(_mapping(span).get("artifact_unit_id"), prefix)
            for unit_id in rows(binding.get("artifact_unit_ids")):
                check(unit_id, prefix)
    for key in ("review", "route_review"):
        review = request.get(key)
        if not isinstance(review, dict):
            continue
        for limitation in rows(review.get('limitation_checks')):
            for evidence in rows(_mapping(limitation).get('evidence')):
                excerpt=_mapping(evidence).get('excerpt')
                if isinstance(excerpt,str) and excerpt and not any(excerpt in str(unit.get('text','')) for unit in units.values()):
                    raise ValidationError('limitation_quote_missing:'+str(_mapping(limitation).get('limitation_id','')))
        for limitation in rows(review.get('limitation_checks')):
            for evidence in rows(_mapping(limitation).get('evidence')):
                unit_id=_mapping(evidence).get('artifact_unit_id')
                if isinstance(unit_id,str) and unit_id not in units:
                    raise ValidationError('limitation_quote_missing:'+str(_mapping(limitation).get('limitation_id','')))
        for row in [*rows(review.get("dimensions")), *rows(review.get("limitation_checks")), *rows(review.get("overclaim_checks")), *rows(review.get("world_ref_checks"))]:
            for evidence in rows(_mapping(row).get("evidence")):
                check(_mapping(evidence).get("artifact_unit_id"), "review evidence")
        for finding in rows(review.get("findings")):
            check(_mapping(_mapping(finding).get("evidence")).get("artifact_unit_id"), "review evidence")


def fill_check_fingerprints(request: dict[str, Any]) -> dict[str, Any]:
    """Fill the fingerprints a caller left out of a SharedWriting contract or a route review.

    References are copied from the ReaderBrief, ArtifactMap and route composition
    in the same request, span locators and fingerprints from the ArtifactMap unit
    they name, excerpt fingerprints from the excerpt text, and each record gets
    its own fingerprint last.  Values the caller gives are kept and checked.
    """
    amap = _mapping(request.get("artifact_map"))
    brief = _mapping(request.get("reader_brief"))
    units = {row.get("artifact_unit_id"): row for row in amap.get("units", []) if isinstance(row, Mapping)}
    quote_errors = []
    resolved_bindings = []
    for key in ('contract', 'shared_writing'):
        contract = _mapping(request.get(key))
        for binding in contract.get('unit_bindings') or []:
            if not isinstance(binding, dict):
                continue
            try:
                resolved = quote_binding_units(binding, units)
                if resolved is not None:
                    resolved_bindings.append((binding, resolved))
            except ValidationError as exc:
                quote_errors.append(str(exc))
    if quote_errors:
        raise ValidationError('; '.join(quote_errors))
    _check_artifact_unit_membership(request, units)
    for binding, resolved in resolved_bindings:
        binding['artifact_unit_ids'] = [row['artifact_unit_id'] for row in resolved]
        if 'artifact_spans' not in binding:
            binding['artifact_spans'] = [{key: row[key] for key in
                ('artifact_unit_id', 'locator', 'content_fingerprint')} for row in resolved]
    for key in ("contract", "shared_writing"):
        contract = request.get(key)
        if not isinstance(contract, dict):
            continue
        for field, value in (
            ("route_decision_fingerprint", brief.get("route_decision_fingerprint")),
            ("reader_intent_fingerprint", brief.get("reader_intent_fingerprint")),
            ("reader_brief_fingerprint", brief.get("brief_fingerprint")),
            ("composition_plan_fingerprint", _mapping(brief.get("composition_plan")).get("plan_fingerprint")),
            ("route_extension_fingerprint", _mapping(brief.get("route_extension")).get("extension_fingerprint")),
            ("artifact_map_fingerprint", amap.get("map_fingerprint")),
            ("artifact_fingerprint", amap.get("artifact_fingerprint")),
        ):
            fill_missing(contract, field, value)
        for binding in contract.get("unit_bindings") or []:
            for span in _mapping(binding).get("artifact_spans") or []:
                if isinstance(span, dict):
                    unit = _mapping(units.get(span.get("artifact_unit_id")))
                    fill_missing(span, "locator", unit.get("locator"))
                    fill_missing(span, "content_fingerprint", unit.get("content_fingerprint"))
        fill_fingerprint(contract, "contract_fingerprint")
    extension_fp = _mapping(request.get("route_composition")).get("extension_fingerprint") or _mapping(
        brief.get("route_extension")).get("extension_fingerprint")
    for key in ("review", "route_review"):
        review = request.get(key)
        if not isinstance(review, dict):
            continue
        fill_missing(review, "route_extension_fingerprint", extension_fp)
        fill_missing(review, "artifact_map_fingerprint", amap.get("map_fingerprint"))
        fill_missing(review, "artifact_fingerprint", amap.get("artifact_fingerprint"))
        for row in [*(review.get("dimensions") or []), *(review.get("limitation_checks") or []), *(review.get("overclaim_checks") or []), *(review.get("world_ref_checks") or [])]:
            for evidence in _mapping(row).get("evidence") or []:
                _fill_evidence(evidence, units)
        for finding in review.get("findings") or []:
            _fill_evidence(_mapping(finding).get("evidence"), units)
        fill_fingerprint(review, "review_fingerprint")
    return request


def fill_closure_fingerprints(request: dict[str, Any]) -> dict[str, Any]:
    """Fill the fingerprints a caller left out of a closure request.

    SharedWriting and the route review are completed as in
    fill_check_fingerprints.  The ReaderJudgment copies its references from the
    ReaderBrief, ArtifactMap, SharedWriting, deterministic audit and route
    review in the same request; its evaluation profile is identified by the
    final owner and the scored dimensions.  Revision provenance takes the
    current artifact and ReaderIntent fingerprints.  Each record gets its own
    fingerprint last; values the caller gives are kept and checked.
    """
    fill_check_fingerprints(request)
    amap = _mapping(request.get("artifact_map"))
    brief = _mapping(request.get("reader_brief"))
    units = {row.get("artifact_unit_id"): row for row in amap.get("units", []) if isinstance(row, Mapping)}
    judgment = request.get("judgment")
    if isinstance(judgment, dict):
        for field, value in (
            ("reader_intent_fingerprint", brief.get("reader_intent_fingerprint")),
            ("reader_brief_fingerprint", brief.get("brief_fingerprint")),
            ("composition_plan_fingerprint", _mapping(brief.get("composition_plan")).get("plan_fingerprint")),
            ("artifact_map_fingerprint", amap.get("map_fingerprint")),
            ("shared_writing_contract_fingerprint", _mapping(request.get("shared_writing")).get("contract_fingerprint")),
            ("deterministic_audit_fingerprint", _mapping(request.get("deterministic_audit")).get("audit_fingerprint")),
            ("route_audit_fingerprint", _mapping(request.get("route_review")).get("review_fingerprint")),
            ("artifact_fingerprint", amap.get("artifact_fingerprint")),
        ):
            fill_missing(judgment, field, value)
        if isinstance(judgment.get("scores"), Mapping):
            fill_missing(judgment, "evaluation_profile_fingerprint", fingerprint(
                {"final_owner": judgment.get("final_owner"), "dimensions": sorted(judgment["scores"])}))
        for row in judgment.get("reverse_outline") or []:
            _fill_evidence(_mapping(row).get("evidence"), units)
        for row in [*(judgment.get("defects") or []), *(judgment.get("strengths") or [])]:
            _fill_evidence(_mapping(row).get("evidence"), units)
        fill_fingerprint(judgment, "judgment_fingerprint")
    intent = _mapping(brief.get("reader_intent"))
    for key in ("revision_provenance", "provenance"):
        if key in request or (key == "revision_provenance" and intent):
            request[key] = validate_revision_provenance(
                request.get(key), target_artifact_fingerprint=request.get("target_artifact_fingerprint") or amap.get("artifact_fingerprint"),
                artifact_mode=intent.get("artifact_mode"), artifact_map=amap or request.get("artifact_map"),
                reader_intent_fingerprint=brief.get("reader_intent_fingerprint"), final_owner=brief.get("final_owner"),
                recorded_at=_mapping(request.get("judgment")).get("judged_at"))
    return request
