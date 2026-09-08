"""Resolve the single applicable reader-review obligation manifest."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from _common import ValidationError, fingerprint


BASE = (
    ("fact_content_fidelity", "required", "Every selected content unit must remain faithful to its declared meaning."),
    ("instruction_fidelity", "required", "The artifact must satisfy the ReaderIntent and selected structure."),
    ("throughline", "required", "The artifact must maintain the declared central question and throughline."),
    ("material_boundaries", "required", "Every material limitation must be visible or materially narrow the claim."),
)


# These are the route review dimensions, kept here as the stable bridge from
# the semantic obligation vocabulary to the actual-artifact review vocabulary.
# Each obligation in a manifest receives exactly one dimension ID; closure
# consumers must use this manifest rather than maintaining a second list.
DIMENSION_IDS = {
    "investigation": {
        "fact_content_fidelity": "bounded_answer",
        "instruction_fidelity": "recoverable_question",
        "throughline": "conclusion_scope",
        "material_boundaries": "limitations",
        "evidence_strength": "evidence_strength",
        "alternative_and_recheck": "alternatives",
    },
    "academic-writing": {
        "fact_content_fidelity": "paragraph_contribution",
        "instruction_fidelity": "research_question",
        "throughline": "central_contribution",
        "material_boundaries": "qualification_implication",
        "method_conditions": "method_depth",
        "figure_table_jobs": "figure_table_jobs",
    },
    "fiction-writing": {
        "fact_content_fidelity": "continuity",
        "instruction_fidelity": "output_room",
        "throughline": "reader_state",
        "material_boundaries": "resistance_cost",
        "pov_voice": "pov_voice",
        "reveal_boundary": "promise_reveal",
        "scene_movement": "story_movement",
        "revision_report": "actual_spans",
    },
    "travel-guide": {
        "fact_content_fidelity": "local_texture",
        "instruction_fidelity": "guide_kind",
        "throughline": "narrative_body",
        "material_boundaries": "source_recheck",
        "traveler_fit": "traveler_fit",
        "operational_information": "operational_appendix",
        "appendix": "unit_responsibility",
    },
}


def _row(
    owner: str,
    obligation_id: str,
    status: str,
    basis: str,
    *,
    applicability: str | None = None,
) -> dict[str, str]:
    """Create one manifest row with explicit canonical applicability.

    ``not_applicable_with_reason`` is retained as the public status spelling
    used by the 3.x candidate fixtures.  ``applicability`` is the canonical
    machine field, so new consumers can distinguish N/A from a failed or
    omitted obligation without relying on the legacy suffix.
    """
    canonical = applicability or ("not_applicable" if status.startswith("not_applicable") else status)
    return {
        "obligation_id": obligation_id,
        "dimension_id": DIMENSION_IDS[owner][obligation_id],
        "status": status,
        "applicability": canonical,
        "basis": basis,
    }


def resolve_review_obligations(owner: str, profile: str, reader_intent: Mapping[str, Any], selected_composition: Mapping[str, Any]) -> dict[str, Any]:
    if owner not in {"investigation", "academic-writing", "fiction-writing", "travel-guide"}:
        raise ValidationError(f"unknown review owner: {owner}")
    intent = dict(reader_intent)
    obligations = [_row(owner, key, status, basis) for key, status, basis in BASE]
    if owner == "academic-writing":
        empirical = profile == "empirical_paper"
        has_figures = bool(selected_composition.get("figure_table_jobs"))
        obligations.append(_row(owner, "method_conditions", "required", "Empirical papers must state methods and their conditions."))
        obligations.append(_row(
            owner,
            "figure_table_jobs",
            "required" if has_figures else "not_applicable_with_reason",
            "Declared figure/table jobs are reviewed when present; conceptual arguments without them have no figure obligation.",
        ))
        if not empirical:
            obligations[-2]["basis"] = "Method depth remains required for this profile's claims and evidence." if profile != "conceptual_argument" else "A conceptual argument has no empirical method conditions to review."
            if profile == "conceptual_argument":
                obligations[-2]["status"] = "not_applicable_with_reason"
                obligations[-2]["applicability"] = "not_applicable"
    elif owner == "fiction-writing":
        obligations.extend([
            _row(owner, "pov_voice", "required", "The final artifact must remain in the selected point of view and voice."),
            _row(owner, "reveal_boundary", "required", "Prohibited reveals remain unknown to the focal character until licensed."),
            _row(owner, "scene_movement", "required", "The final scene or movement must cause a reader-state or story-state change."),
        ])
        if selected_composition.get("artifact_kind") == "revision" or profile == "audit":
            obligations.append(_row(owner, "revision_report", "required", "A fiction revision task must report actual changes and their continuity effects."))
    elif owner == "travel-guide":
        has_appendix = bool(selected_composition.get("appendix_sections"))
        obligations.extend([
            _row(owner, "traveler_fit", "required", "Practical recommendations must match the declared traveler conditions."),
            _row(owner, "operational_information", "required", "Operational information must occur in a reasonable body or appendix location."),
            _row(
                owner,
                "appendix",
                "required" if has_appendix else "not_applicable_with_reason",
                "An appendix is reviewed only when selected by the composition; no empty appendix is invented.",
            ),
        ])
    else:
        obligations.extend([
            _row(owner, "evidence_strength", "required", "Answers retain the declared evidence strength."),
            _row(owner, "alternative_and_recheck", "required", "Live alternatives and recheck conditions remain actionable."),
        ])
    if len({row["dimension_id"] for row in obligations}) != len(obligations):
        raise ValidationError("review obligation dimensions must map one-to-one to stable review IDs")
    manifest = {
        "schema_version": "1.1",
        "owner": owner,
        "profile": profile,
        "reader_intent_fingerprint": intent.get("intent_fingerprint"),
        "selected_composition_fingerprint": fingerprint(dict(selected_composition)),
        "obligations": obligations,
    }
    manifest["manifest_fingerprint"] = fingerprint(manifest)
    return manifest


def validate_review_obligation_manifest(
    value: Mapping[str, Any],
    *,
    owner: str | None = None,
    profile: str | None = None,
    reader_intent_fingerprint: str | None = None,
    selected_composition: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a manifest and optionally rederive it from current inputs."""
    if not isinstance(value, Mapping):
        raise ValidationError("review obligation manifest must be an object")
    manifest = dict(value)
    if manifest.get("schema_version") not in {"1.0", "1.1"}:
        raise ValidationError("review obligation manifest has an unsupported schema version")
    if manifest.get("manifest_fingerprint") != fingerprint({k: v for k, v in manifest.items() if k != "manifest_fingerprint"}):
        raise ValidationError("review obligation manifest fingerprint is stale")
    if owner is not None and manifest.get("owner") != owner:
        raise ValidationError("review obligation manifest belongs to a sibling owner")
    if profile is not None and manifest.get("profile") != profile:
        raise ValidationError("review obligation manifest belongs to a different profile")
    if reader_intent_fingerprint is not None and manifest.get("reader_intent_fingerprint") != reader_intent_fingerprint:
        raise ValidationError("review obligation manifest is stale for ReaderIntent")
    if selected_composition is not None:
        expected = resolve_review_obligations(
            str(manifest["owner"]), str(manifest["profile"]),
            {"intent_fingerprint": manifest.get("reader_intent_fingerprint")},
            selected_composition,
        )
        expected_obligations = expected["obligations"]
        if manifest.get("selected_composition_fingerprint") != expected["selected_composition_fingerprint"] or manifest.get("obligations") != expected_obligations:
            raise ValidationError("review obligation manifest is not derived from current composition")
    obligations = manifest.get("obligations")
    if not isinstance(obligations, list) or not obligations:
        raise ValidationError("review obligation manifest must contain obligations")
    ids = [str(row.get("obligation_id", "")) for row in obligations]
    dimensions = [str(row.get("dimension_id", "")) for row in obligations]
    if not all(ids) or len(set(ids)) != len(ids) or not all(dimensions) or len(set(dimensions)) != len(dimensions):
        raise ValidationError("review obligation IDs and dimension IDs must be unique")
    for row in obligations:
        status = row.get("status")
        applicability = row.get("applicability")
        if status == "required" and applicability not in {None, "required"}:
            raise ValidationError("required review obligation has non-required applicability")
        if status and status.startswith("not_applicable") and applicability != "not_applicable":
            raise ValidationError("N/A review obligation must declare canonical not_applicable applicability")
    return manifest


__all__ = ["DIMENSION_IDS", "resolve_review_obligations", "validate_review_obligation_manifest"]
