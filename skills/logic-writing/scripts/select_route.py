"""Select exactly one Logic Writing final owner from the terminal deliverable."""

from __future__ import annotations

from _common import (
    ValidationError,
    cli_validate,
    fingerprint,
    require_datetime,
    require_identifier,
    require_mapping,
    require_schema,
    require_string,
    require_string_list,
    validation_result,
)


INVESTIGATION_DELIVERABLES = {
    "research_report",
    "briefing",
    "evidence_package",
    "decision_note",
    "investigated_answer",
    "memo",
    "evidence_audit",
    "policy_analysis",
    "market_analysis",
    "case_investigation",
}
ACADEMIC_DELIVERABLES = {
    "paper",
    "thesis",
    "thesis_chapter",
    "dissertation",
    "dissertation_section",
    "academic_chapter",
    "literature_review",
    "formal_literature_review",
    "research_proposal",
    "proposal",
    "academic_revision",
}
FICTION_DELIVERABLES = {
    "short_story",
    "fiction_chapter",
    "novel",
    "novella",
    "fiction_outline",
    "story_plan",
    "series_bible",
    "story_audit",
    "fiction_revision",
}
TRAVEL_DELIVERABLES = {
    "itinerary",
    "destination_guide",
    "travel_guide",
    "lodging_strategy",
    "route_plan",
    "traveler_fit_recommendation",
    "travel_revision",
}
TRIVIAL_CLASSES = {
    "quick_lookup",
    "quick_fact",
    "grammar_only",
    "formatting_only",
    "casual_copy",
    "casual_summary",
}
KNOWN_DELIVERABLES = (
    INVESTIGATION_DELIVERABLES
    | ACADEMIC_DELIVERABLES
    | FICTION_DELIVERABLES
    | TRAVEL_DELIVERABLES
    | TRIVIAL_CLASSES
    | {"unresolved"}
)


def select_route(request):
    request = require_mapping(request, "request")
    request_id = require_identifier(request, "request_id", min_length=3, max_length=128)
    decision_id = require_identifier(request, "decision_id", min_length=3, max_length=128)
    decided_at = require_datetime(request, "decided_at")
    deliverable_input = require_mapping(request.get("terminal_deliverable"), "terminal_deliverable")
    requested_kind = require_string(deliverable_input, "kind")
    deliverable_kind = requested_kind if requested_kind in KNOWN_DELIVERABLES else "unresolved"
    acceptance_criteria = require_string_list(
        deliverable_input.get("acceptance_criteria"),
        "acceptance_criteria",
    )
    deliverable = {
        "kind": deliverable_kind,
        "description": require_string(deliverable_input, "description"),
        "acceptance_criteria": acceptance_criteria,
    }
    deliverable["fingerprint"] = fingerprint(deliverable)
    scope_class = request.get("scope_class", "substantive")
    if not isinstance(scope_class, str) or not scope_class.strip():
        raise ValidationError("scope_class must be a non-empty string")
    research_required = request.get("substantial_research_required", False)
    if not isinstance(research_required, bool):
        raise ValidationError("substantial_research_required must be boolean")
    child_routes: list[str] = []

    if scope_class in TRIVIAL_CLASSES or requested_kind in TRIVIAL_CLASSES:
        owner = None
        status = "skipped"
        reason = f"scope_class={scope_class} does not activate Logic Writing"
    elif deliverable_kind in INVESTIGATION_DELIVERABLES:
        owner = "investigation"
        status = "current"
        reason = "the terminal artifact is an investigation product"
    elif deliverable_kind in ACADEMIC_DELIVERABLES:
        owner = "academic-writing"
        status = "current"
        reason = "the terminal artifact is academic"
        if research_required:
            child_routes.append("investigation")
    elif deliverable_kind in FICTION_DELIVERABLES:
        owner = "fiction-writing"
        status = "current"
        reason = "the terminal artifact is fiction"
        if research_required:
            child_routes.append("investigation")
    elif deliverable_kind in TRAVEL_DELIVERABLES:
        owner = "travel-guide"
        status = "current"
        reason = "the terminal artifact is a traveler-facing guide or plan"
        if research_required:
            child_routes.append("investigation")
    else:
        owner = None
        status = "ambiguous"
        reason = "terminal deliverable does not identify one final owner"

    material = {
        "request_id": request_id,
        "requested_terminal_kind": requested_kind,
        "terminal_deliverable": deliverable,
        "scope_class": scope_class,
        "substantial_research_required": research_required,
        "constraints": require_mapping(request.get("constraints", {}), "constraints"),
    }
    decision = {
        "schema_version": "1.0",
        "decision_id": decision_id,
        "request_fingerprint": fingerprint(material),
        "terminal_deliverable": deliverable,
        "final_owner": owner,
        "child_routes": child_routes,
        "material_assumptions": require_string_list(
            request.get("material_assumptions", []),
            "material_assumptions",
        ),
        "status": status,
        "reason": reason,
        "stale_because": [],
        "decided_at": decided_at,
    }
    decision["decision_fingerprint"] = fingerprint(decision)
    require_schema("route-decision.schema.json", decision, label="route decision")
    return decision


def validate_request(value):
    result = select_route(value)
    return validation_result(status="current_pass" if result["status"] in {"current", "skipped"} else "blocked", route_decision=result)


if __name__ == "__main__":
    raise SystemExit(cli_validate(validate_request, __doc__))
