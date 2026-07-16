#!/usr/bin/env python3
"""Aggregate Longform Mode closure evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

import chapter_interface_check
import evidence_identity
import guard_handoff_check
import model_prose_binding_check
import novel_ledger_check
import promise_payoff_check
import semantic_review_check
import story_contribution_check
import storyline_route_check
import voice_style_continuity_check


UNIVERSAL_GUARD_SURFACES = {
    "flowguard_process",
    "traceguard_storyline",
    "worldguard_story_claims",
    "logicguard_theme_support",
    "sourceguard_canon_support",
}
LEVEL_REQUIRED_SURFACES = {
    "chapter": UNIVERSAL_GUARD_SURFACES | {"novel_ledger", "story_contribution", "chapter_interface", "promise_payoff", "voice_style"},
    "volume": UNIVERSAL_GUARD_SURFACES | {"novel_ledger", "story_contribution", "chapter_interface", "promise_payoff", "voice_style", "reverse_outline"},
    "book": UNIVERSAL_GUARD_SURFACES | {"novel_ledger", "story_contribution", "chapter_interface", "promise_payoff", "voice_style", "reverse_outline"},
    "series": UNIVERSAL_GUARD_SURFACES | {"novel_ledger", "story_contribution", "chapter_interface", "promise_payoff", "voice_style", "reverse_outline"},
}
PASS_STATUSES = {"passed", "pass", "scoped_out", "not_applicable_with_reason"}
REASONED_NONPASS_STATUSES = {"scoped_out", "not_applicable_with_reason"}
DECISIONS = {"passed", "partial", "blocked", "downgraded", "human_review", "human-review"}
FINAL_PROSE_REQUIRED_SURFACES = {"source_requirements", "final_artifact", "artifact_bound_review", "model_prose_binding"}
SOURCE_REQUIREMENTS_SCHEMA_VERSION = "storyline-design.source_requirements.v1"
LOCAL_MODEL_SURFACES = {
    "novel_ledger",
    "story_contribution",
    "chapter_interface",
    "promise_payoff",
    "voice_style",
    "reverse_outline",
    "model_prose_binding",
}
MODEL_OR_GUARD_SURFACES = LOCAL_MODEL_SURFACES | UNIVERSAL_GUARD_SURFACES
PROSE_ONLY_EVIDENCE_PREFIXES = ("review:", "ai:", "llm:", "self-report:", "model-answer:")


class Reporter:
    def __init__(self) -> None:
        self.issues: list[dict[str, str]] = []

    def error(self, code: str, path: str, message: str) -> None:
        self.issues.append({"severity": "error", "code": code, "path": path, "message": message})

    @property
    def error_count(self) -> int:
        return len(self.issues)


def nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def normalize(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().lower().split())


def normalize_code(value: Any) -> str:
    return normalize(value).replace("-", "_").replace(" ", "_")


def evidence_ref_is_prose_only(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return normalize(value).startswith(PROSE_ONLY_EVIDENCE_PREFIXES)


def has_reason(surface: dict[str, Any]) -> bool:
    for field in ("not_applicable_reason", "skip_reason", "reason", "next_action", "evidence_ref"):
        value = surface.get(field)
        if not isinstance(value, str) or not value.strip():
            continue
        lowered = value.lower()
        if "reason" in lowered or "because" in lowered or "not applicable" in lowered or "scoped" in lowered or "no material" in lowered:
            return True
    return False


def combined_reason_text(surface: dict[str, Any]) -> str:
    values = []
    for field in ("not_applicable_reason", "skip_reason", "reason", "next_action", "evidence_ref"):
        value = surface.get(field)
        if isinstance(value, str):
            values.append(value)
    return normalize(" ".join(values))


def is_fiction_only_worldguard_scopeout(name: Any, status: str, surface: dict[str, Any]) -> bool:
    if name not in {"worldguard", "worldguard_story_claims"}:
        return False
    if status not in {"not_applicable_with_reason", "scoped_out"}:
        return False
    reason = combined_reason_text(surface)
    if "fiction" not in reason and "fictional" not in reason and "invented" not in reason:
        return False
    material_boundary_terms = (
        "no material world",
        "no event",
        "no ability",
        "no capability",
        "no access",
        "no resource",
        "no rule",
        "no caus",
        "no consequence",
        "does not affect",
    )
    return not any(term in reason for term in material_boundary_terms)


def evidence_reference_path(value: str) -> Path:
    reference = value.split(";", 1)[0].strip()
    if reference.startswith("file:"):
        reference = reference[5:]
    reference = reference.split("#", 1)[0].strip()
    return Path(reference)


def resolve_evidence_path(base_path: Path, value: str) -> Path:
    path = evidence_reference_path(value)
    if path.is_absolute():
        return path
    candidates: list[Path] = []
    anchors = [base_path.parent, *base_path.parents, Path.cwd(), *Path.cwd().parents]
    seen: set[str] = set()
    for anchor in anchors:
        candidate = anchor / path
        key = str(candidate.resolve(strict=False)).lower()
        if key not in seen:
            candidates.append(candidate)
            seen.add(key)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else path


def evidence_ref_is_local_json(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    reference = value.split(";", 1)[0].strip()
    if reference.startswith("file:"):
        reference = reference[5:]
    lowered = reference.lower()
    if lowered.startswith(("review:", "http://", "https://", "urn:", "id:")):
        return False
    reference = reference.split("#", 1)[0].strip()
    return bool(reference) and Path(reference).suffix.lower() == ".json"


def reverse_outline_rows(payload: Any) -> tuple[list[Any], str]:
    if isinstance(payload, list):
        return payload, "reverse_outlines"
    if isinstance(payload, dict) and isinstance(payload.get("reverse_outlines"), list):
        return payload["reverse_outlines"], "reverse_outlines"
    if (
        isinstance(payload, dict)
        and isinstance(payload.get("chapter_interface_bundle"), dict)
        and isinstance(payload["chapter_interface_bundle"].get("reverse_outlines"), list)
    ):
        return payload["chapter_interface_bundle"]["reverse_outlines"], "chapter_interface_bundle.reverse_outlines"
    if isinstance(payload, dict) and isinstance(payload.get("chapters"), list):
        return payload["chapters"], "chapters"
    return [], ""


def validate_reverse_outline_evidence(payload: Any, source_path: str) -> dict[str, Any]:
    reporter = Reporter()
    rows, collection_path = reverse_outline_rows(payload)
    if not rows:
        reporter.error("missing_reverse_outlines", "$", "Expected reverse_outlines evidence from actual prose.")
    for index, row in enumerate(rows):
        path = f"{collection_path}[{index}]" if collection_path else f"reverse_outlines[{index}]"
        if not isinstance(row, dict):
            reporter.error("invalid_row_type", path, "Reverse outline row must be an object.")
            continue
        for field in ("id", "chapter_id", "source_draft_ref", "model_alignment", "status"):
            if not nonempty_str(row.get(field)):
                reporter.error("missing_required_field", f"{path}.{field}", "Required reverse-outline field is missing.")
        for field in ("observed_events", "observed_reader_state_after", "observed_promise_movements", "observed_arc_movements"):
            value = row.get(field)
            if not isinstance(value, list):
                reporter.error("invalid_type", f"{path}.{field}", "Expected list.")
            elif not value:
                reporter.error("empty_required_list", f"{path}.{field}", "Reverse-outline evidence must be event-and-state specific, not a broad pass label.")
        if not isinstance(row.get("drift"), list):
            reporter.error("invalid_type", f"{path}.drift", "Expected list.")
        if row.get("model_alignment") not in {"pass", "passed"} or row.get("status") not in {"pass", "passed"}:
            reporter.error("reverse_outline_not_passed", f"{path}.status", "Reverse outline must align with the model.")
    return {
        "schema_version": "storyline-design.reverse_outline_evidence_check.report.v1",
        "source_path": source_path,
        "passed": reporter.error_count == 0,
        "summary": {"error_count": reporter.error_count, "issue_count": len(reporter.issues), "reverse_outline_count": len(rows)},
        "issues": reporter.issues,
    }


MODEL_SURFACE_VALIDATORS: dict[str, tuple[str, Callable[[Any, str], dict[str, Any]]]] = {
    "novel_ledger": ("novel_ledger_check", novel_ledger_check.validate_ledger),
    "story_contribution": ("story_contribution_check", story_contribution_check.validate),
    "chapter_interface": ("chapter_interface_check", chapter_interface_check.validate),
    "promise_payoff": ("promise_payoff_check", promise_payoff_check.validate_promises),
    "voice_style": ("voice_style_continuity_check", voice_style_continuity_check.validate),
    "reverse_outline": ("reverse_outline_evidence_check", validate_reverse_outline_evidence),
    "model_prose_binding": ("model_prose_binding_check", model_prose_binding_check.validate),
}


def summarize_child_issues(report: dict[str, Any]) -> str:
    issues = report.get("issues")
    if not isinstance(issues, list) or not issues:
        return "no child issue details"
    snippets: list[str] = []
    for issue in issues[:3]:
        if not isinstance(issue, dict):
            continue
        code = issue.get("code", "issue")
        path = issue.get("path", "$")
        snippets.append(f"{code} at {path}")
    remaining = len(issues) - len(snippets)
    if remaining > 0:
        snippets.append(f"{remaining} more")
    return "; ".join(snippets) if snippets else "no child issue details"


def validate_surface_evidence(
    surface: Any,
    index: int,
    base_path: Path,
    reporter: Reporter,
    repository_root: str | Path | None = None,
    final_prose: bool = False,
) -> None:
    if not isinstance(surface, dict):
        return
    name = surface.get("surface")
    status = surface.get("status")
    path = f"required_surfaces[{index}]"
    normalized_status = normalize_code(status)
    if name in UNIVERSAL_GUARD_SURFACES and normalized_status in {"pass", "passed", "scoped_out", "not_applicable_with_reason"}:
        expected_input_fingerprint = surface.get("input_fingerprint")
        if not nonempty_str(expected_input_fingerprint):
            reporter.error(
                "missing_guard_input_fingerprint",
                f"{path}.input_fingerprint",
                f"Guard surface {name!r} must bind its handoff to the closure owner's current expected input fingerprint.",
            )
        report = guard_handoff_check.validate_reference(
            surface.get("evidence_ref"),
            str(base_path),
            str(name),
            repository_root=repository_root,
            expected_input_fingerprint=expected_input_fingerprint if nonempty_str(expected_input_fingerprint) else None,
        )
        if report.get("passed") is not True:
            reporter.error(
                "guard_handoff_invalid",
                f"{path}.evidence_ref",
                f"Guard surface {name!r} did not consume a current native terminal receipt: {summarize_child_issues(report)}.",
            )
        else:
            terminal_status = normalize_code(report.get("handoff", {}).get("terminal_status"))
            expected_status = "passed" if normalized_status == "pass" else normalized_status
            if terminal_status != expected_status:
                reporter.error(
                    "guard_terminal_status_mismatch",
                    f"{path}.status",
                    f"Closure status {normalized_status!r} does not match Guard terminal receipt status {terminal_status!r}.",
                )
        return
    if name not in LOCAL_MODEL_SURFACES or status not in {"pass", "passed"}:
        return
    if final_prose and name in FINAL_PROSE_REQUIRED_SURFACES:
        return
    evidence_ref = surface.get("evidence_ref")
    if name == "model_prose_binding":
        try:
            identity = evidence_identity.verify_content_reference(evidence_ref, base_path, repository_root)
            root = evidence_identity.repository_root_for(base_path, repository_root)
            evidence_path = root / identity["repository_path"]
        except evidence_identity.EvidenceIdentityError as exc:
            reporter.error(exc.code, f"{path}.evidence_ref", exc.message)
            return
    else:
        if not evidence_ref_is_local_json(evidence_ref):
            reporter.error(
                "surface_evidence_not_local_json",
                f"{path}.evidence_ref",
                f"Passed surface {name!r} must point to local JSON evidence that can be opened and validated.",
            )
            return
        evidence_path = resolve_evidence_path(base_path, str(evidence_ref))
    try:
        payload = load_json(evidence_path)
    except OSError as exc:
        reporter.error("surface_evidence_missing", f"{path}.evidence_ref", f"Cannot read {name!r} evidence {evidence_ref!r}: {exc}")
        return
    except json.JSONDecodeError as exc:
        reporter.error(
            "surface_evidence_invalid_json",
            f"{path}.evidence_ref",
            f"{name!r} evidence {evidence_ref!r} is invalid JSON at line {exc.lineno}, column {exc.colno}.",
        )
        return
    validator_name, validator = MODEL_SURFACE_VALIDATORS[str(name)]
    try:
        if name == "model_prose_binding":
            report = model_prose_binding_check.validate(payload, str(evidence_path), repository_root)
        else:
            report = validator(payload, str(evidence_path))
    except Exception as exc:  # pragma: no cover - defensive boundary for validator crashes.
        reporter.error("surface_validator_error", f"{path}.evidence_ref", f"{validator_name} crashed for {name!r}: {exc}")
        return
    if not isinstance(report, dict) or report.get("passed") is not True:
        child_summary = summarize_child_issues(report) if isinstance(report, dict) else "validator did not return a report"
        reporter.error(
            "surface_evidence_invalid",
            f"{path}.evidence_ref",
            f"Passed surface {name!r} did not pass {validator_name}: {child_summary}.",
        )


def final_prose_claimed(route_decision: dict[str, Any] | None) -> bool:
    return isinstance(route_decision, dict) and route_decision.get("prose_phase") == "final_prose"


def validate_surface(surface: Any, index: int, reporter: Reporter) -> str:
    path = f"required_surfaces[{index}]"
    if not isinstance(surface, dict):
        reporter.error("invalid_row_type", path, "Required surface entry must be an object.")
        return ""
    for field in ("surface", "status", "evidence_ref", "next_action"):
        if not nonempty_str(surface.get(field)):
            reporter.error("missing_required_field", f"{path}.{field}", "Required surface field is missing.")
    name = surface.get("surface", "")
    status = normalize_code(surface.get("status"))
    if name in MODEL_OR_GUARD_SURFACES and status in {"passed", "pass"} and evidence_ref_is_prose_only(surface.get("evidence_ref")):
        reporter.error(
            "prose_only_evidence",
            f"{path}.evidence_ref",
            f"Required surface {name!r} cannot be closed by prose-only review or AI self-report evidence.",
        )
    if status in REASONED_NONPASS_STATUSES:
        if surface.get("blocks_closure") is True:
            reporter.error(
                "reasoned_nonpass_blocks_closure",
                f"{path}.blocks_closure",
                f"Surface {name!r} cannot be {status} and blocks_closure=true.",
            )
        if not has_reason(surface):
            reporter.error(
                "missing_reason_for_nonpass_surface",
                f"{path}.evidence_ref",
                f"Surface {name!r} is {status} but does not state the reason.",
            )
        if is_fiction_only_worldguard_scopeout(name, status, surface):
            reporter.error(
                "fictional_world_auto_scopeout",
                path,
                "WorldGuard cannot be marked not applicable merely because the story is fictional.",
            )
    if surface.get("blocks_closure") is True and status not in PASS_STATUSES:
        reporter.error("blocking_surface_not_passed", f"{path}.status", f"Surface {name!r} blocks closure and is not passed.")
    if status not in PASS_STATUSES and surface.get("blocks_closure") is not False:
        reporter.error("surface_not_passed", f"{path}.status", f"Surface {name!r} is required but not passed or scoped out.")
    return name if isinstance(name, str) else ""


def validate_child_report(report: Any, index: int, reporter: Reporter) -> None:
    path = f"child_reports[{index}]"
    if not isinstance(report, dict):
        reporter.error("invalid_row_type", path, "Child report must be an object.")
        return
    for field in ("id", "level", "status", "evidence_ref"):
        if not nonempty_str(report.get(field)):
            reporter.error("missing_required_field", f"{path}.{field}", "Required child report field is missing.")
    if report.get("blocks_parent") is True and report.get("status") not in PASS_STATUSES:
        reporter.error("blocking_child_report", f"{path}.status", "Child report blocks parent closure.")


def open_verified_json_surface(
    surface: dict[str, Any],
    index: int,
    base_path: Path,
    repository_root: str | Path | None,
    reporter: Reporter,
) -> tuple[Any, Path, dict[str, str]] | None:
    path = f"required_surfaces[{index}].evidence_ref"
    try:
        identity = evidence_identity.verify_content_reference(surface.get("evidence_ref"), base_path, repository_root)
        root = evidence_identity.repository_root_for(base_path, repository_root)
        evidence_path = root / identity["repository_path"]
        payload = load_json(evidence_path)
    except evidence_identity.EvidenceIdentityError as exc:
        reporter.error(exc.code, path, exc.message)
        return None
    except OSError as exc:
        reporter.error("content_read_error", path, f"Cannot read structured evidence: {exc}")
        return None
    except json.JSONDecodeError as exc:
        reporter.error(
            "structured_evidence_invalid_json",
            path,
            f"Structured evidence is invalid JSON at line {exc.lineno}, column {exc.colno}.",
        )
        return None
    return payload, evidence_path, identity


def validate_source_requirements(
    payload: Any,
    source_path: Path,
    repository_root: str | Path | None,
    project_id: str,
    manuscript_identity: dict[str, str] | None,
    reporter: Reporter,
) -> None:
    path = "source_requirements"
    if not isinstance(payload, dict):
        reporter.error("invalid_source_requirements", path, "Source requirements must be a JSON object.")
        return
    if payload.get("schema_version") != SOURCE_REQUIREMENTS_SCHEMA_VERSION:
        reporter.error("invalid_source_requirements_schema", f"{path}.schema_version", f"Expected {SOURCE_REQUIREMENTS_SCHEMA_VERSION}.")
    if not nonempty_str(payload.get("requirements_id")):
        reporter.error("missing_required_field", f"{path}.requirements_id", "Source requirements need a stable requirements_id.")
    if payload.get("project_id") != project_id:
        reporter.error("source_requirements_project_mismatch", f"{path}.project_id", "Source requirements must bind the closure project_id.")
    requirements = payload.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        reporter.error("missing_source_requirements", f"{path}.requirements", "At least one structured source requirement is required.")
        requirements = []
    for index, row in enumerate(requirements):
        row_path = f"{path}.requirements[{index}]"
        if not isinstance(row, dict):
            reporter.error("invalid_source_requirement", row_path, "Source requirement row must be an object.")
            continue
        for field in ("id", "requirement", "status"):
            if not nonempty_str(row.get(field)):
                reporter.error("missing_required_field", f"{row_path}.{field}", f"Source requirement {field} is required.")
        if row.get("status") not in {"satisfied", "pass", "passed"}:
            reporter.error("unsatisfied_source_requirement", f"{row_path}.status", "Final prose closure requires every source requirement to be satisfied.")
    unmet = payload.get("unmet_requirements")
    if not isinstance(unmet, list):
        reporter.error("invalid_type", f"{path}.unmet_requirements", "unmet_requirements must be a list.")
    elif unmet:
        reporter.error("unmet_source_requirements", f"{path}.unmet_requirements", "Final prose closure cannot retain unmet source requirements.")
    if payload.get("decision") != "passed":
        reporter.error("source_requirements_not_passed", f"{path}.decision", "Source requirements decision must be passed.")
    try:
        identity = evidence_identity.verify_content_reference(payload.get("artifact_ref"), source_path, repository_root)
        evidence_identity.require_matching_sha256(payload.get("artifact_sha256"), identity["sha256"])
    except evidence_identity.EvidenceIdentityError as exc:
        reporter.error("stale_source_requirements", f"{path}.{exc.path}", exc.message)
        return
    if manuscript_identity is not None and identity["sha256"] != manuscript_identity["sha256"]:
        reporter.error("stale_source_requirements", f"{path}.artifact_ref", "Source requirements bind a different manuscript identity.")


def validate_bound_child_report(
    report: Any,
    kind: str,
    project_id: str,
    manuscript_identity: dict[str, str] | None,
    reporter: Reporter,
) -> None:
    path = kind
    invalid_code = f"{kind}_invalid"
    stale_code = f"stale_{kind}"
    if not isinstance(report, dict):
        reporter.error(invalid_code, path, f"{kind} validator did not return a structured report.")
        return
    if report.get("passed") is not True:
        child_codes = {
            issue.get("code")
            for issue in report.get("issues", [])
            if isinstance(issue, dict) and isinstance(issue.get("code"), str)
        }
        identity_codes = {"content_hash_mismatch", "content_file_missing", "artifact_sha256_mismatch"}
        code = stale_code if child_codes & identity_codes else invalid_code
        reporter.error(code, path, f"{kind} did not pass its native structured validator: {summarize_child_issues(report)}.")
    if report.get("project_id") != project_id:
        reporter.error(f"{kind}_project_mismatch", f"{path}.project_id", f"{kind} must bind the closure project_id.")
    identity = report.get("artifact_identity")
    if not isinstance(identity, dict) or not nonempty_str(identity.get("sha256")):
        reporter.error(stale_code, f"{path}.artifact_identity", f"{kind} did not prove a current manuscript identity.")
    elif manuscript_identity is not None and identity.get("sha256") != manuscript_identity.get("sha256"):
        reporter.error(stale_code, f"{path}.artifact_identity", f"{kind} binds a different manuscript identity.")


def validate_final_prose_surfaces(
    surfaces: list[Any],
    base_path: Path,
    repository_root: str | Path | None,
    project_id: str,
    route_decision: dict[str, Any],
    reporter: Reporter,
) -> dict[str, str] | None:
    by_name: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for index, surface in enumerate(surfaces):
        if isinstance(surface, dict) and isinstance(surface.get("surface"), str):
            by_name.setdefault(surface["surface"], []).append((index, surface))
    route_surfaces = route_decision.get("required_surfaces")
    if not isinstance(route_surfaces, list) or not FINAL_PROSE_REQUIRED_SURFACES.issubset(set(route_surfaces)):
        reporter.error("route_missing_final_prose_contract", "route_decision.required_surfaces", "Compiled final-prose route must require all four final evidence surfaces.")
    for required in sorted(FINAL_PROSE_REQUIRED_SURFACES):
        if required not in by_name:
            reporter.error(
                "missing_final_prose_surface",
                "required_surfaces",
                f"Final prose closure requires surface {required!r}.",
            )
        elif len(by_name[required]) > 1:
            reporter.error("duplicate_final_prose_surface", "required_surfaces", f"Final prose surface {required!r} must appear exactly once.")
        else:
            index, surface = by_name[required][0]
            if normalize_code(surface.get("status")) not in {"pass", "passed"}:
                reporter.error("final_prose_surface_not_passed", f"required_surfaces[{index}].status", f"Final prose surface {required!r} must be passed.")

    manuscript_identity: dict[str, str] | None = None
    if by_name.get("final_artifact"):
        index, surface = by_name["final_artifact"][0]
        try:
            manuscript_identity = evidence_identity.verify_content_reference(surface.get("evidence_ref"), base_path, repository_root)
        except evidence_identity.EvidenceIdentityError as exc:
            reporter.error(exc.code, f"required_surfaces[{index}].evidence_ref", exc.message)

    source_record = by_name.get("source_requirements")
    if source_record:
        index, surface = source_record[0]
        opened = open_verified_json_surface(surface, index, base_path, repository_root, reporter)
        if opened is not None:
            payload, evidence_path, _ = opened
            validate_source_requirements(payload, evidence_path, repository_root, project_id, manuscript_identity, reporter)

    if by_name.get("artifact_bound_review"):
        index, surface = by_name["artifact_bound_review"][0]
        opened = open_verified_json_surface(surface, index, base_path, repository_root, reporter)
        if opened is not None:
            payload, evidence_path, _ = opened
            report = semantic_review_check.validate(payload, str(evidence_path), repository_root)
            validate_bound_child_report(report, "semantic_review", project_id, manuscript_identity, reporter)

    if by_name.get("model_prose_binding"):
        index, surface = by_name["model_prose_binding"][0]
        opened = open_verified_json_surface(surface, index, base_path, repository_root, reporter)
        if opened is not None:
            payload, evidence_path, _ = opened
            report = model_prose_binding_check.validate(payload, str(evidence_path), repository_root)
            validate_bound_child_report(report, "model_prose_binding", project_id, manuscript_identity, reporter)
    return manuscript_identity


def validate(
    payload: Any,
    source_path: str,
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    reporter = Reporter()
    base_path = Path(source_path)
    if not isinstance(payload, dict):
        reporter.error("invalid_root_type", "$", "Longform closure bundle must be an object.")
        payload = {}
    required_fields = ["schema_version", "project_id", "closure_id", "artifact_type", "prose_phase", "closure_level", "claim_boundary", "decision"]
    for field in required_fields:
        if not nonempty_str(payload.get(field)):
            reporter.error("missing_required_field", field, "Required closure field is missing.")
    if payload.get("schema_version") != "storyline-design.longform_closure.v1":
        reporter.error("invalid_schema_version", "schema_version", "Expected storyline-design.longform_closure.v1.")
    route_decision: dict[str, Any] | None = None
    try:
        route_decision = storyline_route_check.compile_route_decision(payload)
    except storyline_route_check.RouteBlocked as exc:
        reporter.error(exc.code, exc.field or "route_decision", exc.message)
    level = payload.get("closure_level")
    if level not in LEVEL_REQUIRED_SURFACES:
        reporter.error("invalid_closure_level", "closure_level", "Closure level must be chapter, volume, book, or series.")
        required = set()
    else:
        required = LEVEL_REQUIRED_SURFACES[level]
    if route_decision is not None and route_decision.get("closure_level") != level:
        reporter.error(
            "closure_level_route_mismatch",
            "closure_level",
            f"Closure level {level!r} does not match compiled route level {route_decision.get('closure_level')!r}.",
        )
    if payload.get("decision") not in DECISIONS:
        reporter.error("invalid_decision", "decision", "Unknown closure decision.")
    surfaces = payload.get("required_surfaces")
    if not isinstance(surfaces, list):
        reporter.error("invalid_type", "required_surfaces", "required_surfaces must be a list.")
        surfaces = []
    claims_final_prose = final_prose_claimed(route_decision)
    observed = set()
    for index, surface in enumerate(surfaces):
        observed.add(validate_surface(surface, index, reporter))
        validate_surface_evidence(surface, index, base_path, reporter, repository_root, claims_final_prose)
    for surface in sorted(required - observed):
        reporter.error("missing_required_surface", "required_surfaces", f"Required surface {surface!r} is missing for {level} closure.")
    manuscript_identity: dict[str, str] | None = None
    if claims_final_prose:
        manuscript_identity = validate_final_prose_surfaces(
            surfaces,
            base_path,
            repository_root,
            str(payload.get("project_id", "")),
            route_decision or {},
            reporter,
        )
    child_reports = payload.get("child_reports")
    if not isinstance(child_reports, list):
        reporter.error("invalid_type", "child_reports", "child_reports must be a list.")
        child_reports = []
    if level in {"volume", "book", "series"} and not child_reports:
        reporter.error("missing_child_reports", "child_reports", f"{level} closure requires child reports.")
    for index, report in enumerate(child_reports):
        validate_child_report(report, index, reporter)
    for field in ("deferred_items", "blocking_items", "stale_items", "next_actions"):
        if not isinstance(payload.get(field), list):
            reporter.error("invalid_type", field, f"{field} must be a list.")
    if payload.get("decision") == "passed":
        if payload.get("blocking_items"):
            reporter.error("passed_with_blocking_items", "blocking_items", "Passed closure cannot include blocking items.")
        if payload.get("stale_items"):
            reporter.error("passed_with_stale_items", "stale_items", "Passed closure cannot include stale items.")
        if claims_final_prose and reporter.error_count and not payload.get("next_actions"):
            reporter.error("missing_revision_next_action", "next_actions", "Failed final-prose closure evidence needs a concrete revision or refresh action.")
    return {
        "schema_version": "storyline-design.longform_closure_check.report.v1",
        "source_path": source_path,
        "passed": reporter.error_count == 0,
        "closure_level": level if isinstance(level, str) else "",
        "decision": str(payload.get("decision", "")),
        "route_decision": route_decision,
        "manuscript_identity": manuscript_identity,
        "summary": {"error_count": reporter.error_count, "issue_count": len(reporter.issues), "surface_count": len(surfaces), "child_report_count": len(child_reports), "final_prose_claimed": claims_final_prose},
        "issues": reporter.issues,
    }


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate aggregate long-form closure evidence.")
    parser.add_argument("input")
    parser.add_argument("--repo-root")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        input_path = Path(args.input).expanduser()
        report = validate(load_json(input_path), str(input_path), args.repo_root)
    except OSError as exc:
        report = validate({}, args.input, args.repo_root)
        report["issues"].append({"severity": "error", "code": "read_error", "path": args.input, "message": str(exc)})
        report["summary"]["error_count"] += 1
        report["passed"] = False
    except json.JSONDecodeError as exc:
        report = validate({}, args.input, args.repo_root)
        report["issues"].append({"severity": "error", "code": "json_decode_error", "path": args.input, "message": f"{exc.msg} at line {exc.lineno}, column {exc.colno}"})
        report["summary"]["error_count"] += 1
        report["passed"] = False
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Longform closure check: {'passed' if report['passed'] else 'failed'}")
        for issue in report["issues"]:
            print(f"- [{issue['severity']}] {issue['code']} at {issue['path']}: {issue['message']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
