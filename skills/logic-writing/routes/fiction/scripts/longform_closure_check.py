#!/usr/bin/env python3
"""Check a Longform Mode closure bundle: reverse outline and source requirements.

The other story models (novel ledger, story contribution, chapter interfaces,
promise/payoff, voice/style, model-prose binding, semantic review) are run
directly with their own scripts; this check does not re-run them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import evidence_identity
import storyline_route_check


DECISIONS = {"passed", "partial", "blocked", "downgraded", "human_review", "human-review"}
CLOSURE_LEVELS = {"chapter", "volume", "book", "series"}
REVERSE_OUTLINE_LEVELS = {"volume", "book", "series"}
FINAL_PROSE_REQUIRED_SURFACES = ("final_artifact", "source_requirements")
SOURCE_REQUIREMENTS_SCHEMA_VERSION = "storyline-design.source_requirements.v1"
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


def final_prose_claimed(route_decision: dict[str, Any] | None) -> bool:
    return isinstance(route_decision, dict) and route_decision.get("prose_phase") == "final_prose"


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


def surfaces_by_name(surfaces: list[Any]) -> dict[str, tuple[int, dict[str, Any]]]:
    by_name: dict[str, tuple[int, dict[str, Any]]] = {}
    for index, surface in enumerate(surfaces):
        if isinstance(surface, dict) and isinstance(surface.get("surface"), str):
            by_name.setdefault(surface["surface"], (index, surface))
    return by_name


def check_reverse_outline(index: int, surface: dict[str, Any], base_path: Path, reporter: Reporter) -> None:
    path = f"required_surfaces[{index}]"
    if normalize_code(surface.get("status")) not in {"pass", "passed"}:
        reporter.error("reverse_outline_not_passed", f"{path}.status", "Reverse outline must be passed before closure.")
        return
    evidence_ref = surface.get("evidence_ref")
    if not evidence_ref_is_local_json(evidence_ref):
        reporter.error("surface_evidence_not_local_json", f"{path}.evidence_ref", "Reverse outline must point to local JSON evidence from the actual prose.")
        return
    evidence_path = resolve_evidence_path(base_path, str(evidence_ref))
    try:
        payload = load_json(evidence_path)
    except OSError as exc:
        reporter.error("surface_evidence_missing", f"{path}.evidence_ref", f"Cannot read reverse outline evidence {evidence_ref!r}: {exc}")
        return
    except json.JSONDecodeError as exc:
        reporter.error("surface_evidence_invalid_json", f"{path}.evidence_ref", f"Reverse outline evidence is invalid JSON at line {exc.lineno}, column {exc.colno}.")
        return
    report = validate_reverse_outline_evidence(payload, str(evidence_path))
    if report["passed"] is not True:
        reporter.error("surface_evidence_invalid", f"{path}.evidence_ref", f"Reverse outline did not pass: {summarize_child_issues(report)}.")


def check_final_prose(
    by_name: dict[str, tuple[int, dict[str, Any]]],
    base_path: Path,
    repository_root: str | Path | None,
    project_id: str,
    reporter: Reporter,
) -> dict[str, str] | None:
    for required in FINAL_PROSE_REQUIRED_SURFACES:
        if required not in by_name:
            reporter.error("missing_final_prose_surface", "required_surfaces", f"Final prose closure requires surface {required!r}.")
        elif normalize_code(by_name[required][1].get("status")) not in {"pass", "passed"}:
            reporter.error("final_prose_surface_not_passed", f"required_surfaces[{by_name[required][0]}].status", f"Final prose surface {required!r} must be passed.")
    manuscript_identity: dict[str, str] | None = None
    if "final_artifact" in by_name:
        index, surface = by_name["final_artifact"]
        try:
            manuscript_identity = evidence_identity.verify_content_reference(surface.get("evidence_ref"), base_path, repository_root)
        except evidence_identity.EvidenceIdentityError as exc:
            reporter.error(exc.code, f"required_surfaces[{index}].evidence_ref", exc.message)
    if "source_requirements" in by_name:
        index, surface = by_name["source_requirements"]
        opened = open_verified_json_surface(surface, index, base_path, repository_root, reporter)
        if opened is not None:
            payload, evidence_path, _ = opened
            validate_source_requirements(payload, evidence_path, repository_root, project_id, manuscript_identity, reporter)
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
    for field in ("schema_version", "project_id", "closure_id", "artifact_type", "prose_phase", "closure_level", "claim_boundary", "decision"):
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
    if level not in CLOSURE_LEVELS:
        reporter.error("invalid_closure_level", "closure_level", "Closure level must be chapter, volume, book, or series.")
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
    by_name = surfaces_by_name(surfaces)
    claims_final_prose = final_prose_claimed(route_decision)
    if "reverse_outline" in by_name:
        check_reverse_outline(*by_name["reverse_outline"], base_path, reporter)
    elif level in REVERSE_OUTLINE_LEVELS or claims_final_prose:
        reporter.error("missing_required_surface", "required_surfaces", f"Required surface 'reverse_outline' is missing for {level} closure.")
    manuscript_identity = None
    if claims_final_prose:
        manuscript_identity = check_final_prose(by_name, base_path, repository_root, str(payload.get("project_id", "")), reporter)
    if payload.get("decision") == "passed":
        if payload.get("blocking_items"):
            reporter.error("passed_with_blocking_items", "blocking_items", "Passed closure cannot include blocking items.")
        if payload.get("stale_items"):
            reporter.error("passed_with_stale_items", "stale_items", "Passed closure cannot include stale items.")
    return {
        "schema_version": "storyline-design.longform_closure_check.report.v1",
        "source_path": source_path,
        "passed": reporter.error_count == 0,
        "closure_level": level if isinstance(level, str) else "",
        "decision": str(payload.get("decision", "")),
        "route_decision": route_decision,
        "manuscript_identity": manuscript_identity,
        "summary": {"error_count": reporter.error_count, "issue_count": len(reporter.issues), "surface_count": len(surfaces), "final_prose_claimed": claims_final_prose},
        "issues": reporter.issues,
    }


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a long-form closure bundle: reverse outline and source requirements.")
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
