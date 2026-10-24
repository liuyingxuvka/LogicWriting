"""Reader plan core: current reader-chain responsibilities."""
from __future__ import annotations

from world_refs import validate_world_refs
from route_inputs import route_extension_fingerprint

from _common import ValidationError, _ids, _require_exact_fingerprint, fingerprint_without, require_mapping, require_schema
from reader_rules import FINAL_OWNERS, HIDDEN_CONTENT_DISPOSITIONS, ROUTE_SCHEMA, VISIBLE_CONTENT_DISPOSITIONS
from typing import Any, Iterable, Mapping


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


def open_material_choices(intent: Mapping[str, Any]) -> list[dict[str, str]]:
    """Project the declared material questions without choosing an answer."""
    choices = intent.get("unresolved_choices", [])
    if not isinstance(choices, list):
        return []
    return [
        {"choice_id": row["choice_id"], "question": row["question"]}
        for row in choices
        if isinstance(row, Mapping) and row.get("material") is True
        and isinstance(row.get("choice_id"), str) and isinstance(row.get("question"), str)
    ]


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
        missing = sorted(required_content - set(disposition_by_id))
        if missing:
            raise ValidationError("; ".join(f"content unit {identity} is in no planned unit; add a content_dispositions row (omitted, deferred, appendix, merged or blocked)" for identity in missing))
        raise ValidationError(f"CompositionPlan content dispositions name unknown content units: {sorted(set(disposition_by_id) - required_content)}")
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
        raise ValidationError(f"CompositionPlan needs explicit limitation_dispositions rows for {sorted(known_limitations)}")
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
            raise ValidationError(f"limitation dispositions must cover current limitations; missing {sorted(known_limitations - seen_limitations)}")
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
    if composition.get("extension_fingerprint") != route_extension_fingerprint(composition):
        raise ValidationError("route composition extension_fingerprint is stale for its current inputs")
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
    if composition_plan is not None and owner in {"fiction-writing", "travel-guide"}:
        validate_world_refs(composition_plan, composition)
    return composition
