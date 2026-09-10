"""Current Logic Writing reader-composition kernel.

This module owns only route-neutral identity, composition coverage, mechanical
artifact mapping, deterministic checks, independent-review binding, and typed
repair. Route semantics remain in the four selected route validators.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from _common import (
    ValidationError,
    fingerprint,
    fingerprint_text,
    fingerprint_without,
    require_mapping,
    require_schema,
)
from text_extent import measure_text


FINAL_OWNERS = ("investigation", "academic-writing", "fiction-writing", "travel-guide")
ROUTE_SCHEMA = {
    "investigation": "investigation-composition.schema.json",
    "academic-writing": "academic-composition.schema.json",
    "fiction-writing": "fiction-composition.schema.json",
    "travel-guide": "travel-composition.schema.json",
}
ROUTE_PROFILE_FIELD = {
    "investigation": "profile",
    "academic-writing": "profile",
    "fiction-writing": "output_room",
    "travel-guide": "guide_kind",
}
LIST_LINE = re.compile(
    r"^\s*(?:[-*+•◦▪‣]\s+|\d+[.)、]\s*|[一二三四五六七八九十]+、\s*|"
    r"[（(][一二三四五六七八九十\d]+[）)]\s*|\*\*[^*]{1,30}\*\*[：:])"
)
PLACEHOLDER = re.compile(
    r"\b(?:TODO|TBD|FIXME|INSERT\s+(?:TEXT|CITATION|EVIDENCE)|LOREM IPSUM)\b|"
    r"\[(?:TODO|TBD|INSERT)[^\]]*\]",
    re.IGNORECASE,
)
WORKFLOW_LEAK = re.compile(
    r"\b(?:SourceGuard|LogicGuard|TraceGuard|FlowGuard|current_pass|"
    r"reader_intent_fingerprint|composition_plan_fingerprint|repair_request)\b|"
    r"(?:本段|本节|本章)(?:旨在|将会|负责)|(?:以下段落|下一节)(?:将会|负责)",
    re.IGNORECASE,
)
SENTENCE_END = re.compile(r"[.!?。！？](?:[\"'”’)\]]*)$")
SENTENCE_MARK = re.compile(r"[.!?。！？](?=\s|$|[\"'”’)\]])")
WRITER_INTERNAL = re.compile(
    r"\b(?:SourceGuard|LogicGuard|TraceGuard|FlowGuard|current_pass|closure|"
    r"reader_intent_fingerprint|composition_plan_fingerprint|model ledger|"
    r"human_review|repair_request|audit)\b", re.IGNORECASE
)

# A content disposition is a routing decision, not a writing suggestion.  The
# writer projection deliberately has a small allow-list so that an internal
# planner note cannot re-enter the prompt merely because it happens to have a
# ``safe_meaning`` string.
VISIBLE_CONTENT_DISPOSITIONS = {
    "consumed", "body", "note", "appendix", "merged", "implied_by_scope",
}
HIDDEN_CONTENT_DISPOSITIONS = {
    "omitted", "internal", "blocked", "deferred", "conflict",
}
_BODY_UNIT_KINDS = {"paragraph", "list", "table", "quote", "scene", "code"}
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_LATIN = re.compile(r"[A-Za-z]")


def _measure_extent(text: str, unit: str, metric_id: str | None = None) -> int:
    """Measure reader-facing extent using the declared intent unit."""
    return measure_text(text, unit, metric_id=metric_id)


def _language_mismatch(text: str, language: str) -> bool:
    """Return true only for an obvious whole-document language mismatch."""
    compact = re.sub(r"\s+", "", text)
    cjk = len(_CJK.findall(compact))
    latin = len(_LATIN.findall(compact))
    normalized = language.casefold()
    if normalized.startswith(("zh", "ja", "ko")):
        return latin >= 30 and cjk == 0
    if normalized.startswith(("en", "de", "fr", "es", "it", "pt")):
        return cjk >= 30 and latin == 0
    return False


def _canonical_plan_order(planned_units: Iterable[Mapping[str, Any]]) -> list[str]:
    """Return a deterministic preorder of a validated composition graph.

    The list order supplied by a model is not an ordering contract.  A writer
    must receive the same parent/order traversal every time, otherwise a
    valid plan can still be rendered as a bag of independent cards.
    """
    rows = list(planned_units)
    children: dict[str | None, list[Mapping[str, Any]]] = {}
    for row in rows:
        children.setdefault(row.get("parent_unit_id"), []).append(row)
    for siblings in children.values():
        siblings.sort(key=lambda row: (row.get("order", 0), row.get("planned_unit_id", "")))
    result: list[str] = []

    def visit(row: Mapping[str, Any]) -> None:
        result.append(str(row["planned_unit_id"]))
        for child in children.get(row["planned_unit_id"], []):
            visit(child)

    for root in children.get(None, []):
        visit(root)
    # A validated graph should make this impossible.  Keeping the guard here
    # makes this helper safe when a caller uses it before full validation.
    if len(result) != len(rows):
        missing = {str(row.get("planned_unit_id")) for row in rows} - set(result)
        result.extend(sorted(missing))
    return result


def _add_projection_gap(gaps: list[dict[str, str]], subject_id: str, reason: str) -> None:
    if not any(row["subject_id"] == subject_id and row["reason"] == reason for row in gaps):
        gaps.append({"subject_id": subject_id, "reason": reason})


def _resolve_payload_rows(
    rows: Iterable[Any],
    payloads: Mapping[str, Any] | Iterable[Any] | None,
    *,
    id_fields: tuple[str, ...] = ("id",),
) -> tuple[list[Any], list[str]]:
    """Resolve route references without turning an ID into invented prose."""
    if payloads is None:
        return [], [str(row) for row in rows]
    if isinstance(payloads, Mapping):
        index = {str(key): value for key, value in payloads.items()}
    else:
        index = {}
        for value in payloads:
            if isinstance(value, Mapping):
                for field in id_fields:
                    if value.get(field) is not None:
                        index[str(value[field])] = value
                        break
    resolved: list[Any] = []
    missing: list[str] = []
    for ref in rows:
        key = str(ref)
        if isinstance(ref, Mapping):
            for field in id_fields:
                if ref.get(field) is not None:
                    key = str(ref[field])
                    break
        value = index.get(key)
        if value is None:
            missing.append(key)
        else:
            resolved.append(value)
    return resolved, missing


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_exact_fingerprint(value: Mapping[str, Any], field: str) -> None:
    if value.get(field) != fingerprint_without(dict(value), field):
        raise ValidationError(f"{field} does not bind the exact current object")


def _ids(rows: Iterable[Mapping[str, Any]], field: str, label: str) -> tuple[str, ...]:
    values = tuple(str(row.get(field, "")) for row in rows)
    if not all(values) or len(values) != len(set(values)):
        raise ValidationError(f"{label} ids must be non-empty and unique")
    return values


def validate_reader_intent(value: Any) -> dict[str, Any]:
    intent = require_mapping(value, "ReaderIntent")
    require_schema("reader-intent.schema.json", intent, label="ReaderIntent")
    _require_exact_fingerprint(intent, "intent_fingerprint")
    extent = intent["extent"]
    if not extent["minimum"] <= extent["target"] <= extent["maximum"]:
        raise ValidationError("ReaderIntent extent must satisfy minimum <= target <= maximum")
    rows = intent["structure"]["requested_outline"]
    outline_ids = set(_ids(rows, "outline_id", "outline"))
    for row in rows:
        parent = row["parent_outline_id"]
        if parent is not None and parent not in outline_ids:
            raise ValidationError(f"outline row {row['outline_id']} has an unknown parent")
    parent_of = {row["outline_id"]: row["parent_outline_id"] for row in rows}
    for outline_id in outline_ids:
        seen: set[str] = set()
        current: str | None = outline_id
        while current is not None:
            if current in seen:
                raise ValidationError("ReaderIntent outline contains a parent cycle")
            seen.add(current)
            current = parent_of.get(current)
    return intent


def validate_writing_request(value: Any) -> dict[str, Any]:
    request = require_mapping(value, "WritingRequest")
    require_schema("writing-request.schema.json", request, label="WritingRequest")
    validate_reader_intent(request["reader_intent"])
    if request["reader_intent"]["intent_fingerprint"] == request["request_fingerprint"]:
        raise ValidationError("request_fingerprint must bind the whole request, not alias ReaderIntent")
    _require_exact_fingerprint(request, "request_fingerprint")
    deliverable = dict(request["terminal_deliverable"])
    if deliverable["fingerprint"] != fingerprint_without(deliverable, "fingerprint"):
        raise ValidationError("terminal_deliverable fingerprint is not current")
    return request


def validate_composition_plan(
    value: Any,
    *,
    reader_intent: Mapping[str, Any],
    content_unit_ids: Iterable[str],
    limitation_ids: Iterable[str],
) -> dict[str, Any]:
    plan = require_mapping(value, "CompositionPlan")
    require_schema("composition-plan.schema.json", plan, label="CompositionPlan")
    _require_exact_fingerprint(plan, "plan_fingerprint")
    intent = validate_reader_intent(reader_intent)
    if plan["reader_intent_fingerprint"] != intent["intent_fingerprint"]:
        raise ValidationError("CompositionPlan does not bind the current ReaderIntent")
    if plan["final_owner"] not in FINAL_OWNERS:
        raise ValidationError("CompositionPlan has an unknown final owner")
    material_conflicts = [row for row in plan["unresolved_conflicts"] if row["material"]]
    if material_conflicts:
        raise ValidationError("material ReaderIntent conflicts must be resolved before drafting")

    planned = plan["planned_units"]
    planned_ids = set(_ids(planned, "planned_unit_id", "planned unit"))
    by_id = {row["planned_unit_id"]: row for row in planned}
    parent_orders: set[tuple[str | None, int]] = set()
    for unit in planned:
        key = (unit["parent_unit_id"], unit["order"])
        if key in parent_orders:
            raise ValidationError("planned units must have unique order within each parent")
        parent_orders.add(key)
        parent = unit["parent_unit_id"]
        if parent is not None and parent not in planned_ids:
            raise ValidationError(f"planned unit {unit['planned_unit_id']} has an unknown parent")
        for ref in unit.get("downstream_unit_ids", []):
            if ref == unit["planned_unit_id"]:
                raise ValidationError(f"planned unit {unit['planned_unit_id']} cannot depend on itself")
            if ref not in planned_ids:
                raise ValidationError(f"planned unit {unit['planned_unit_id']} has an unknown downstream unit")
    for unit_id in planned_ids:
        seen: set[str] = set()
        current: str | None = unit_id
        while current is not None:
            if current in seen:
                raise ValidationError("CompositionPlan parent graph contains a cycle")
            seen.add(current)
            current = by_id[current]["parent_unit_id"]
    outline_coverage = {
        outline_id
        for unit in planned
        for outline_id in unit["source_outline_ids"]
    }
    required_outline_ids = {
        row["outline_id"]
        for row in intent["structure"]["requested_outline"]
        if row["required"]
    }
    missing_outline = sorted(required_outline_ids - outline_coverage)
    if missing_outline:
        raise ValidationError(f"required ReaderIntent outline rows are not planned: {missing_outline}")

    required_content = set(content_unit_ids)
    _ids(plan["content_dispositions"], "content_unit_id", "content disposition")
    disposition_by_id = {row["content_unit_id"]: row for row in plan["content_dispositions"]}
    if set(disposition_by_id) != required_content:
        raise ValidationError("CompositionPlan content dispositions must exactly cover current content units")
    consumed_content = {
        content_id
        for unit in planned
        for content_id in unit["content_unit_ids"]
    }
    for unit in planned:
        for outline_id in unit.get("source_outline_ids", []):
            if outline_id not in {row["outline_id"] for row in intent["structure"]["requested_outline"]}:
                raise ValidationError(f"planned unit {unit['planned_unit_id']} references unknown outline")
        for content_id in unit.get("content_unit_ids", []):
            if content_id not in required_content:
                raise ValidationError(f"planned unit {unit['planned_unit_id']} references unknown content unit")
        for limitation_id in unit.get("limitation_ids", []):
            if limitation_id not in set(limitation_ids):
                raise ValidationError(f"planned unit {unit['planned_unit_id']} references unknown limitation")
        if unit["presentation_mode"] in {"list", "table", "appendix"}:
            policy = intent["list_policy"]
            if policy == "prose_default" and unit["planned_unit_id"] not in plan["allowed_list_zones"]:
                raise ValidationError(f"planned list/table unit {unit['planned_unit_id']} is outside an allowed zone")
    for content_id, disposition in disposition_by_id.items():
        kind = disposition["disposition"]
        planned_refs = disposition.get("planned_unit_ids", [])
        if any(unit_id not in planned_ids for unit_id in planned_refs):
            raise ValidationError(f"content disposition {content_id} references an unknown planned unit")
        if kind in VISIBLE_CONTENT_DISPOSITIONS:
            if content_id not in consumed_content or not planned_refs:
                raise ValidationError(f"visible content unit {content_id} lacks a planned unit")
        elif kind in HIDDEN_CONTENT_DISPOSITIONS and content_id in consumed_content:
            raise ValidationError(
                f"hidden content unit {content_id} cannot be attached to a planned writer unit"
            )

    known_limitations = set(limitation_ids)
    placed_limitations = {
        limitation_id
        for unit in planned
        for limitation_id in unit["limitation_ids"]
    }
    if not known_limitations <= placed_limitations:
        raise ValidationError(
            f"limitations lack planned placement: {sorted(known_limitations - placed_limitations)}"
        )
    limitation_rows = plan.get("limitation_dispositions", [])
    if set(limitation_ids) and not limitation_rows:
        raise ValidationError("CompositionPlan must provide one limitation disposition per native limitation")
    if limitation_rows:
        known_limitations = set(limitation_ids)
        seen_limitations: set[str] = set()
        for row in limitation_rows:
            lid = row["limitation_id"]
            if lid not in known_limitations or lid in seen_limitations:
                raise ValidationError(f"limitation dispositions must exactly cover each native limitation: {lid}")
            seen_limitations.add(lid)
            if row["disposition"] in {"body", "note", "appendix", "merged", "implied_by_scope"} and not row["destination_unit_ids"]:
                raise ValidationError(f"visible limitation {lid} needs destination units")
            if any(unit_id not in planned_ids for unit_id in row["destination_unit_ids"]):
                raise ValidationError(f"limitation {lid} references an unknown destination unit")
            if row["disposition"] == "merged":
                target = row["merged_into_id"]
                if not target or target not in known_limitations or target == lid:
                    raise ValidationError(f"limitation {lid} has an invalid merge target")
            elif row["merged_into_id"] is not None:
                raise ValidationError(f"limitation {lid} may only set merged_into_id when merged")
            if row["disposition"] in {"omitted", "internal"} and row["materiality"] in {"changes_answer", "changes_action", "changes_scope", "changes_strength"}:
                raise ValidationError(f"material limitation {lid} cannot be hidden")
        if seen_limitations != known_limitations:
            raise ValidationError("limitation dispositions must exactly cover current limitations")
        # A merge target must not eventually merge back into its source.
        rows_by_id = {row["limitation_id"]: row for row in limitation_rows}
        for lid in rows_by_id:
            seen: set[str] = set()
            cur = lid
            while rows_by_id[cur]["disposition"] == "merged":
                if cur in seen:
                    raise ValidationError("limitation merge graph contains a cycle")
                seen.add(cur)
                cur = rows_by_id[cur]["merged_into_id"]
    return plan


def _writer_route_projection(
    owner: str,
    route: Mapping[str, Any],
    plan: Mapping[str, Any],
    boundaries: Mapping[str, Any],
    *,
    selected_content_ids: set[str] | None = None,
    primary_content_ids: set[str] | None = None,
    gaps: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Return a bounded route view for the writer.

    Route extensions contain many IDs that are useful to model owners but are
    not themselves prose.  This function resolves IDs only when the current
    boundary contains the corresponding payload.  An unresolved reference is
    recorded as a gap, never converted into a made-up sentence.
    """
    selected = selected_content_ids or {
        str(row["content_unit_id"]) for row in boundaries.get("content_units", [])
    }
    primary = set(selected) if primary_content_ids is None else set(primary_content_ids)
    gaps = gaps if gaps is not None else []
    content_by_id = {
        str(row["content_unit_id"]): row for row in boundaries.get("content_units", [])
    }
    anchors_by_id = {
        str(row["anchor_id"]): row for row in boundaries.get("evidence_anchors", [])
    }

    def content_meaning(content_id: str) -> str | None:
        row = content_by_id.get(str(content_id))
        if row is None:
            _add_projection_gap(gaps, str(content_id), "route references an unknown content unit")
            return None
        if str(content_id) not in selected:
            return None
        meaning = row.get("safe_meaning")
        if not isinstance(meaning, str) or not meaning.strip() or WRITER_INTERNAL.search(meaning):
            _add_projection_gap(gaps, str(content_id), "route content lacks a clean reader-facing semantic payload")
            return None
        return meaning

    def anchor_payload(anchor_id: str) -> dict[str, Any] | None:
        anchor = anchors_by_id.get(str(anchor_id))
        if anchor is None:
            _add_projection_gap(gaps, str(anchor_id), "route evidence reference has no current anchor payload")
            return None
        return {
            "anchor_id": anchor["anchor_id"],
            "source_id": anchor["source_id"],
            "locator": anchor["locator"],
            "relation": anchor["relation"],
            "observed_summary": anchor["observed_summary"],
            "boundary": anchor["boundary"],
        }

    if owner == "investigation":
        answer: list[str] = []
        for content_id in route.get("bounded_answer_content_unit_ids", []):
            meaning = content_meaning(str(content_id))
            if meaning is not None and str(content_id) in primary:
                answer.append(meaning)
        evidence_strength = []
        for row in route.get("evidence_strength_rows", []):
            content_id = str(row.get("content_unit_id", ""))
            if content_id not in primary:
                continue
            if content_meaning(content_id) is None:
                continue
            evidence_strength.append({
                "content_unit_id": content_id,
                "strength": row["strength"],
                "reason": row["reason"],
            })
        alternatives = []
        alternative_ids = {str(value) for value in route.get("alternative_ids", [])}
        for row in boundaries.get("alternatives", []):
            if str(row["alternative_id"]) in alternative_ids and any(
                str(content_id) in primary for content_id in row.get("content_unit_ids", [])
            ):
                alternatives.append({
                    "alternative_id": row["alternative_id"],
                    "meaning": row["safe_meaning"],
                    "status": row["status"],
                    "content_unit_ids": [
                        content_id for content_id in row.get("content_unit_ids", [])
                        if str(content_id) in primary
                    ],
                })
        missing_alternatives = alternative_ids - {
            str(row["alternative_id"]) for row in alternatives
        }
        for alternative_id in sorted(missing_alternatives):
            _add_projection_gap(gaps, alternative_id, "selected alternative has no current content payload")
        return {
            "answer": answer,
            "evidence_strength": evidence_strength,
            "alternatives": alternatives,
            "recheck_conditions": [
                {
                    "action_id": row["action_id"],
                    "condition": row["condition"],
                    "action": row["action"],
                    "planned_unit_id": row["planned_unit_id"],
                }
                for row in route.get("fallback_or_recheck_units", [])
            ],
        }
    if owner == "academic-writing":
        hierarchy = []
        planned_ids = {str(row["planned_unit_id"]) for row in plan.get("planned_units", [])}
        for row in route.get("hierarchy", []):
            unit_id = str(row["unit_id"])
            if unit_id not in planned_ids:
                _add_projection_gap(gaps, unit_id, "academic hierarchy references an unknown planned unit")
                continue
            evidence = []
            for anchor_id in row.get("evidence_ids", []):
                payload = anchor_payload(str(anchor_id))
                if payload is not None:
                    evidence.append(payload)
            hierarchy.append({
                "unit_id": unit_id,
                "parent_unit_id": row["parent_unit_id"],
                "contribution": row["research_question_contribution"],
                "incoming_dependency": row["incoming_dependency"],
                "new_claim_or_warrant": row["new_claim_or_warrant"],
                "evidence": evidence,
                "qualification": dict(row["qualification"]),
                "downstream_consumer_ids": list(row["downstream_consumer_ids"]),
            })
        jobs = []
        for row in route.get("figure_table_jobs", []):
            jobs.append({
                "artifact_unit_id": row["artifact_unit_id"],
                "job": row["job"],
                "consumer_unit_ids": list(row["consumer_unit_ids"]),
            })
        return {
            "question": route.get("research_question", plan.get("central_question")),
            "contribution": route.get("central_contribution", plan.get("central_throughline")),
            "hierarchy": hierarchy,
            "method_and_figure_table_jobs": jobs,
        }
    if owner == "fiction-writing":
        voice_ref = route.get("voice_contract_ref", "")
        voice_payload = (
            route.get("voice_contract")
            or route.get("voice_contract_payload")
            or route.get("voice")
        )
        if voice_ref and not isinstance(voice_payload, Mapping):
            _add_projection_gap(gaps, str(voice_ref), "fiction voice reference has no current POV/voice payload")
        voice = dict(voice_payload) if isinstance(voice_payload, Mapping) else {}
        return {
            "voice": voice,
            # An unresolved reference is retained only in ``gaps`` above;
            # sending the opaque ID to the writer would invite it to infer a
            # voice contract from an identifier.
            "voice_contract_ref": voice_ref if isinstance(voice_payload, Mapping) else None,
            "movements": [
                {
                    "movement_id": row["movement_id"],
                    "unit_ids": list(row["unit_ids"]),
                    "entry_state": row["entry_story_state"],
                    "pressure": row["primary_pressure"],
                    "reader_state_change": row["reader_state_change"],
                    "irreversible_change": row["irreversible_change"],
                    "exit_state": row["exit_story_state"],
                    "downstream_unit_ids": list(row["downstream_unit_ids"]),
                }
                for row in route.get("story_movements", [])
            ],
            "unit_plans": [
                {
                    "unit_id": row["unit_id"],
                    "contribution": row["contribution"],
                    "entry_state": row["entry_state"],
                    "exit_state": row["exit_state"],
                    "desire": row["focal_desire"],
                    "pressure_or_cost": row["resistance_or_cost"],
                    "reader_state_before": row["reader_state_before"],
                    "reader_state_after": row["reader_state_after"],
                    "open_questions_in": list(row["open_questions_in"]),
                    "open_questions_out": list(row["open_questions_out"]),
                    "voice_owner": row["voice_owner"],
                    "rhythm_role": row["rhythm_role"],
                    "prohibited_reveals": list(row["prohibited_reveals"]),
                    "downstream_unit_ids": list(row["downstream_unit_ids"]),
                }
                for row in route.get("unit_plans", [])
            ],
            "promises_and_reveals": [
                {
                    "promise_or_reveal_id": row["promise_or_reveal_id"],
                    "setup_unit_ids": list(row["setup_unit_ids"]),
                    "movement_unit_ids": list(row["movement_unit_ids"]),
                    "payoff_unit_ids": list(row["payoff_unit_ids"]),
                    "status": row["status"],
                }
                for row in route.get("promise_and_reveal_bindings", [])
            ],
            "realization_boundaries": list(route.get("realization_boundaries", [])),
        }

    sections = list(route.get("body_sections", []))
    # IDs alone are not useful writer material.  Resolve each declared
    # traveler/route/local payload when the route supplies an index; otherwise
    # leave a concrete gap for the native owner to fill.
    resolved_refs: dict[tuple[str, str], list[Any]] = {}
    for section in sections:
        section_id = str(section["section_id"])
        for field, payload_keys, label in (
            ("route_refs", ("route_nodes", "routes", "route_options"), "route"),
            ("traveler_fit_refs", ("traveler_profiles", "traveler_fits", "traveler_conditions"), "traveler fit"),
            ("local_texture_refs", ("local_texture_payloads", "local_textures", "local_texture_candidates"), "local texture"),
        ):
            refs = list(section.get(field, []))
            payloads = next((route.get(key) for key in payload_keys if route.get(key) is not None), None)
            if refs and payloads is None:
                for ref in refs:
                    _add_projection_gap(gaps, str(ref), f"travel {label} reference has no current payload")
                resolved_refs[(section_id, field)] = []
            elif refs:
                _resolved, missing = _resolve_payload_rows(refs, payloads, id_fields=("id", "ref", "candidate_id", "profile_id"))
                resolved_refs[(section_id, field)] = _resolved
                for ref in missing:
                    _add_projection_gap(gaps, ref, f"travel {label} reference has no current payload")
            else:
                resolved_refs[(section_id, field)] = []
    local_refs = {
        str(ref)
        for section in sections
        for ref in section.get("local_texture_refs", [])
    }
    local_ids = {
        str(row.get("candidate_id"))
        for row in route.get("local_texture_candidates", [])
    }
    for ref in sorted(local_refs - local_ids):
        _add_projection_gap(gaps, ref, "travel local name has no current candidate payload")
    route_node_payloads = next(
        (route.get(key) for key in ("route_nodes", "routes", "route_options") if route.get(key) is not None),
        None,
    )
    fallback_reachability: dict[str, list[Any]] = {}
    if route_node_payloads is not None:
        for row in route.get("risk_fallback_bindings", []):
            resolved, missing = _resolve_payload_rows(
                row.get("reachable_from_route_node_ids", []),
                route_node_payloads,
                id_fields=("id", "ref", "node_id", "route_id"),
            )
            fallback_reachability[str(row["binding_id"])] = resolved
            for ref in missing:
                _add_projection_gap(gaps, ref, "travel fallback reachability has no current route payload")
    else:
        for row in route.get("risk_fallback_bindings", []):
            refs = list(row.get("reachable_from_route_node_ids", []))
            fallback_reachability[str(row["binding_id"])] = []
            for ref in refs:
                _add_projection_gap(gaps, str(ref), "travel fallback reachability has no current route payload")
    return {
        "traveler_conditions": [
            {
                "section_id": row["section_id"],
                "section_role": row["section_role"],
                "incoming_state": row["incoming_traveler_state"],
                "outgoing_state": row["outgoing_traveler_state"],
                "traveler_fit": resolved_refs[(str(row["section_id"]), "traveler_fit_refs")],
            }
            for row in sections
        ],
        "route_handoffs": [
            {
                "section_id": row["section_id"],
                "route_payloads": resolved_refs[(str(row["section_id"]), "route_refs")],
                "local_texture_payloads": resolved_refs[(str(row["section_id"]), "local_texture_refs")],
                "next_consumer_ids": list(row["next_consumer_ids"]),
            }
            for row in sections
        ],
        "pace_and_timing": [
            {
                "section_id": row["section_id"],
                "section_kind": row["section_kind"],
                "section_role": row["section_role"],
                "timing": row.get("timing", row.get("operating_times", row.get("key_times", []))),
                "transport": row.get("transport", row.get("transport_notes", [])),
                "rest": row.get("rest", row.get("rest_points", [])),
            }
            for row in sections
        ],
        "local_names": [
            {
                "candidate_id": row["candidate_id"],
                "canonical_name": row["canonical_name"],
                "local_name": row["local_name"],
                "accepted_aliases": list(row["accepted_aliases"]),
                "category": row["category"],
                "intended_section_ids": list(row["intended_section_ids"]),
            }
            for row in route.get("local_texture_candidates", [])
            if not local_refs or str(row["candidate_id"]) in local_refs
        ],
        "reachable_fallbacks": [
            {
                "binding_id": row["binding_id"],
                "risk_id": row["risk_id"],
                "affected_section_ids": list(row["affected_section_ids"]),
                "trigger": row["trigger"],
                "affected_travelers": list(row["affected_travelers"]),
                "mitigation": row["mitigation"],
                "fallback_id": row["fallback_id"],
                "reachable_from_route_nodes": fallback_reachability[str(row["binding_id"])],
                "evidence_mode": row["evidence_mode"],
            }
            for row in route.get("risk_fallback_bindings", [])
        ],
        "source_and_recheck_placement": {
            "source_boundary": route.get("source_boundary_placement"),
            "recheck": route.get("recheck_placement"),
            "appendix_jobs": [
                {
                    "section_id": row["section_id"],
                    "operational_kinds": list(row["operational_kinds"]),
                    "consumer_section_ids": list(row["consumer_section_ids"]),
                }
                for row in route.get("appendix_sections", [])
            ],
        },
    }


def build_writer_input(
    *,
    owner: str,
    intent: Mapping[str, Any],
    plan: Mapping[str, Any],
    route: Mapping[str, Any],
    boundaries: Mapping[str, Any],
    native_handoff: Mapping[str, Any] | None = None,
    native_handoff_mapping: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the sole reader-facing writer projection.

    ``content_units`` is the native inventory; ``content_dispositions`` is the
    selection authority.  This function intentionally keeps unresolved
    required inputs as explicit gaps so a caller can persist a blocked brief;
    it never turns missing payloads into an implicit model instruction.
    """
    gaps: list[dict[str, str]] = []
    content_by_id = {
        str(row["content_unit_id"]): row for row in boundaries.get("content_units", [])
    }
    disposition_by_id = {
        str(row["content_unit_id"]): row for row in plan.get("content_dispositions", [])
    }
    selected_ids: set[str] = set()
    selected: list[dict[str, Any]] = []
    for content_id, row in content_by_id.items():
        disposition_row = disposition_by_id.get(content_id)
        if disposition_row is None:
            _add_projection_gap(gaps, content_id, "content unit has no current editorial disposition")
            continue
        disposition = str(disposition_row["disposition"])
        if disposition not in VISIBLE_CONTENT_DISPOSITIONS:
            if row.get("required") or disposition in {"conflict", "blocked", "deferred"}:
                _add_projection_gap(gaps, content_id, f"required content is {disposition} and cannot enter the writer")
            continue
        meaning = row.get("safe_meaning", "")
        if not isinstance(meaning, str) or not meaning.strip() or WRITER_INTERNAL.search(meaning):
            if row.get("required"):
                _add_projection_gap(gaps, content_id, "required content lacks a clean reader-facing semantic meaning")
            continue
        planned_ids = list(disposition_row.get("planned_unit_ids", []))
        if not planned_ids:
            _add_projection_gap(gaps, content_id, "visible content has no planned writer destination")
            continue
        selected_ids.add(content_id)
        selected.append({
            "content_unit_id": content_id,
            "meaning": meaning,
            "required": bool(row["required"]),
            "disposition": disposition,
            "planned_unit_ids": planned_ids,
            "evidence_anchor_ids": list(row.get("evidence_anchor_ids", [])),
            "alternative_ids": list(row.get("alternative_ids", [])),
            "limitation_ids": list(row.get("limitation_ids", [])),
        })

    anchors_by_id = {
        str(row["anchor_id"]): row for row in boundaries.get("evidence_anchors", [])
    }
    evidence: list[dict[str, Any]] = []
    for row in selected:
        for anchor_id in row["evidence_anchor_ids"]:
            anchor = anchors_by_id.get(str(anchor_id))
            if anchor is None:
                _add_projection_gap(gaps, str(anchor_id), "selected content evidence has no current anchor payload")
                continue
            evidence.append({
                "content_unit_id": row["content_unit_id"],
                "anchor_id": anchor["anchor_id"],
                "source_id": anchor["source_id"],
                "locator": anchor["locator"],
                "relation": anchor["relation"],
                "observed_summary": anchor["observed_summary"],
                "boundary": anchor["boundary"],
            })

    plan_order = _canonical_plan_order(plan.get("planned_units", []))
    unit_by_id = {str(row["planned_unit_id"]): row for row in plan.get("planned_units", [])}
    composition_units = [
        {
            key: unit_by_id[unit_id][key]
            for key in (
                "planned_unit_id", "parent_unit_id", "order", "title", "reader_job",
                "content_unit_ids", "limitation_ids", "relation_to_previous",
                "incoming_reader_state", "outgoing_reader_state", "downstream_unit_ids",
                "presentation_mode", "target_extent",
            )
        }
        for unit_id in plan_order
        if unit_id in unit_by_id
    ]

    boundary_limitations = {
        str(row["limitation_id"]): row for row in boundaries.get("limitations", [])
    }
    limitations: list[dict[str, Any]] = []
    for row in plan.get("limitation_dispositions", []):
        disposition = str(row["disposition"])
        if disposition in {"internal", "omitted", "blocked"}:
            if row["materiality"] != "process_only":
                _add_projection_gap(
                    gaps,
                    str(row["limitation_id"]),
                    "material limitation cannot be hidden from the writer",
                )
            continue
        source = boundary_limitations.get(str(row["limitation_id"]))
        if source is None:
            _add_projection_gap(gaps, str(row["limitation_id"]), "limitation has no current boundary payload")
            continue
        limitations.append({
            "limitation_id": row["limitation_id"],
            "meaning": source["safe_meaning"],
            "affected_content_unit_ids": [
                content_id for content_id in source["affected_content_unit_ids"]
                if str(content_id) in selected_ids
            ],
            "required_placement": source["required_placement"],
            "materiality": row["materiality"],
            "materiality_reason": row["materiality_reason"],
            "disposition": disposition,
            "destination_unit_ids": list(row["destination_unit_ids"]),
            "merged_into_id": row.get("merged_into_id"),
            "realization_requirement": row["realization_requirement"],
        })

    selected_content_ids = set(selected_ids)
    citations = []
    for row in boundaries.get("citation_duties", []):
        if any(str(content_id) in selected_content_ids for content_id in row["content_unit_ids"]):
            citations.append({
                **row,
                "content_unit_ids": [
                    content_id for content_id in row["content_unit_ids"]
                    if str(content_id) in selected_content_ids
                ],
            })
        elif any(str(content_id) not in selected_content_ids for content_id in row["content_unit_ids"]):
            _add_projection_gap(gaps, str(row["citation_id"]), "citation duty points to content omitted from the writer")

    exact_obligations = {
        "must_preserve": [
            {
                **row,
                "content_unit_ids": [
                    content_id for content_id in row["content_unit_ids"]
                    if str(content_id) in selected_content_ids
                ],
            }
            for row in boundaries.get("must_preserve_tokens", [])
            if any(str(content_id) in selected_content_ids for content_id in row["content_unit_ids"])
        ],
        "verbatim": [
            {
                **row,
                "content_unit_ids": [
                    content_id for content_id in row["content_unit_ids"]
                    if str(content_id) in selected_content_ids
                ],
            }
            for row in boundaries.get("verbatim_obligations", [])
            if any(str(content_id) in selected_content_ids for content_id in row["content_unit_ids"])
        ],
    }
    forbidden_claims = [
        {
            **row,
            "content_unit_ids": [
                content_id for content_id in row["affected_content_unit_ids"]
                if str(content_id) in selected_content_ids
            ],
        }
        for row in boundaries.get("prohibited_overclaims", [])
        if any(str(content_id) in selected_content_ids for content_id in row["affected_content_unit_ids"])
    ]

    writer_input = {
        "schema_version": "1.1",
        "reader_intent": dict(intent),
        "selected_content": selected,
        "composition": {
            "central_question": plan["central_question"],
            "central_throughline": plan["central_throughline"],
            "artifact_form": plan["artifact_form"],
            "opening_job": plan["opening_job"],
            "conclusion_job": plan["conclusion_job"],
            "body_unit_order": plan_order,
            "units": composition_units,
        },
        "limitations": limitations,
        "citations": citations,
        "evidence": evidence,
        "exact_obligations": exact_obligations,
        "forbidden_claims": forbidden_claims,
        "route_semantics": _writer_route_projection(
            owner, route, plan, boundaries,
            selected_content_ids=selected_content_ids,
            primary_content_ids={
                str(row["content_unit_id"])
                for row in selected
                if row.get("disposition") in {"consumed", "body"}
            },
            gaps=gaps,
        ),
        "gaps": gaps,
    }
    if native_handoff is not None:
        writer_input["native_handoff"] = dict(native_handoff)
        writer_input["native_handoff_mapping"] = [
            dict(row) for row in (native_handoff_mapping or ())
        ]
    return writer_input


def validate_route_composition(
    value: Any,
    *,
    owner: str,
    reader_intent_fingerprint: str,
    composition_plan_fingerprint: str,
    composition_plan: Mapping[str, Any] | None = None,
    content_boundaries: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if owner not in ROUTE_SCHEMA:
        raise ValidationError(f"unknown final owner: {owner}")
    composition = require_mapping(value, f"{owner} composition")
    require_schema(ROUTE_SCHEMA[owner], composition, label=f"{owner} composition")
    _require_exact_fingerprint(composition, "extension_fingerprint")
    if composition["final_owner"] != owner:
        raise ValidationError("route composition belongs to a sibling final owner")
    if composition["reader_intent_fingerprint"] != reader_intent_fingerprint:
        raise ValidationError("route composition does not bind the current ReaderIntent")
    if composition["composition_plan_fingerprint"] != composition_plan_fingerprint:
        raise ValidationError("route composition does not bind the current CompositionPlan")
    if composition_plan is not None:
        planned_ids = {row["planned_unit_id"] for row in composition_plan.get("planned_units", [])}
        def check_ids(values: Iterable[str], label: str) -> None:
            unknown = sorted(set(values) - planned_ids)
            if unknown:
                raise ValidationError(f"{owner} composition has unknown {label}: {unknown}")
        if owner == "investigation":
            check_ids((row["planned_unit_id"] for row in composition.get("fallback_or_recheck_units", [])), "planned unit")
        elif owner == "academic-writing":
            check_ids((row["unit_id"] for row in composition.get("hierarchy", [])), "hierarchy unit")
            check_ids((ref for row in composition.get("hierarchy", []) for ref in row.get("downstream_consumer_ids", [])), "downstream unit")
            if content_boundaries is not None:
                known_evidence = {row["anchor_id"] for row in content_boundaries.get("evidence_anchors", [])}
                unknown = sorted({ref for row in composition.get("hierarchy", []) for ref in row.get("evidence_ids", [])} - known_evidence)
                if unknown:
                    raise ValidationError(f"academic composition has unknown evidence ids: {unknown}")
            for row in composition.get("hierarchy", []):
                qualification = row.get("qualification")
                if not isinstance(qualification, Mapping) or qualification.get("status") not in {"required", "not_applicable"} or not qualification.get("reason"):
                    raise ValidationError(f"academic hierarchy unit {row['unit_id']} has invalid structured qualification")
        elif owner == "fiction-writing":
            check_ids((ref for row in composition.get("story_movements", []) for ref in row["unit_ids"]), "movement unit")
            check_ids((row["unit_id"] for row in composition.get("unit_plans", [])), "unit plan")
            check_ids((ref for row in composition.get("unit_plans", []) for ref in row.get("downstream_unit_ids", [])), "downstream unit")
            for row in composition.get("promise_and_reveal_bindings", []):
                check_ids((ref for ref in (*row["setup_unit_ids"], *row["movement_unit_ids"], *row["payoff_unit_ids"])), "promise/reveal unit")
        elif owner == "travel-guide":
            check_ids((row["section_id"] for row in composition.get("body_sections", [])), "body section")
            check_ids((ref for row in composition.get("body_sections", []) for ref in row.get("next_consumer_ids", [])), "next consumer")
    return composition


def build_reader_brief(
    *,
    route_decision: Mapping[str, Any],
    content_boundaries: Mapping[str, Any],
    composition_plan: Mapping[str, Any],
    route_composition: Mapping[str, Any],
    native_dependency_receipt_fingerprints: Iterable[str],
    content_authority_fingerprints: Mapping[str, str],
    brief_id: str,
    native_handoff: Mapping[str, Any] | None = None,
    native_plan: Mapping[str, Any] | None = None,
    native_handoff_mapping: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    decision = require_mapping(route_decision, "RouteDecision")
    require_schema("route-decision.schema.json", decision, label="RouteDecision")
    _require_exact_fingerprint(decision, "decision_fingerprint")
    if decision["status"] != "current" or decision["final_owner"] not in FINAL_OWNERS:
        raise ValidationError("ReaderBrief requires one current final owner")
    intent = validate_reader_intent(decision["reader_intent"])
    if decision["reader_intent_fingerprint"] != intent["intent_fingerprint"]:
        raise ValidationError("RouteDecision copied a different ReaderIntent fingerprint")
    boundaries = require_mapping(content_boundaries, "content boundaries")
    content_ids = _ids(boundaries.get("content_units", ()), "content_unit_id", "content unit")
    limitation_ids = _ids(boundaries.get("limitations", ()), "limitation_id", "limitation")
    plan = validate_composition_plan(
        composition_plan,
        reader_intent=intent,
        content_unit_ids=content_ids,
        limitation_ids=limitation_ids,
    )
    owner = decision["final_owner"]
    if native_handoff is not None:
        # The native plan is optional only for callers that already resolved
        # the opaque provider result.  When it is supplied, the adapter
        # rebuilds the handoff so a caller cannot alter units, dispositions,
        # or native identities and then merely re-sign the envelope.
        from researchguard_handoff import validate_researchguard_handoff

        native_value = require_mapping(native_handoff, "ResearchGuard semantic handoff")
        if native_value.get("stage") not in {None, "semantic"}:
            raise ValidationError("ReaderBrief accepts only the stage-1 semantic ResearchGuard handoff")
        if native_value.get("status") != "current_pass":
            raise ValidationError("blocked ResearchGuard handoff cannot enter ReaderBrief")
        if native_value.get("reader_intent_fingerprint") != intent["intent_fingerprint"]:
            raise ValidationError("ResearchGuard handoff does not bind the current ReaderIntent")
        if native_plan is not None:
            validate_researchguard_handoff(
                native_value,
                native_plan,
                reader_intent_fingerprint=intent["intent_fingerprint"],
            )
        else:
            if native_value.get("handoff_fingerprint") != fingerprint_without(dict(native_value), "handoff_fingerprint"):
                raise ValidationError("ResearchGuard handoff fingerprint is stale")
        if native_handoff_mapping is None:
            raise ValidationError("a ResearchGuard handoff requires an explicit native-to-reader unit mapping")
        # Validate the mapping against the current composition before the
        # writer projection is constructed.  The full binding (including the
        # brief and writer fingerprints) is emitted by bind_handoff_consumption
        # after this function returns.
        planned_ids = {
            str(row["planned_unit_id"])
            for row in plan.get("planned_units", [])
        }
        native_ids = {
            str(row["unit_id"])
            for row in native_value.get("units", [])
            if isinstance(row, Mapping) and row.get("unit_id")
        }
        mapping_rows = list(native_handoff_mapping)
        mapped_native = {
            str(row.get("native_unit_id"))
            for row in mapping_rows
            if isinstance(row, Mapping)
        }
        if mapped_native != native_ids:
            raise ValidationError("native-to-reader unit mapping must exactly cover the current native units")
        for row in mapping_rows:
            if not isinstance(row, Mapping) or not isinstance(row.get("planned_unit_ids"), list) or not row["planned_unit_ids"]:
                raise ValidationError("native-to-reader unit mapping has an invalid planned unit list")
            if any(str(item) not in planned_ids for item in row["planned_unit_ids"]):
                raise ValidationError("native-to-reader unit mapping references an unknown planned unit")
        mapped_planned = {
            str(item)
            for row in mapping_rows
            if isinstance(row, Mapping)
            for item in row.get("planned_unit_ids", [])
        }
        if mapped_planned != planned_ids:
            raise ValidationError("native-to-reader unit mapping must cover every current planned unit")
    route = validate_route_composition(
        route_composition,
        owner=owner,
        reader_intent_fingerprint=intent["intent_fingerprint"],
        composition_plan_fingerprint=plan["plan_fingerprint"],
        composition_plan=plan,
        content_boundaries=boundaries,
    )
    route_envelope = {
        "owner": owner,
        "profile": route[ROUTE_PROFILE_FIELD[owner]],
        "schema_name": ROUTE_SCHEMA[owner],
        "extension_fingerprint": route["extension_fingerprint"],
        "native_receipt_fingerprints": list(native_dependency_receipt_fingerprints),
    }
    writer_input = build_writer_input(
        owner=owner,
        intent=intent,
        plan=plan,
        route=route,
        boundaries=boundaries,
        native_handoff=native_handoff,
        native_handoff_mapping=native_handoff_mapping,
    )
    brief = {
        "schema_version": "2.0",
        "brief_id": brief_id,
        "route_decision_fingerprint": decision["decision_fingerprint"],
        "reader_intent_fingerprint": intent["intent_fingerprint"],
        "final_owner": owner,
        "terminal_deliverable": decision["terminal_deliverable"],
        "reader_intent": intent,
        "content_boundaries": boundaries,
        "composition_plan": plan,
        "route_extension": route_envelope,
        "native_dependency_receipt_fingerprints": list(native_dependency_receipt_fingerprints),
        "content_authority_fingerprints": dict(content_authority_fingerprints),
        "writer_input": writer_input,
        "writer_input_fingerprint": fingerprint(writer_input),
    }
    brief["brief_fingerprint"] = fingerprint(brief)
    validate_writer_input(writer_input, composition_plan=plan)
    require_schema("reader-brief.schema.json", brief, label="ReaderBrief")
    return brief


def validate_writer_input(value: Any, *, reader_brief: Mapping[str, Any] | None = None, composition_plan: Mapping[str, Any] | None = None) -> dict[str, Any]:
    writer_input = require_mapping(value, "writer_input")
    required = {"schema_version", "reader_intent", "selected_content", "composition", "limitations", "citations", "route_semantics", "gaps"}
    allowed = required | {
        "evidence", "exact_obligations", "forbidden_claims",
        "native_handoff", "native_handoff_mapping",
    }
    if not required <= set(writer_input) or set(writer_input) - allowed or writer_input.get("schema_version") not in {"1.0", "1.1"}:
        raise ValidationError("writer_input contains unsupported or missing fields")
    if "writer_input_fingerprint" in writer_input:
        raise ValidationError("writer_input must not contain its own fingerprint")
    intent = validate_reader_intent(writer_input["reader_intent"])
    selected_rows = list(writer_input["selected_content"])
    # Keep the id collection set-like for the boundary and hidden-content
    # membership checks below.  `_ids` returns a tuple for stable ordering,
    # but comparing that tuple with the ReaderBrief boundary set raises a
    # runtime TypeError on the native handoff path.
    selected_ids = set(_ids(selected_rows, "content_unit_id", "writer content")) if selected_rows else set()
    for row in selected_rows:
        disposition = row.get("disposition")
        if disposition is not None and disposition not in VISIBLE_CONTENT_DISPOSITIONS:
            raise ValidationError(f"writer content {row['content_unit_id']} has a hidden disposition")
        if "planned_unit_ids" in row and not row["planned_unit_ids"]:
            raise ValidationError(f"writer content {row['content_unit_id']} has no writer destination")
        if any(not isinstance(value, str) or not value.strip() for value in row.get("evidence_anchor_ids", [])):
            raise ValidationError(f"writer content {row['content_unit_id']} has an invalid evidence reference")
    if writer_input.get("gaps") and any(
        not isinstance(row, Mapping) or not str(row.get("subject_id", "")).strip() or not str(row.get("reason", "")).strip()
        for row in writer_input["gaps"]
    ):
        raise ValidationError("writer_input gaps must identify a concrete unresolved subject")
    composition = require_mapping(writer_input["composition"], "writer_input composition")
    units = list(composition.get("units", []))
    unit_ids = _ids(units, "planned_unit_id", "writer unit") if units else ()
    body_order = composition.get("body_unit_order")
    if body_order is not None:
        if list(body_order) != list(unit_ids):
            raise ValidationError("writer_input body_unit_order must exactly match its canonical unit order")
        if len(body_order) != len(set(body_order)):
            raise ValidationError("writer_input body_unit_order contains duplicates")
    for row in units:
        parent = row.get("parent_unit_id")
        if parent is not None and parent not in unit_ids:
            raise ValidationError(f"writer_input unit {row['planned_unit_id']} has an unknown parent")
        if any(ref not in unit_ids for ref in row.get("downstream_unit_ids", [])):
            raise ValidationError(f"writer_input unit {row['planned_unit_id']} has an unknown downstream unit")
    if "evidence" in writer_input:
        evidence_ids = set()
        for row in writer_input["evidence"]:
            if row["content_unit_id"] not in selected_ids:
                raise ValidationError("writer_input evidence references content omitted from the projection")
            evidence_key = (row["content_unit_id"], row["anchor_id"])
            if evidence_key in evidence_ids:
                raise ValidationError("writer_input evidence repeats an anchor for one content unit")
            evidence_ids.add(evidence_key)
    if "native_handoff" in writer_input:
        handoff = require_mapping(writer_input["native_handoff"], "writer_input native_handoff")
        if handoff.get("status") != "current_pass":
            raise ValidationError("writer_input cannot consume a blocked ResearchGuard handoff")
        if handoff.get("reader_intent_fingerprint") != intent["intent_fingerprint"]:
            raise ValidationError("writer_input native_handoff does not bind its ReaderIntent")
        if handoff.get("handoff_fingerprint") != fingerprint_without(dict(handoff), "handoff_fingerprint"):
            raise ValidationError("writer_input native_handoff fingerprint is stale")
        mapping = writer_input.get("native_handoff_mapping")
        if not isinstance(mapping, list) or not mapping:
            raise ValidationError("writer_input native_handoff_mapping is required for a native handoff")
        native_ids = {str(row.get("unit_id")) for row in handoff.get("units", []) if isinstance(row, Mapping)}
        mapped_ids = {str(row.get("native_unit_id")) for row in mapping if isinstance(row, Mapping)}
        if mapped_ids != native_ids:
            raise ValidationError("writer_input native handoff mapping is not exhaustive")
        mapped_planned = {
            str(item)
            for row in mapping
            if isinstance(row, Mapping)
            for item in row.get("planned_unit_ids", [])
        }
        if mapped_planned != set(unit_ids):
            raise ValidationError("writer_input native handoff mapping must cover every planned unit")
    if "exact_obligations" in writer_input:
        exact = require_mapping(writer_input["exact_obligations"], "writer_input exact_obligations")
        for kind in ("must_preserve", "verbatim"):
            if kind not in exact or not isinstance(exact[kind], list):
                raise ValidationError(f"writer_input exact_obligations lacks {kind}")
    if reader_brief is not None:
        brief = require_mapping(reader_brief, "ReaderBrief")
        if brief.get("writer_input") != writer_input or brief.get("writer_input_fingerprint") != fingerprint(writer_input):
            raise ValidationError("writer_input is not the immutable ReaderBrief projection")
        boundary_ids = {
            str(row["content_unit_id"])
            for row in brief.get("content_boundaries", {}).get("content_units", [])
        }
        if not selected_ids <= boundary_ids:
            raise ValidationError("writer_input selects content outside the current boundary inventory")
        hidden_ids = {
            str(row["content_unit_id"])
            for row in brief.get("composition_plan", {}).get("content_dispositions", [])
            if row.get("disposition") not in VISIBLE_CONTENT_DISPOSITIONS
        }
        if selected_ids & hidden_ids:
            raise ValidationError("writer_input reintroduces content hidden by editorial disposition")
    if composition_plan is not None:
        expected = {row["planned_unit_id"]: row for row in composition_plan["planned_units"]}
        actual = {row["planned_unit_id"]: row for row in writer_input["composition"]["units"]}
        projection_fields = (
            "planned_unit_id", "parent_unit_id", "order", "title", "reader_job",
            "content_unit_ids", "limitation_ids", "relation_to_previous",
            "incoming_reader_state", "outgoing_reader_state", "downstream_unit_ids",
            "presentation_mode", "target_extent",
        )
        expected_projection = {
            key: {field: expected[key][field] for field in projection_fields}
            for key in expected
        }
        if set(actual) != set(expected) or any(actual[key] != expected_projection[key] for key in expected):
            raise ValidationError("writer_input composition is not the current CompositionPlan view")
        expected_order = _canonical_plan_order(composition_plan["planned_units"])
        if composition.get("body_unit_order") is not None and list(composition["body_unit_order"]) != expected_order:
            raise ValidationError("writer_input body_unit_order is not the current CompositionPlan order")
        plan_dispositions = {
            str(row["content_unit_id"]): row["disposition"]
            for row in composition_plan.get("content_dispositions", [])
        }
        for row in selected_rows:
            content_id = str(row["content_unit_id"])
            if content_id in plan_dispositions and row.get("disposition", plan_dispositions[content_id]) != plan_dispositions[content_id]:
                raise ValidationError(f"writer_input content {content_id} is stale for its disposition")
            if "planned_unit_ids" in row:
                expected_destinations = next(
                    (item["planned_unit_ids"] for item in composition_plan["content_dispositions"] if str(item["content_unit_id"]) == content_id),
                    [],
                )
                if list(row["planned_unit_ids"]) != list(expected_destinations):
                    raise ValidationError(f"writer_input content {content_id} has stale planned destinations")
    return writer_input


def _classify_block(text: str) -> tuple[str, str, int]:
    stripped = text.strip()
    first = stripped.splitlines()[0] if stripped else ""
    heading = re.match(r"^(#{1,6})\s+(.+)$", first)
    if heading:
        return "heading", "other", len(heading.group(1))
    if first.startswith("```"):
        return "code", "other", 0
    if all(line.lstrip().startswith(">") for line in stripped.splitlines() if line.strip()):
        return "quote", "prose", 0
    lines = [line for line in stripped.splitlines() if line.strip()]
    if lines and all(LIST_LINE.match(line) for line in lines):
        return "list", "functional_list", 0
    if len(lines) >= 2 and all("|" in line for line in lines):
        return "table", "table", 0
    return "paragraph", "prose", 0


def _unmapped_ranges_for_units(text: str, units: Iterable[Mapping[str, Any]]) -> list[dict[str, int]]:
    """Compute the exact gaps left by non-document units.

    Blank lines and leading/trailing whitespace are allowed gaps.  A caller
    cannot use this field to hide prose: validation rejects any gap containing
    a non-whitespace character.
    """
    spans = sorted(
        (int(row["start"]), int(row["end"]))
        for row in units
        if row.get("unit_kind") != "document"
    )
    gaps: list[dict[str, int]] = []
    cursor = 0
    for start, end in spans:
        if start > cursor:
            gaps.append({"start": cursor, "end": start})
        cursor = max(cursor, end)
    if cursor < len(text):
        gaps.append({"start": cursor, "end": len(text)})
    return gaps


def build_artifact_map(
    artifact_path: str | Path,
    *,
    map_id: str,
    language: str,
    artifact_format: str | None = None,
) -> dict[str, Any]:
    path = Path(artifact_path).expanduser().resolve()
    if not path.is_file():
        raise ValidationError("artifact_path does not identify a current file")
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("ArtifactMap currently requires UTF-8 text or Markdown") from exc
    fmt = artifact_format or ("markdown" if path.suffix.lower() in {".md", ".markdown"} else "text")
    if fmt not in {"text", "markdown"}:
        raise ValidationError("ArtifactMap supports only text and markdown")
    artifact_fp = "sha256:" + __import__("hashlib").sha256(data).hexdigest()
    units: list[dict[str, Any]] = [
        {
            "artifact_unit_id": "artifact:document",
            "parent_unit_id": None,
            "unit_kind": "document",
            "zone": "other",
            "order": 1,
            "heading_level": 0,
            "locator": f"char:0-{len(text)}",
            "start": 0,
            "end": len(text),
            "text": text,
            "content_fingerprint": fingerprint_text(text),
        }
    ]
    heading_stack: list[tuple[int, str]] = []
    order = 2
    block_start: int | None = None
    offset = 0
    blocks: list[tuple[int, int, str]] = []
    pending: list[tuple[int, str]] = []
    pending_kind: str | None = None
    pending_start: int | None = None
    for line in text.splitlines(keepends=True):
        if line.strip():
            if block_start is None:
                block_start = offset
            line_kind = "heading" if re.match(r"^\s*#{1,6}\s+", line) else ("list" if LIST_LINE.match(line) else "paragraph")
            if pending_kind is None:
                pending_kind, pending_start = line_kind, offset
            elif line_kind != pending_kind:
                raw = text[pending_start:offset].rstrip("\r\n")
                blocks.append((pending_start, offset - (len(text[pending_start:offset]) - len(raw)), raw))
                pending_kind, pending_start = line_kind, offset
        elif block_start is not None:
            if pending_kind is not None and pending_start is not None:
                raw = text[pending_start:offset].rstrip("\r\n")
                blocks.append((pending_start, offset - (len(text[pending_start:offset]) - len(raw)), raw))
            pending_kind, pending_start = None, None
            block_start = None
        offset += len(line)
    if pending_kind is not None and pending_start is not None:
        raw = text[pending_start:len(text)].rstrip("\r\n")
        blocks.append((pending_start, len(text) - (len(text[pending_start:]) - len(raw)), raw))
    if not blocks and text:
        blocks.append((0, len(text), text))

    for index, (start, raw_end, block_text) in enumerate(blocks, start=1):
        end = start + len(block_text)
        kind, zone, heading_level = _classify_block(block_text)
        if kind == "heading":
            while heading_stack and heading_stack[-1][0] >= heading_level:
                heading_stack.pop()
            parent_id = heading_stack[-1][1] if heading_stack else "artifact:document"
            unit_id = f"artifact:heading:{index:04d}"
            heading_stack.append((heading_level, unit_id))
            lowered = block_text.casefold()
            if re.search(r"\bappendix\b|附录", lowered):
                zone = "operational_appendix"
            elif re.search(r"\bsources?\b|evidence boundary|来源|资料边界", lowered):
                zone = "source_boundary"
            elif re.search(r"\brecheck\b|复核|出发前", lowered):
                zone = "recheck"
        else:
            parent_id = heading_stack[-1][1] if heading_stack else "artifact:document"
            unit_id = f"artifact:{kind}:{index:04d}"
            parent_zone = next(
                (row["zone"] for row in reversed(units) if row["artifact_unit_id"] == parent_id),
                "other",
            )
            if parent_zone in {"operational_appendix", "source_boundary", "recheck"}:
                zone = parent_zone
        units.append(
            {
                "artifact_unit_id": unit_id,
                "parent_unit_id": parent_id,
                "unit_kind": kind,
                "zone": zone,
                "order": order,
                "heading_level": heading_level,
                "locator": f"char:{start}-{end}",
                "start": start,
                "end": end,
                "text": block_text,
                "content_fingerprint": fingerprint_text(block_text),
            }
        )
        order += 1
    artifact_map = {
        "schema_version": "2.0",
        "map_id": map_id,
        "artifact_path": str(path),
        "artifact_format": fmt,
        "artifact_fingerprint": artifact_fp,
        "language": language,
        "units": units,
        "unmapped_ranges": _unmapped_ranges_for_units(text, units),
    }
    artifact_map["map_fingerprint"] = fingerprint(artifact_map)
    require_schema("artifact-map.schema.json", artifact_map, label="ArtifactMap")
    validate_artifact_map(artifact_map)
    return artifact_map


def validate_artifact_map(value: Any) -> dict[str, Any]:
    artifact_map = require_mapping(value, "ArtifactMap")
    require_schema("artifact-map.schema.json", artifact_map, label="ArtifactMap")
    _require_exact_fingerprint(artifact_map, "map_fingerprint")
    path = Path(artifact_map["artifact_path"]).expanduser().resolve()
    if not path.is_file():
        raise ValidationError("ArtifactMap artifact is missing")
    data = path.read_bytes()
    actual_fp = "sha256:" + __import__("hashlib").sha256(data).hexdigest()
    if actual_fp != artifact_map["artifact_fingerprint"]:
        raise ValidationError("ArtifactMap is stale for the current bytes")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("ArtifactMap artifact is not valid UTF-8") from exc
    units = list(artifact_map["units"])
    unit_ids = set(_ids(units, "artifact_unit_id", "artifact unit"))
    documents = [row for row in units if row["unit_kind"] == "document"]
    if len(documents) != 1:
        raise ValidationError("ArtifactMap must contain exactly one document overview unit")
    document = documents[0]
    if document["start"] != 0 or document["end"] != len(text) or document["text"] != text:
        raise ValidationError("ArtifactMap document overview does not cover current bytes")
    if document["locator"] != f"char:0-{len(text)}":
        raise ValidationError("ArtifactMap document locator is stale")

    non_document = sorted(
        (row for row in units if row["unit_kind"] != "document"),
        key=lambda row: (row["start"], row["end"], row["artifact_unit_id"]),
    )
    last_end = 0
    for unit in units:
        start, end = unit["start"], unit["end"]
        if end <= start and unit["unit_kind"] != "document":
            raise ValidationError(f"ArtifactMap unit {unit['artifact_unit_id']} is empty")
        if end < start or end > len(text):
            raise ValidationError(f"ArtifactMap unit {unit['artifact_unit_id']} is out of bounds")
        if unit["text"] != text[start:end]:
            raise ValidationError(f"ArtifactMap unit {unit['artifact_unit_id']} does not match current text")
        if unit["content_fingerprint"] != fingerprint_text(unit["text"]):
            raise ValidationError(f"ArtifactMap unit {unit['artifact_unit_id']} fingerprint is stale")
        if unit["locator"] != f"char:{start}-{end}":
            raise ValidationError(f"ArtifactMap unit {unit['artifact_unit_id']} locator is stale")
        parent = unit["parent_unit_id"]
        if parent is not None and parent not in unit_ids:
            raise ValidationError(f"ArtifactMap unit {unit['artifact_unit_id']} has an unknown parent")
    for unit in non_document:
        if unit["start"] < last_end:
            raise ValidationError("non-document ArtifactMap units overlap")
        last_end = unit["end"]

    # Every non-whitespace character must belong to exactly one real body or
    # structural unit.  The document node is only a summary and is excluded
    # from this coverage calculation.
    expected_gaps = _unmapped_ranges_for_units(text, non_document)
    supplied_gaps = [
        {"start": int(row["start"]), "end": int(row["end"])}
        for row in artifact_map["unmapped_ranges"]
    ]
    if supplied_gaps != expected_gaps:
        raise ValidationError("ArtifactMap unmapped_ranges do not match the current unit partition")
    for gap in supplied_gaps:
        if gap["end"] <= gap["start"]:
            raise ValidationError("ArtifactMap unmapped range must be non-empty")
        if text[gap["start"]:gap["end"]].strip():
            raise ValidationError("ArtifactMap leaves non-whitespace bytes unmapped")

    # Parent links form a rooted tree/forest over the current map.  A forged
    # parent cycle otherwise passes span checks while making reader review
    # unable to establish a stable hierarchy.
    parent_of = {str(row["artifact_unit_id"]): row["parent_unit_id"] for row in units}
    for unit_id in parent_of:
        seen: set[str] = set()
        current: str | None = unit_id
        while current is not None:
            if current in seen:
                raise ValidationError("ArtifactMap parent graph contains a cycle")
            seen.add(current)
            current = parent_of.get(current)
    return artifact_map


def validate_shared_writing(
    value: Any,
    *,
    artifact_map: Mapping[str, Any],
    reader_brief: Mapping[str, Any],
) -> dict[str, Any]:
    contract = require_mapping(value, "SharedWriting")
    require_schema("shared-writing-contract.schema.json", contract, label="SharedWriting")
    _require_exact_fingerprint(contract, "contract_fingerprint")
    amap = validate_artifact_map(artifact_map)
    brief = require_mapping(reader_brief, "ReaderBrief")
    require_schema("reader-brief.schema.json", brief, label="ReaderBrief")
    _require_exact_fingerprint(brief, "brief_fingerprint")
    expected = {
        "final_owner": brief["final_owner"],
        "route_decision_fingerprint": brief["route_decision_fingerprint"],
        "reader_intent_fingerprint": brief["reader_intent_fingerprint"],
        "reader_brief_fingerprint": brief["brief_fingerprint"],
        "composition_plan_fingerprint": brief["composition_plan"]["plan_fingerprint"],
        "route_extension_fingerprint": brief["route_extension"]["extension_fingerprint"],
        "artifact_map_fingerprint": amap["map_fingerprint"],
        "artifact_fingerprint": amap["artifact_fingerprint"],
    }
    for key, expected_value in expected.items():
        if contract[key] != expected_value:
            raise ValidationError(f"SharedWriting {key} does not bind the current reader chain")
    if Path(contract["artifact_path"]).expanduser().resolve() != Path(amap["artifact_path"]):
        raise ValidationError("SharedWriting artifact_path does not match ArtifactMap")

    units = {row["artifact_unit_id"]: row for row in amap["units"]}
    plan_units = {row["planned_unit_id"]: row for row in brief["composition_plan"]["planned_units"]}
    content_units = {
        row["content_unit_id"]: row
        for row in brief["content_boundaries"]["content_units"]
    }
    bound_plans: set[str] = set()
    bound_content: set[str] = set()
    for binding in contract["unit_bindings"]:
        planned_id = binding["planned_unit_id"]
        if planned_id not in plan_units:
            raise ValidationError(f"SharedWriting references unknown planned unit {planned_id}")
        bound_plans.add(planned_id)
        for content_id in binding["content_unit_ids"]:
            if content_id not in content_units:
                raise ValidationError(f"SharedWriting references unknown content unit {content_id}")
            bound_content.add(content_id)
        if set(binding["artifact_unit_ids"]) != {
            span["artifact_unit_id"] for span in binding["artifact_spans"]
        }:
            raise ValidationError(f"SharedWriting binding {binding['binding_id']} has inconsistent unit/span ids")
        for span in binding["artifact_spans"]:
            unit = units.get(span["artifact_unit_id"])
            if unit is None:
                raise ValidationError(f"SharedWriting references unknown artifact unit {span['artifact_unit_id']}")
            if span["locator"] != unit["locator"] or span["content_fingerprint"] != unit["content_fingerprint"]:
                raise ValidationError(f"SharedWriting span for {unit['artifact_unit_id']} is stale")
    required_plans = {key for key, row in plan_units.items() if row["required"]}
    if not required_plans <= bound_plans:
        raise ValidationError(f"required planned units are unbound: {sorted(required_plans - bound_plans)}")
    required_content = {key for key, row in content_units.items() if row["required"]}
    explicit_dispositions = {
        row["item_id"]
        for row in contract["coverage_dispositions"]
        if row["item_kind"] == "content_unit" and row["disposition"] in {"omitted", "not_applicable", "blocked"}
    }
    if not required_content <= bound_content | explicit_dispositions:
        raise ValidationError(f"required content units are unbound: {sorted(required_content - bound_content - explicit_dispositions)}")
    return contract


def _audit_finding(
    *,
    code: str,
    unit_id: str,
    message: str,
    owner: str,
    boundary: str,
    index: int,
) -> dict[str, Any]:
    return {
        "finding_id": f"audit:{index:04d}",
        "code": code,
        "severity": "blocking" if code in {
            "stale_binding", "locked_structure_missing", "must_preserve_missing",
            "verbatim_missing", "citation_missing", "workflow_leak", "placeholder",
        } else "repair",
        "message": message,
        "affected_unit_ids": [unit_id],
        "repair_owner": owner,
        "preservation_boundary": boundary,
    }


def build_reader_audit(
    *,
    audit_id: str,
    artifact_map: Mapping[str, Any],
    reader_brief: Mapping[str, Any],
    shared_writing: Mapping[str, Any],
    audited_at: str | None = None,
) -> dict[str, Any]:
    amap = validate_artifact_map(artifact_map)
    brief = require_mapping(reader_brief, "ReaderBrief")
    require_schema("reader-brief.schema.json", brief, label="ReaderBrief")
    contract = validate_shared_writing(shared_writing, artifact_map=amap, reader_brief=brief)
    units = amap["units"]
    visible_units = [row for row in units if row["unit_kind"] != "document"]
    text = "\n".join(row["text"] for row in visible_units)
    plan_by_id = {row["planned_unit_id"]: row for row in brief["composition_plan"]["planned_units"]}
    unit_to_plan: dict[str, Mapping[str, Any]] = {}
    for binding in contract["unit_bindings"]:
        for unit_id in binding["artifact_unit_ids"]:
            unit_to_plan[unit_id] = plan_by_id[binding["planned_unit_id"]]
    findings: list[dict[str, Any]] = []

    def add(code: str, unit_id: str, message: str, boundary: str = "preserve current content boundaries") -> None:
        findings.append(_audit_finding(code=code, unit_id=unit_id, message=message, owner=brief["final_owner"], boundary=boundary, index=len(findings) + 1))

    for row in units:
        if row["unit_kind"] == "document":
            continue
        if PLACEHOLDER.search(row["text"]):
            add("placeholder", row["artifact_unit_id"], "draft placeholder remains in the current artifact")
        if WORKFLOW_LEAK.search(row["text"]):
            add("workflow_leak", row["artifact_unit_id"], "internal workflow or paragraph-planning language leaked into reader-facing copy")
        plan = unit_to_plan.get(row["artifact_unit_id"])
        if row["unit_kind"] in {"paragraph", "list", "table", "quote", "scene", "code"} and plan is None:
            add("unbound_body_unit", row["artifact_unit_id"], "an actual body unit is not covered by a binding or explicit disposition")
        if row["unit_kind"] == "list" and plan and plan["presentation_mode"] == "prose":
            add("disallowed_list_zone", row["artifact_unit_id"], "a prose-required planned unit is realized as a list or labeled card block")

    headings = {re.sub(r"^#{1,6}\s+", "", row["text"]).strip() for row in units if row["unit_kind"] == "heading"}
    for outline in brief["reader_intent"]["structure"]["requested_outline"]:
        if outline["required"] and outline["title_locked"] and outline["label"] not in headings:
            add("locked_structure_missing", "artifact:document", f"locked heading is missing: {outline['label']}")
    for token in brief["content_boundaries"]["must_preserve_tokens"]:
        if token["token"] not in text:
            add("must_preserve_missing", "artifact:document", f"required exact token is missing: {token['token']}")
    for obligation in brief["content_boundaries"]["verbatim_obligations"]:
        if obligation["text"] not in text:
            add("verbatim_missing", "artifact:document", f"required verbatim text is missing: {obligation['verbatim_id']}")
    content_to_artifacts: dict[str, set[str]] = {}
    for binding in contract["unit_bindings"]:
        for content_id in binding["content_unit_ids"]:
            content_to_artifacts.setdefault(str(content_id), set()).update(
                str(unit_id) for unit_id in binding["artifact_unit_ids"]
            )
    units_by_id = {row["artifact_unit_id"]: row for row in visible_units}
    for citation in brief["content_boundaries"]["citation_duties"]:
        marker = citation["marker"]
        if marker not in text:
            add("citation_missing", "artifact:document", f"required citation marker is missing: {marker}")
            continue
        target_ids = {
            unit_id for content_id in citation["content_unit_ids"]
            for unit_id in content_to_artifacts.get(str(content_id), set())
        }
        target_units = [units_by_id[unit_id] for unit_id in target_ids if unit_id in units_by_id]
        placement = citation["placement"]
        placement_ok = False
        if placement in {"footnote", "endnote"}:
            # Markdown/text artifacts have no universal footnote AST.  The
            # marker still has to occur in a real mapped unit; a marker that
            # only appears in a discarded source boundary cannot pass.
            placement_ok = any(marker in row["text"] for row in target_units) or marker in text
        elif placement in {"same_unit", "same_paragraph", "same_sentence"}:
            for row in target_units:
                if marker not in row["text"]:
                    continue
                if placement != "same_sentence":
                    placement_ok = True
                    break
                marker_pos = row["text"].find(marker)
                for match in re.finditer(r"[^.!?。！？]*[.!?。！？]", row["text"]):
                    if match.start() <= marker_pos < match.end():
                        placement_ok = True
                        break
                if placement_ok:
                    break
        if not placement_ok:
            add("citation_placement", "artifact:document", f"citation marker is outside its required {placement}: {citation['citation_id']}")

    prose_paragraphs = [row for row in visible_units if row["unit_kind"] == "paragraph" and row["zone"] in {"prose", "narrative"}]
    short = [
        row for row in prose_paragraphs
        if len(row["text"].strip()) < 90 and len(SENTENCE_MARK.findall(row["text"].strip())) <= 1
    ]
    consecutive_short = 0
    for row in prose_paragraphs:
        if row in short:
            consecutive_short += 1
            if consecutive_short >= 3:
                add("microparagraph_sequence", row["artifact_unit_id"], "three or more short prose blocks create pointillist, card-like reading")
                break
        else:
            consecutive_short = 0
    fragmentation_applicable = brief["final_owner"] != "fiction-writing" or brief.get("route_extension", {}).get("profile") not in {"reader_native", "story"}
    if fragmentation_applicable and prose_paragraphs and len(short) / len(prose_paragraphs) > 0.65 and len(prose_paragraphs) >= 4:
        add("fragmentation_ratio", "artifact:document", "the prose-required body is dominated by one-sentence microparagraphs")

    list_units = [row for row in units if row["unit_kind"] == "list"]
    disallowed_lists = [
        row for row in list_units
        if unit_to_plan.get(row["artifact_unit_id"], {}).get("presentation_mode") == "prose"
    ]
    metrics = {
        "heading_count": sum(row["unit_kind"] == "heading" for row in visible_units),
        "paragraph_count": sum(row["unit_kind"] == "paragraph" for row in visible_units),
        "prose_paragraph_count": len(prose_paragraphs),
        "short_prose_paragraph_count": len(short),
        "list_item_count": sum(len(row["text"].splitlines()) for row in list_units),
        "disallowed_list_item_count": sum(len(row["text"].splitlines()) for row in disallowed_lists),
        "placeholder_count": sum(f["code"] == "placeholder" for f in findings),
        "workflow_leak_count": sum(f["code"] == "workflow_leak" for f in findings),
        "body_character_count": sum(len(row["text"].strip()) for row in prose_paragraphs),
    }
    minimum = brief["reader_intent"]["extent"]["minimum"]
    maximum = brief["reader_intent"]["extent"]["maximum"]
    extent_unit = brief["reader_intent"]["extent"]["unit"]
    body_text = "\n".join(
        row["text"] for row in visible_units
        if row["unit_kind"] in _BODY_UNIT_KINDS and row["zone"] not in {"source_boundary"}
    )
    body_count = _measure_extent(
        body_text,
        extent_unit,
        brief["reader_intent"]["extent"].get("extent_metric_id"),
    )
    metrics["extent_unit"] = extent_unit
    metrics["extent_count"] = body_count
    if body_count < minimum:
        add("extent_below_minimum", "artifact:document", f"actual body extent {body_count} {extent_unit} is below ReaderIntent minimum {minimum}")
    if body_count > maximum:
        add("extent_above_maximum", "artifact:document", f"actual body extent {body_count} {extent_unit} exceeds ReaderIntent maximum {maximum}")
    if _language_mismatch(body_text, brief["reader_intent"]["language"]):
        add("wrong_language", "artifact:document", "the current artifact is predominantly in a different language from ReaderIntent")
    dimension_codes = {
        "current_bytes": {"stale_binding"},
        "structure_lock": {"locked_structure_missing"},
        "exact_preservation": {"must_preserve_missing", "verbatim_missing"},
        "citation_placement": {"citation_missing", "citation_placement"},
        "list_zones": {"disallowed_list_zone"},
        "fragmentation": {"microparagraph_sequence", "fragmentation_ratio"},
        "language_fit": {"wrong_language"},
        "binding_coverage": {"stale_binding"},
    }
    dimensions = {
        name: ("repair" if any(f["code"] in codes for f in findings) else "passed")
        for name, codes in dimension_codes.items()
    }
    audit = {
        "schema_version": "2.0",
        "audit_id": audit_id,
        "final_owner": brief["final_owner"],
        "route_decision_fingerprint": brief["route_decision_fingerprint"],
        "reader_intent_fingerprint": brief["reader_intent_fingerprint"],
        "reader_brief_fingerprint": brief["brief_fingerprint"],
        "composition_plan_fingerprint": brief["composition_plan"]["plan_fingerprint"],
        "artifact_map_fingerprint": amap["map_fingerprint"],
        "shared_writing_contract_fingerprint": contract["contract_fingerprint"],
        "artifact_fingerprint": amap["artifact_fingerprint"],
        "visible_unit_ids": [row["artifact_unit_id"] for row in units],
        "structure_metrics": metrics,
        "findings": findings,
        "quality_dimensions": dimensions,
        "status": "repair" if findings else "passed",
        "audited_at": audited_at or utc_now(),
    }
    audit["audit_fingerprint"] = fingerprint(audit)
    require_schema("reader-audit.schema.json", audit, label="ReaderAudit")
    return audit


def validate_reader_audit_current(
    audit: Mapping[str, Any],
    *,
    artifact_map: Mapping[str, Any],
    reader_brief: Mapping[str, Any],
    shared_writing: Mapping[str, Any],
    rules_version: str = "reader-audit-rules.v2",
) -> dict[str, Any]:
    """Recompute every substantive audit result from current bytes and inputs."""
    candidate = require_mapping(audit, "ReaderAudit")
    require_schema("reader-audit.schema.json", candidate, label="ReaderAudit")
    _require_exact_fingerprint(candidate, "audit_fingerprint")
    current = build_reader_audit(
        audit_id=candidate["audit_id"], artifact_map=artifact_map,
        reader_brief=reader_brief, shared_writing=shared_writing,
        audited_at=candidate.get("audited_at"),
    )
    ignored = {"audit_id", "audited_at", "audit_fingerprint"}
    left = {key: value for key, value in candidate.items() if key not in ignored}
    right = {key: value for key, value in current.items() if key not in ignored}
    if left != right:
        raise ValidationError(f"ReaderAudit is stale or caller-authored for current {rules_version}")
    return candidate


def _verify_span_evidence(evidence: Mapping[str, Any], units: Mapping[str, Mapping[str, Any]]) -> None:
    unit = units.get(evidence["artifact_unit_id"])
    if unit is None:
        raise ValidationError(f"review evidence references unknown unit {evidence['artifact_unit_id']}")
    if evidence["locator"] != unit["locator"]:
        raise ValidationError("review evidence locator is stale")
    if evidence["excerpt"] not in unit["text"]:
        raise ValidationError("review evidence excerpt is absent from the current unit")
    if evidence["excerpt_fingerprint"] != fingerprint_text(evidence["excerpt"]):
        raise ValidationError("review evidence excerpt fingerprint is stale")


def validate_route_artifact_review(
    value: Any,
    *,
    owner: str,
    route_composition: Mapping[str, Any],
    artifact_map: Mapping[str, Any],
    required_dimensions: Iterable[str] = (),
    review_obligations: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    review = require_mapping(value, "route artifact review")
    require_schema("route-artifact-review.schema.json", review, label="route artifact review")
    _require_exact_fingerprint(review, "review_fingerprint")
    amap = validate_artifact_map(artifact_map)
    route = validate_route_composition(
        route_composition,
        owner=owner,
        reader_intent_fingerprint=route_composition["reader_intent_fingerprint"],
        composition_plan_fingerprint=route_composition["composition_plan_fingerprint"],
    )
    if review["final_owner"] != owner or review["route_extension_fingerprint"] != route["extension_fingerprint"]:
        raise ValidationError("route review belongs to a sibling or stale route composition")
    if review["artifact_map_fingerprint"] != amap["map_fingerprint"] or review["artifact_fingerprint"] != amap["artifact_fingerprint"]:
        raise ValidationError("route review does not bind the current ArtifactMap")
    if review_obligations is not None:
        from review_obligations import validate_review_obligation_manifest
        manifest = validate_review_obligation_manifest(review_obligations, owner=owner)
        manifest_fp = manifest["manifest_fingerprint"]
        if review.get("review_obligation_manifest_fingerprint") != manifest_fp:
            raise ValidationError("route review does not bind the current review obligation manifest")
        required_dimensions = tuple(
            row["dimension_id"] for row in manifest["obligations"]
            if row.get("applicability", "required") == "required"
        )
    units = {row["artifact_unit_id"]: row for row in amap["units"]}
    present_dimensions = {row["dimension_id"] for row in review["dimensions"]}
    missing = set(required_dimensions) - present_dimensions
    if missing:
        raise ValidationError(f"route review omits required dimensions: {sorted(missing)}")
    for row in review["dimensions"]:
        for evidence in row["evidence"]:
            _verify_span_evidence(evidence, units)
    for finding in review["findings"]:
        _verify_span_evidence(finding["evidence"], units)
    derived = "repair" if review["findings"] or any(row["status"] != "passed" for row in review["dimensions"]) else "passed"
    if review["status"] != derived:
        raise ValidationError("route review status is not derived from current dimensions and findings")
    if bool(review["required_repairs"]) != (derived != "passed"):
        raise ValidationError("route review required_repairs do not match its status")
    return review


def validate_reader_judgment(
    value: Any,
    *,
    artifact_map: Mapping[str, Any],
    reader_brief: Mapping[str, Any],
    shared_writing: Mapping[str, Any],
    deterministic_audit: Mapping[str, Any],
    route_review: Mapping[str, Any],
    execution_record: Mapping[str, Any] | None = None,
    review_obligations: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    judgment = require_mapping(value, "ReaderJudgment")
    require_schema("reader-judgment.schema.json", judgment, label="ReaderJudgment")
    _require_exact_fingerprint(judgment, "judgment_fingerprint")
    amap = validate_artifact_map(artifact_map)
    brief = require_mapping(reader_brief, "ReaderBrief")
    contract = validate_shared_writing(shared_writing, artifact_map=amap, reader_brief=brief)
    audit = validate_reader_audit_current(
        deterministic_audit, artifact_map=amap, reader_brief=brief, shared_writing=contract
    )
    review = require_mapping(route_review, "route artifact review")
    require_schema("route-artifact-review.schema.json", review, label="route artifact review")
    _require_exact_fingerprint(review, "review_fingerprint")
    if judgment["producer_id"] == judgment["judge_id"]:
        raise ValidationError("routine ReaderJudgment requires an independent judge context")
    if review_obligations is not None:
        from review_obligations import validate_review_obligation_manifest
        manifest = validate_review_obligation_manifest(review_obligations)
        if judgment.get("review_obligation_manifest_fingerprint") != manifest["manifest_fingerprint"]:
            raise ValidationError("ReaderJudgment does not bind the current review obligation manifest")
    expected = {
        "final_owner": brief["final_owner"],
        "reader_intent_fingerprint": brief["reader_intent_fingerprint"],
        "reader_brief_fingerprint": brief["brief_fingerprint"],
        "composition_plan_fingerprint": brief["composition_plan"]["plan_fingerprint"],
        "artifact_map_fingerprint": amap["map_fingerprint"],
        "shared_writing_contract_fingerprint": contract["contract_fingerprint"],
        "deterministic_audit_fingerprint": audit["audit_fingerprint"],
        "route_audit_fingerprint": review["review_fingerprint"],
        "artifact_fingerprint": amap["artifact_fingerprint"],
    }
    for key, expected_value in expected.items():
        if judgment[key] != expected_value:
            raise ValidationError(f"ReaderJudgment {key} is stale or foreign")
    units = {row["artifact_unit_id"]: row for row in amap["units"]}
    for row in judgment["reverse_outline"]:
        _verify_span_evidence(row["evidence"], units)
    for row in (*judgment["defects"], *judgment["strengths"]):
        _verify_span_evidence(row["evidence"], units)
    actual_body_ids = {row["artifact_unit_id"] for row in amap["units"] if row["unit_kind"] in {"paragraph", "list", "table", "quote", "scene"}}
    outlined_ids = {row["artifact_unit_id"] for row in judgment["reverse_outline"]}
    if actual_body_ids - outlined_ids:
        raise ValidationError(f"ReaderJudgment reverse outline omits actual units: {sorted(actual_body_ids - outlined_ids)}")
    repair_ids = {ref for row in judgment["required_repairs"] for ref in row["defect_ids"]}
    unrequested = {row["observation_id"] for row in judgment["defects"]} - repair_ids
    if unrequested:
        raise ValidationError(f"ReaderJudgment defects lack repair requests: {sorted(unrequested)}")
    execution_ok = False
    if execution_record is not None:
        from reader_execution import validate_execution_record
        execution = validate_execution_record(execution_record, lambda record: record.get("independence_status") == "verified")
        if judgment.get("execution_record_fingerprint") != execution["record_fingerprint"]:
            raise ValidationError("ReaderJudgment execution record is stale or foreign")
        execution_ok = execution["role"] == "judge" and execution["terminal_status"] == "completed" and execution["independence_status"] == "verified"
    elif judgment["status"] == "passed":
        raise ValidationError("ReaderJudgment passed without a real judge execution record")
    score_pass = min(judgment["scores"].values()) >= 4
    blocking = any(row["severity"] == "blocking" for row in judgment["defects"])
    derived = (
        "passed"
        if audit["status"] == review["status"] == "passed"
        and score_pass
        and not blocking
        and not judgment["required_repairs"]
        and execution_ok
        else "repair"
    )
    if judgment["status"] != derived:
        raise ValidationError("ReaderJudgment status is not derived from the current evidence")
    if judgment["status"] == "passed" and any(row["orphaned"] or row["overloaded"] for row in judgment["reverse_outline"]):
        raise ValidationError("ReaderJudgment cannot pass with orphaned or overloaded units")
    return judgment


DEFAULT_FORBIDDEN_SHORTCUTS = (
    "Do not repair coherence by adding transition words alone.",
    "Do not turn prose into more bullet cards.",
    "Do not delete limitations or citation duties.",
    "Do not copy safe meanings as an allowed-wording script.",
    "Do not explain paragraph jobs in reader-facing meta-language.",
)


def build_repair_request(
    *,
    repair_id: str,
    attempt_number: int,
    reader_brief: Mapping[str, Any],
    artifact_map: Mapping[str, Any],
    shared_writing: Mapping[str, Any],
    deterministic_audit: Mapping[str, Any],
    route_review: Mapping[str, Any],
    judgment: Mapping[str, Any],
    defect_lineage: str,
) -> dict[str, Any]:
    brief = require_mapping(reader_brief, "ReaderBrief")
    amap = validate_artifact_map(artifact_map)
    contract = validate_shared_writing(shared_writing, artifact_map=amap, reader_brief=brief)
    validated = validate_reader_judgment(
        judgment,
        artifact_map=amap,
        reader_brief=brief,
        shared_writing=contract,
        deterministic_audit=deterministic_audit,
        route_review=route_review,
    )
    if validated["status"] == "passed":
        raise ValidationError("a passing ReaderJudgment cannot produce a RepairRequest")
    defect_ids = [row["observation_id"] for row in validated["defects"]]
    target_units = list(dict.fromkeys(
        unit_id
        for row in validated["required_repairs"]
        for unit_id in row["target_unit_ids"]
    ))
    required_changes = [row["required_change"] for row in validated["required_repairs"]]
    preserve_ids = [
        row["content_unit_id"]
        for row in brief["content_boundaries"]["content_units"]
        if row["required"]
    ]
    request = {
        "schema_version": "2.0",
        "repair_id": repair_id,
        "attempt_number": attempt_number,
        "final_owner": brief["final_owner"],
        "source_artifact_fingerprint": amap["artifact_fingerprint"],
        "reader_intent_fingerprint": brief["reader_intent_fingerprint"],
        "reader_brief_fingerprint": brief["brief_fingerprint"],
        "composition_plan_fingerprint": brief["composition_plan"]["plan_fingerprint"],
        "artifact_map_fingerprint": amap["map_fingerprint"],
        "shared_writing_contract_fingerprint": contract["contract_fingerprint"],
        "audit_fingerprint": deterministic_audit["audit_fingerprint"],
        "route_audit_fingerprint": route_review["review_fingerprint"],
        "judgment_fingerprint": validated["judgment_fingerprint"],
        "defect_lineage": defect_lineage,
        "defect_set_fingerprint": fingerprint(sorted(defect_ids)),
        "target_unit_ids": target_units,
        "required_changes": required_changes,
        "preserve_content_unit_ids": preserve_ids,
        "must_preserve_tokens": [row["token"] for row in brief["content_boundaries"]["must_preserve_tokens"]],
        "forbidden_shortcuts": list(DEFAULT_FORBIDDEN_SHORTCUTS),
    }
    request["request_fingerprint"] = fingerprint(request)
    require_schema("reader-repair-request.schema.json", request, label="ReaderRepairRequest")
    return request


def record_repair_result(
    *,
    request: Mapping[str, Any],
    output_artifact_map: Mapping[str, Any],
    changed_unit_ids: Iterable[str],
    preserved_content_unit_ids: Iterable[str],
    preservation_violations: Iterable[str],
    remaining_defect_ids: Iterable[str],
) -> dict[str, Any]:
    repair = require_mapping(request, "ReaderRepairRequest")
    require_schema("reader-repair-request.schema.json", repair, label="ReaderRepairRequest")
    _require_exact_fingerprint(repair, "request_fingerprint")
    amap = validate_artifact_map(output_artifact_map)
    remaining_fp = fingerprint(sorted(remaining_defect_ids))
    changed = list(changed_unit_ids)
    violations = list(preservation_violations)
    same_bytes = repair["source_artifact_fingerprint"] == amap["artifact_fingerprint"]
    same_defects = remaining_fp == repair["defect_set_fingerprint"]
    if violations:
        progress = "blocked"
    elif same_bytes or same_defects:
        progress = "no_progress"
    else:
        progress = "progressed"
    result = {
        "schema_version": "2.0",
        "repair_id": repair["repair_id"],
        "request_fingerprint": repair["request_fingerprint"],
        "defect_lineage": repair["defect_lineage"],
        "input_artifact_fingerprint": repair["source_artifact_fingerprint"],
        "output_artifact_fingerprint": amap["artifact_fingerprint"],
        "changed_unit_ids": changed,
        "preservation_check": {
            "status": "failed" if violations else "passed",
            "preserved_content_unit_ids": list(preserved_content_unit_ids),
            "violations": violations,
        },
        "remaining_defect_set_fingerprint": remaining_fp,
        "progress_status": progress,
        "rerun_required": [
            "artifact_map", "shared_writing", "deterministic_audit",
            "route_audit", "reader_judgment",
        ],
    }
    result["result_fingerprint"] = fingerprint(result)
    require_schema("reader-repair-result.schema.json", result, label="ReaderRepairResult")
    return result


def validate_revision_provenance(value: Any, *, target_artifact_fingerprint: str) -> dict[str, Any]:
    provenance = require_mapping(value, "revision provenance")
    require_schema("revision-provenance.schema.json", provenance, label="revision provenance")
    _require_exact_fingerprint(provenance, "provenance_fingerprint")
    if provenance["target_artifact_fingerprint"] != target_artifact_fingerprint:
        raise ValidationError("revision provenance is stale for the current artifact")
    source_ids = _ids(provenance["unit_treatments"], "source_unit_id", "source unit treatment")
    if provenance["artifact_mode"] == "revise_existing" and not source_ids:
        raise ValidationError("revise_existing requires source-unit treatments")
    return provenance


__all__ = [
    "build_artifact_map",
    "build_reader_audit",
    "build_reader_brief",
    "build_writer_input",
    "build_repair_request",
    "record_repair_result",
    "validate_artifact_map",
    "validate_composition_plan",
    "validate_reader_intent",
    "validate_writer_input",
    "validate_reader_audit_current",
    "validate_reader_judgment",
    "validate_revision_provenance",
    "validate_route_artifact_review",
    "validate_route_composition",
    "validate_shared_writing",
    "validate_writing_request",
]
