"""Writer projection: current reader-chain responsibilities."""
from __future__ import annotations

from _common import ValidationError, unique_ids, fingerprint, fingerprint_without, require_mapping
from reader_plan_core import _canonical_plan_order, validate_reader_intent
from reader_rules import VISIBLE_CONTENT_DISPOSITIONS, WRITER_INTERNAL
from typing import Any, Iterable, Mapping


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
        voice_payload = route.get("voice_contract")
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

    for row in composition_units:
        refs = unit_by_id[row["planned_unit_id"]].get("world_refs")
        if refs is not None:
            row["world_refs"] = list(refs)

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
    # membership checks below.  `unique_ids` returns a tuple for stable ordering,
    # but comparing that tuple with the ReaderBrief boundary set raises a
    # runtime TypeError on the native handoff path.
    selected_ids = set(unique_ids(selected_rows, "content_unit_id", "writer content")) if selected_rows else set()
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
    unit_ids = unique_ids(units, "planned_unit_id", "writer unit") if units else ()
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
        for identity, row in expected.items():
            if "world_refs" in row:
                expected_projection[identity]["world_refs"] = list(row["world_refs"])
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
