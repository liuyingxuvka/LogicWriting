"""Read fiction unit identity/state only from the canonical composition plan.

Legacy-shaped views below are ephemeral inputs to existing domain checks, never
an authored second tree. A surface cannot override the plan through stale fields.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any


class PlanContext:
    def __init__(self, request: dict[str, Any]):
        self.request = request
        self.plan = request["composition_plan"]
        self.units = {row["planned_unit_id"]: row for row in self.plan["planned_units"]}
        route = request.get("route_composition", {})
        self.fiction = {row["unit_id"]: row for row in route.get("unit_plans", [])}

    def ordered(self, kind: str):
        return sorted((row for row in self.units.values() if row.get("unit_kind") == kind), key=lambda row: row.get("order",0))

    def unit_view(self, identifier: str) -> dict[str, Any]:
        unit = self.units.get(identifier, {})
        fiction = self.fiction.get(identifier, {})
        siblings = sorted((row for row in self.units.values() if row.get("parent_unit_id") == unit.get("parent_unit_id")), key=lambda row: row.get("order",0))
        return {"id": identifier, "kind": unit.get("unit_kind", ""), "parent_id": unit.get("parent_unit_id") or "not_applicable",
                "order": unit.get("order", 0), "title": unit.get("title", ""), "summary": unit.get("reader_job", ""),
                "contribution": fiction.get("contribution", unit.get("reader_job", "")),
                "entry_state": fiction.get("entry_state", ""), "exit_state": fiction.get("exit_state", ""),
                "reader_state_before": str(fiction.get("reader_state_before", unit.get("incoming_reader_state", ""))).splitlines(),
                "reader_state_after": str(fiction.get("reader_state_after", unit.get("outgoing_reader_state", ""))).splitlines(),
                "unresolved_tension_in": fiction.get("open_questions_in", []), "unresolved_tension_out": fiction.get("open_questions_out", []),
                "downstream_use": unit.get("downstream_unit_ids", []), "depends_on": [], "evidence_refs": [],
                "plan_terminal": not unit.get("downstream_unit_ids") and bool(siblings) and siblings[-1].get("planned_unit_id") == identifier}

    def hierarchy_view(self):
        return {plural: [self.unit_view(row["planned_unit_id"]) for row in self.ordered(kind)]
                for plural, kind in (("books", "book"), ("volumes", "volume"), ("chapters", "chapter"), ("scenes", "scene"))}


def load_context(payload: Any, source_path: str, reporter) -> PlanContext | None:
    if not isinstance(payload, dict):
        reporter.error("composition_plan_missing", "$", "Unit surfaces require a canonical composition plan.")
        return None
    root = payload.get("novel_ledger", payload)
    ref = root.get("composition_plan") if isinstance(root, dict) else None
    if isinstance(ref, dict):
        request = ref if "composition_plan" in ref else {"composition_plan": ref, "route_composition": payload.get("route_composition", {})}
    else:
        if not isinstance(ref, str) or not ref:
            reporter.error("composition_plan_missing", "composition_plan", "The surface must name its canonical brief request.")
            return None
        path = Path(ref)
        if not path.is_absolute():
            path = Path(source_path).resolve().parent / path
        try:
            request = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            reporter.error("composition_plan_missing", "composition_plan", str(exc))
            return None
    plan = request.get("composition_plan") if isinstance(request, dict) else None
    units = plan.get("planned_units") if isinstance(plan, dict) else None
    if not isinstance(units, list) or not units or any(not isinstance(row, dict) or not isinstance(row.get("planned_unit_id"), str) for row in units):
        reporter.error("composition_plan_invalid", "composition_plan", "Expected canonical planned_units in the brief request.")
        return None
    if len({row["planned_unit_id"] for row in units}) != len(units):
        reporter.error("composition_plan_invalid", "composition_plan", "Planned unit ids must be unique.")
        return None
    context = PlanContext(request)
    for row in units:
        for ref in [row.get("parent_unit_id"), *row.get("downstream_unit_ids", [])]:
            if ref is not None and ref not in context.units:
                reporter.error(f"unit_not_in_plan:composition_plan:{ref}", "composition_plan", "Unit hierarchy/downstream references must resolve in the plan.")
    return context


def member(context, identifier, surface, path, reporter):
    if context is not None and identifier not in context.units:
        reporter.error(f"unit_not_in_plan:{surface}:{identifier}", path, "The unit is not in the current composition plan.")
        return False
    return context is not None


def project_surface(payload, source_path, surface, reporter):
    context = load_context(payload, source_path, reporter)
    result = deepcopy(payload)
    if not isinstance(result, dict) or context is None:
        return result, context
    root = result.get("novel_ledger", result)
    for field in ("validation", "closure"):
        if field in root:
            reporter.error("retired_closure_field", field, "Checks and closure are computed from current source surfaces.")
    if "hierarchy" in root:
        reporter.error("retired_unit_field", "hierarchy", "Unit hierarchy is read only from the composition plan.")
    if surface == "novel_ledger":
        root["hierarchy"] = context.hierarchy_view()
    groups = {"story_units": "novel_ledger", "chapter_interfaces": "chapter_interfaces",
              "prose_blueprints": "prose_blueprints", "reverse_outlines": "reverse_outlines",
              "scenes": surface, "structure": surface}
    for group, label in groups.items():
        rows = root.get(group, [])
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            identifier = row.get("planned_unit_id")
            if not member(context, identifier, label, f"{group}[{index}].planned_unit_id", reporter):
                continue
            view = context.unit_view(identifier)
            if group == "story_units":
                retired = {"id", "kind", "parent_id", "contribution", "downstream_use"}
            elif group == "chapter_interfaces":
                retired = {"chapter_id", "previous_chapter_id", "next_chapter_id", "reader_state_before", "reader_state_after", "unresolved_tension_in", "unresolved_tension_out"}
            elif group in {"prose_blueprints", "reverse_outlines"}:
                retired = {"chapter_id", "scene_order"} if group == "prose_blueprints" else {"chapter_id"}
            else:
                retired = {"id", "kind", "parent_structure_id", "entry_state", "exit_state", "order", "reader_state_before", "reader_state_after", "downstream_unit_ids", "scene_contract", "child_scene_ids", "scene_links"}
            for field in retired & row.keys():
                reporter.error("retired_unit_field", f"{group}[{index}].{field}", "Read this unit field from the composition plan.")
            if group == "story_units":
                for field in ("id", "kind", "parent_id", "contribution", "downstream_use", "plan_terminal"):
                    row[field] = view[field]
            elif group in {"chapter_interfaces", "prose_blueprints", "reverse_outlines"}:
                row["chapter_id"] = identifier
                if group == "prose_blueprints":
                    row["scene_order"] = [unit["planned_unit_id"] for unit in sorted(context.units.values(), key=lambda unit: unit["order"])
                                          if unit.get("parent_unit_id") == identifier and unit.get("unit_kind") == "scene"]
                if group == "chapter_interfaces":
                    siblings = context.ordered("chapter")
                    ids = [unit["planned_unit_id"] for unit in siblings]
                    position = ids.index(identifier) if identifier in ids else -1
                    row["previous_chapter_id"] = ids[position - 1] if position > 0 else "book-open"
                    row["next_chapter_id"] = ids[position + 1] if 0 <= position < len(ids) - 1 else "book-close"
                    for field in ("reader_state_before", "reader_state_after", "unresolved_tension_in", "unresolved_tension_out"):
                        row[field] = view[field]
            else:
                for field in ("id", "kind", "entry_state", "exit_state"):
                    row[field] = view[field]
                if group == "scenes":
                    row["scene_contract"] = context.fiction.get(identifier, {}).get("contribution", context.units[identifier].get("reader_job", ""))
                    row["parent_structure_id"] = context.units[identifier].get("parent_unit_id")
                else:
                    children = [unit["planned_unit_id"] for unit in context.units.values() if unit.get("parent_unit_id") == identifier]
                    row["child_scene_ids"] = children
                    row["scene_links"] = children
    return result, context
