"""Select exactly one Logic Writing final owner while preserving ReaderIntent v2."""

from __future__ import annotations

from _common import (
    ValidationError,
    cli_validate,
    fingerprint,
    require_datetime,
    require_identifier,
    require_mapping,
    require_schema,
    require_string_list,
    validation_result,
)
from reader_pipeline import validate_writing_request


INVESTIGATION_DELIVERABLES = {
    "research_report", "briefing", "evidence_package", "decision_note",
    "investigated_answer", "memo", "evidence_audit", "policy_analysis",
    "market_analysis", "case_investigation",
}
ACADEMIC_DELIVERABLES = {
    "paper", "thesis", "thesis_chapter", "dissertation", "dissertation_section",
    "academic_chapter", "literature_review", "formal_literature_review",
    "research_proposal", "proposal", "academic_revision",
}
FICTION_DELIVERABLES = {
    "short_story", "fiction_chapter", "novel", "novella", "fiction_outline",
    "story_plan", "series_bible", "story_audit", "fiction_revision",
}
TRAVEL_DELIVERABLES = {
    "itinerary", "destination_guide", "travel_guide", "lodging_strategy",
    "route_plan", "traveler_fit_recommendation", "travel_revision",
}
TRIVIAL_CLASSES = {
    "quick_lookup", "quick_fact", "grammar_only", "formatting_only",
    "casual_copy", "casual_summary",
}


def select_route(value):
    envelope = require_mapping(value, "route selection request")
    allowed = {
        "writing_request", "decision_id", "decided_at", "material_assumptions",
        "substantial_research_required", "intent_conflicts",
    }
    unknown = sorted(set(envelope) - allowed)
    if unknown:
        raise ValidationError(f"route selection request has unknown current fields: {unknown}")
    request = validate_writing_request(envelope.get("writing_request"))
    decision_id = require_identifier(envelope, "decision_id", min_length=3, max_length=128)
    decided_at = require_datetime(envelope, "decided_at")
    material_assumptions = require_string_list(
        envelope.get("material_assumptions", []), "material_assumptions"
    )
    research_required = envelope.get("substantial_research_required", False)
    if not isinstance(research_required, bool):
        raise ValidationError("substantial_research_required must be boolean")
    conflicts = envelope.get("intent_conflicts", [])
    if not isinstance(conflicts, list):
        raise ValidationError("intent_conflicts must be an array")
    material_conflicts = [row for row in conflicts if isinstance(row, dict) and row.get("material") is True]

    kind = request["terminal_deliverable"]["kind"]
    child_routes: list[str] = []
    if material_conflicts:
        owner = None
        status = "blocked"
        reason = "material ReaderIntent conflicts must be resolved before final drafting"
    elif kind in TRIVIAL_CLASSES:
        owner = None
        status = "skipped"
        reason = f"terminal deliverable {kind} does not activate Logic Writing"
    elif kind in INVESTIGATION_DELIVERABLES:
        owner = "investigation"
        status = "current"
        reason = "the terminal artifact is an investigation product"
    elif kind in ACADEMIC_DELIVERABLES:
        owner = "academic-writing"
        status = "current"
        reason = "the terminal artifact is academic"
    elif kind in FICTION_DELIVERABLES:
        owner = "fiction-writing"
        status = "current"
        reason = "the terminal artifact is fiction"
    elif kind in TRAVEL_DELIVERABLES:
        owner = "travel-guide"
        status = "current"
        reason = "the terminal artifact is a traveler-facing guide or plan"
    else:
        owner = None
        status = "ambiguous"
        reason = "terminal deliverable does not identify one final owner"
    if owner in {"academic-writing", "fiction-writing", "travel-guide"} and research_required:
        child_routes.append("investigation")

    decision = {
        "schema_version": "2.0",
        "decision_id": decision_id,
        "request_fingerprint": request["request_fingerprint"],
        "reader_intent": request["reader_intent"],
        "reader_intent_fingerprint": request["reader_intent"]["intent_fingerprint"],
        "terminal_deliverable": request["terminal_deliverable"],
        "final_owner": owner,
        "child_routes": child_routes if owner is not None else [],
        "material_assumptions": material_assumptions,
        "intent_conflicts": conflicts,
        "status": status,
        "reason": reason,
        "stale_because": [],
        "decided_at": decided_at,
    }
    decision["decision_fingerprint"] = fingerprint(decision)
    require_schema("route-decision.schema.json", decision, label="RouteDecision")
    return decision


def validate_request(value):
    result = select_route(value)
    return validation_result(
        status="current_pass" if result["status"] in {"current", "skipped"} else "blocked",
        route_decision=result,
    )


if __name__ == "__main__":
    raise SystemExit(cli_validate(validate_request, __doc__))


__all__ = ["select_route"]
