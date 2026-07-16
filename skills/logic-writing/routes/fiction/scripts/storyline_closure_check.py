#!/usr/bin/env python3
"""Aggregate StorylineDesign validation evidence into closure status.

This preserves child-check lineage and computes a deterministic closure result.
It does not replace ledger, turning-point, scene, promise/payoff, or WorldGuard
reports, and it does not judge prose style.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import guard_handoff_check
import storyline_route_check


UNIVERSAL_GUARD_SURFACES = [
    "flowguard_process",
    "traceguard_storyline",
    "worldguard_story_claims",
    "logicguard_theme_support",
    "sourceguard_canon_support",
]

ROUTE_SURFACE_TO_CLOSURE_SURFACE = {"story_ledger": "ledger"}
ROUTE_META_OR_SELF_SURFACES = {
    "target_artifact",
    "claim_boundary",
    "storyline_closure",
    "compact_closure",
    "longform_closure",
}

ALLOWED_CLOSURE_STATUSES = {"passed", "partial", "blocked", "downgraded"}
ALLOWED_CHECK_STATUSES = {
    "passed",
    "pass",
    "partial",
    "blocked",
    "failed",
    "fail",
    "error",
    "skipped",
    "stale",
    "downgraded",
    "human_review",
    "human-review",
    "not_run",
    "not_applicable_with_reason",
    "scoped_out",
    "unsupported",
}
GUARD_CONSUMABLE_STATUSES = {"passed", "not_applicable_with_reason", "scoped_out"}
PASSABLE_WORLDGUARD_STATUSES = {"pass", "passed", "scoped_out"}
NONPASS_WORLDGUARD_STATUSES = {
    "fail",
    "gap",
    "boundary_exceeded",
    "stale_source",
    "stale",
    "forbidden_use",
    "authority_cycle",
    "missing_handoff",
    "not_run",
    "unsupported",
    "human_review",
    "human-review",
}
PLACEHOLDER_VALUES = {
    "tbd",
    "todo",
    "n/a",
    "na",
    "none",
    "unknown",
    "placeholder",
    "fill later",
    "fix later",
    "...",
}

STATUS_RANK = {"passed": 0, "partial": 1, "downgraded": 2, "blocked": 3}
PROSE_ONLY_EVIDENCE_PREFIXES = ("review:", "ai:", "llm:", "self-report:", "model-answer:")
MODEL_EVIDENCE_SURFACES = set(UNIVERSAL_GUARD_SURFACES) | {
    "ledger",
    "turning_point",
    "scene_contract",
    "promise_payoff",
    "novel_ledger",
    "story_contribution",
    "chapter_interface",
    "prose_blueprint",
    "voice_style",
    "reverse_outline",
    "compact_story_movement",
    "main_promise_boundary",
    "worldguard",
}


class Reporter:
    def __init__(self) -> None:
        self.issues: list[dict[str, str]] = []

    def issue(self, severity: str, code: str, path: str, message: str, surface: str = "") -> None:
        issue = {
            "severity": severity,
            "code": code,
            "path": path,
            "message": message,
        }
        if surface:
            issue["surface"] = surface
        self.issues.append(issue)

    def error(self, code: str, path: str, message: str, surface: str = "") -> None:
        self.issue("error", code, path, message, surface)

    def warning(self, code: str, path: str, message: str, surface: str = "") -> None:
        self.issue("warning", code, path, message, surface)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue["severity"] == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue["severity"] == "warning")


def normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().lower().split())


def normalize_code(value: Any) -> str:
    return normalize_text(value).replace("-", "_").replace(" ", "_")


def is_blank_or_placeholder(value: Any) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return True
    if normalized in PLACEHOLDER_VALUES:
        return True
    if normalized.startswith("todo") or normalized.startswith("tbd"):
        return True
    if normalized.startswith("[") and normalized.endswith("]"):
        return True
    return False


def evidence_ref_is_prose_only(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = normalize_text(value)
    return normalized.startswith(PROSE_ONLY_EVIDENCE_PREFIXES)


def has_not_applicable_reason(check: dict[str, Any]) -> bool:
    explicit_reason = check.get("not_applicable_reason")
    if isinstance(explicit_reason, str) and not is_blank_or_placeholder(explicit_reason):
        return True
    for field in ("skip_reason", "reason", "next_action", "evidence_ref"):
        value = check.get(field)
        if isinstance(value, str) and not is_blank_or_placeholder(value):
            lowered = value.lower()
            if "reason" in lowered or "because" in lowered or "not applicable" in lowered or "no material" in lowered:
                return True
    return False


def combined_reason_text(row: dict[str, Any]) -> str:
    values = []
    for field in ("not_applicable_reason", "skip_reason", "reason", "next_action", "evidence_ref"):
        value = row.get(field)
        if isinstance(value, str):
            values.append(value)
    return normalize_text(" ".join(values))


def is_fiction_only_worldguard_scopeout(surface: str, check_status: str, row: dict[str, Any]) -> bool:
    if surface not in {"worldguard", "worldguard_story_claims"}:
        return False
    if check_status not in {"not_applicable_with_reason", "skipped"}:
        return False
    reason = combined_reason_text(row)
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


def escalate(current: str, candidate: str) -> str:
    return candidate if STATUS_RANK[candidate] > STATUS_RANK[current] else current


def required_surfaces_from_route(route_decision: dict[str, Any]) -> list[str]:
    surfaces = route_decision.get("required_surfaces")
    if not isinstance(surfaces, list):
        return []
    required: list[str] = []
    for surface in surfaces:
        if not isinstance(surface, str) or surface in ROUTE_META_OR_SELF_SURFACES:
            continue
        mapped = ROUTE_SURFACE_TO_CLOSURE_SURFACE.get(surface, surface)
        if mapped not in required:
            required.append(mapped)
    return required


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_path(base_path: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    candidate = base_path.parent / path
    if candidate.exists():
        return candidate
    return Path.cwd() / path


def load_child_report(base_path: Path, check: dict[str, Any], path: str, reporter: Reporter) -> dict[str, Any] | None:
    if isinstance(check.get("child_report"), dict):
        return check["child_report"]
    report_ref = check.get("report_path") or check.get("report_ref")
    if not isinstance(report_ref, str) or is_blank_or_placeholder(report_ref):
        return None
    report_path = resolve_path(base_path, report_ref)
    try:
        report = load_json(report_path)
    except OSError as exc:
        reporter.error("missing_child_report", f"{path}.report_path", f"Cannot read child report {report_ref!r}: {exc}", str(check.get("surface", "")))
        return None
    except json.JSONDecodeError as exc:
        reporter.error(
            "invalid_child_report_json",
            f"{path}.report_path",
            f"Child report {report_ref!r} is invalid JSON at line {exc.lineno}, column {exc.colno}.",
            str(check.get("surface", "")),
        )
        return None
    if not isinstance(report, dict):
        reporter.error("invalid_child_report_type", f"{path}.report_path", "Child report must be a JSON object.", str(check.get("surface", "")))
        return None
    return report


def check_bundle_shape(bundle: Any, reporter: Reporter) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        reporter.error("invalid_root_type", "$", "Closure evidence bundle must be a JSON object.")
        return {}
    checks = bundle.get("checks")
    if checks is None and isinstance(bundle.get("script_evidence"), list):
        bundle["checks"] = bundle["script_evidence"]
        checks = bundle["checks"]
    if not isinstance(checks, list):
        reporter.error("missing_required_field", "checks", "Closure bundle must include checks or script_evidence list.")
    for field in ("requested_artifact", "prose_phase", "claim_boundary"):
        if field not in bundle or is_blank_or_placeholder(bundle.get(field)):
            reporter.error("missing_required_field", field, f"Closure bundle must include non-empty {field}.")
    for list_field in ("unresolved_gaps", "deferred_or_downgraded_work", "next_actions"):
        if list_field in bundle and not isinstance(bundle[list_field], list):
            reporter.error("invalid_type", list_field, f"{list_field} must be a list.")
    return bundle


def normalized_check_status(check: dict[str, Any], report: dict[str, Any] | None) -> str:
    raw = normalize_code(check.get("status"))
    if raw in ALLOWED_CHECK_STATUSES:
        if raw == "pass":
            return "passed"
        if raw in {"fail", "failed", "error", "unsupported"}:
            return "blocked"
        return raw
    if report is not None and isinstance(report.get("passed"), bool):
        return "passed" if report["passed"] else "blocked"
    return "blocked"


def summarize_child_report(report: dict[str, Any] | None) -> dict[str, Any]:
    if report is None:
        return {}
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "schema_version": str(report.get("schema_version", "")),
        "passed": report.get("passed") if isinstance(report.get("passed"), bool) else None,
        "summary": summary,
        "source_path": str(report.get("source_path", "")),
        "collection_path": str(report.get("collection_path", "")),
    }


def check_required_surfaces(
    checks: list[Any],
    required_surfaces: list[str],
    reporter: Reporter,
) -> None:
    observed: set[str] = set()
    for item in checks:
        if isinstance(item, dict) and isinstance(item.get("surface"), str):
            observed.add(item["surface"])
    for surface in required_surfaces:
        if surface not in observed:
            reporter.error(
                "missing_required_surface",
                f"checks.{surface}",
                f"Required closure evidence surface {surface!r} is missing.",
                surface,
            )


def evaluate_check(
    base_path: Path,
    check: Any,
    index: int,
    reporter: Reporter,
    repository_root: str | Path | None = None,
) -> tuple[str, dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    path = f"checks[{index}]"
    if not isinstance(check, dict):
        reporter.error("invalid_check_type", path, "Check entry must be an object.")
        return "blocked", {}, [], [], []

    surface = str(check.get("surface", ""))
    status = "passed"
    gaps: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []

    for field in ("surface", "check_name", "evidence_ref"):
        if field not in check or is_blank_or_placeholder(check.get(field)):
            reporter.error("missing_required_field", f"{path}.{field}", f"Check entry must include {field}.", surface)
            status = "blocked"

    guard_report: dict[str, Any] | None = None
    is_guard_surface = surface in UNIVERSAL_GUARD_SURFACES
    if is_guard_surface and any(field in check for field in ("child_report", "report_path", "report_ref", "passed")):
        reporter.error(
            "guard_inline_report_forbidden",
            path,
            f"Guard surface {surface!r} must consume a content-addressed native terminal receipt, not an inline report or passed boolean.",
            surface,
        )
    report = None if is_guard_surface else load_child_report(base_path, check, path, reporter)
    check_status = normalized_check_status(check, report)

    if check_status == "passed" and surface in MODEL_EVIDENCE_SURFACES and evidence_ref_is_prose_only(check.get("evidence_ref")):
        reporter.error(
            "prose_only_evidence",
            f"{path}.evidence_ref",
            f"Required surface {surface!r} cannot be closed by prose-only review or AI self-report evidence.",
            surface,
        )
        check_status = "blocked"

    if check_status == "not_applicable_with_reason" and is_fiction_only_worldguard_scopeout(surface, check_status, check):
        reporter.error(
            "fictional_world_auto_scopeout",
            path,
            "WorldGuard cannot be marked not applicable merely because the story is fictional.",
            surface,
        )
        check_status = "blocked"

    if is_guard_surface and check_status in GUARD_CONSUMABLE_STATUSES:
        expected_input_fingerprint = check.get("input_fingerprint")
        missing_expected_input = not isinstance(expected_input_fingerprint, str) or not expected_input_fingerprint.strip()
        if missing_expected_input:
            reporter.error(
                "missing_guard_input_fingerprint",
                f"{path}.input_fingerprint",
                f"Guard surface {surface!r} must bind its handoff to the current expected input fingerprint.",
                surface,
            )
        guard_report = guard_handoff_check.validate_reference(
            check.get("evidence_ref"),
            str(base_path),
            surface,
            repository_root=repository_root,
            expected_input_fingerprint=expected_input_fingerprint if not missing_expected_input else None,
        )
        if guard_report.get("passed") is not True:
            for issue in guard_report.get("issues", []):
                if not isinstance(issue, dict):
                    continue
                child_path = str(issue.get("path", "$"))
                reporter.error(
                    str(issue.get("code", "guard_handoff_invalid")),
                    f"{path}.{child_path}",
                    str(issue.get("message", "Guard handoff validation failed.")),
                    surface,
                )
            check_status = "blocked"
        else:
            terminal_status = normalize_code(guard_report.get("handoff", {}).get("terminal_status"))
            if terminal_status != check_status:
                reporter.error(
                    "guard_terminal_status_mismatch",
                    f"{path}.status",
                    f"Closure status {check_status!r} does not match Guard terminal receipt status {terminal_status!r}.",
                    surface,
                )
                check_status = "blocked"
        if missing_expected_input:
            check_status = "blocked"

    if report is not None and report.get("passed") is False and check_status == "passed":
        reporter.error("child_report_failed", path, "Check status says passed but child report passed=false.", surface)
        check_status = "blocked"
    elif report is not None and report.get("passed") is False:
        check_status = "blocked" if check.get("required", True) else "partial"

    if check_status == "blocked":
        status = "blocked"
        gaps.append(
            {
                "surface": surface,
                "status": "blocked",
                "gap": str(check.get("gap") or "Required child check failed or is missing required evidence."),
                "blocks": str(check.get("blocks") or "closure"),
                "next_action": str(check.get("next_action") or f"rerun_or_repair_{surface}"),
                "evidence_ref": str(check.get("evidence_ref", "")),
            }
        )
    elif check_status == "not_applicable_with_reason":
        if check.get("blocks_closure") is True:
            reporter.error(
                "not_applicable_blocks_closure",
                f"{path}.blocks_closure",
                f"Surface {surface!r} cannot be both not_applicable_with_reason and blocks_closure=true.",
                surface,
            )
            status = "blocked"
        if not has_not_applicable_reason(check):
            reporter.error(
                "missing_not_applicable_reason",
                path,
                f"Surface {surface!r} is marked not_applicable_with_reason but does not state the reason.",
                surface,
            )
            status = "blocked"
    elif check_status == "downgraded":
        status = "downgraded"
    elif check_status in {"partial", "skipped", "stale", "not_run", "human_review", "human-review"}:
        status = "partial"

    if check.get("stale") is True or check_status == "stale":
        status = escalate(status, "partial")
        stale.append(
            {
                "surface": surface,
                "evidence_ref": str(check.get("evidence_ref", "")),
                "reason": str(check.get("stale_reason") or "Evidence is stale."),
                "next_action": str(check.get("next_action") or f"refresh_{surface}_evidence"),
            }
        )

    raw_skipped = check.get("skipped_checks")
    if check_status == "skipped" or (isinstance(raw_skipped, list) and raw_skipped):
        status = escalate(status, "partial")
        skipped.append(
            {
                "surface": surface,
                "evidence_ref": str(check.get("evidence_ref", "")),
                "skipped_checks": raw_skipped if isinstance(raw_skipped, list) else [str(check.get("check_name", surface))],
                "reason": str(check.get("skip_reason") or "Check was skipped."),
            }
        )

    evidence = {
        "surface": surface,
        "check_name": str(check.get("check_name", "")),
        "status": check_status,
        "required": bool(check.get("required", True)),
        "evidence_ref": str(check.get("evidence_ref", "")),
        "report_path": str(check.get("report_path", "")),
        "child_report": summarize_child_report(report),
        "guard_handoff": guard_report.get("handoff", {}) if isinstance(guard_report, dict) else {},
        "guard_terminal_receipt": guard_report.get("terminal_receipt", {}) if isinstance(guard_report, dict) else {},
    }
    return status, evidence, gaps, skipped, stale


def evaluate_unresolved_gaps(items: Any) -> tuple[str, list[dict[str, Any]]]:
    if not isinstance(items, list):
        return "passed", []
    status = "passed"
    gaps: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            status = escalate(status, "partial")
            gaps.append({"surface": "unknown", "status": "partial", "gap": "Malformed unresolved gap entry.", "next_action": "repair_closure_report"})
            continue
        item_status = normalize_code(item.get("status"))
        blocking = item.get("blocking") is True or bool(item.get("blocks"))
        if item_status in {"blocked", "fail", "failed", "unsupported", "human_review", "human-review"} and blocking:
            status = escalate(status, "blocked")
        elif item_status == "downgraded":
            status = escalate(status, "downgraded")
        else:
            status = escalate(status, "partial")
        gaps.append(
            {
                "surface": str(item.get("surface", "unknown")),
                "status": str(item.get("status", "partial")),
                "gap": str(item.get("gap") or item.get("reason") or "Unresolved gap declared."),
                "blocks": str(item.get("blocks", "")),
                "next_action": str(item.get("next_action") or "repair_or_scope_gap"),
            }
        )
    return status, gaps


def evaluate_downgrades(bundle: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    items = bundle.get("deferred_or_downgraded_work")
    downgraded: list[dict[str, Any]] = []
    status = "passed"
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                downgraded.append(
                    {
                        "surface": str(item.get("surface", "unknown")),
                        "downgrade_from": str(item.get("downgrade_from", "")),
                        "downgrade_to": str(item.get("downgrade_to", "")),
                        "reason": str(item.get("reason") or "Work was downgraded or deferred."),
                    }
                )
            else:
                downgraded.append({"surface": "unknown", "downgrade_from": "", "downgrade_to": "", "reason": str(item)})
        if downgraded:
            status = "downgraded"

    requested = bundle.get("requested_artifact")
    delivered = bundle.get("delivered_artifact") or bundle.get("supported_artifact")
    if isinstance(requested, str) and isinstance(delivered, str) and delivered and requested != delivered:
        status = "downgraded"
        downgraded.append(
            {
                "surface": "closure",
                "downgrade_from": requested,
                "downgrade_to": delivered,
                "reason": "Delivered artifact differs from requested artifact.",
            }
        )
    return status, downgraded


def evaluate_worldguard_claims(items: Any) -> tuple[str, list[dict[str, Any]]]:
    if not isinstance(items, list):
        return "passed", []
    status = "passed"
    gaps: list[dict[str, Any]] = []
    for index, claim in enumerate(items):
        if not isinstance(claim, dict):
            status = escalate(status, "partial")
            gaps.append(
                {
                    "surface": "worldguard_story_claims",
                    "status": "partial",
                    "gap": f"Malformed worldguard_claims[{index}] entry.",
                    "next_action": "repair_worldguard_claim_row",
                }
            )
            continue
        claim_status = normalize_code(claim.get("worldguard_status") or claim.get("status"))
        closure_effect = normalize_code(claim.get("closure_effect"))
        if claim_status in PASSABLE_WORLDGUARD_STATUSES or closure_effect == "scoped_out":
            continue
        if claim_status in NONPASS_WORLDGUARD_STATUSES or not claim_status:
            if claim.get("blocking") is True or closure_effect not in {"scoped_out", "continue"}:
                status = escalate(status, "partial")
            gaps.append(
                {
                    "surface": "worldguard_story_claims",
                    "status": claim_status or "missing_status",
                    "gap": f"WorldGuard claim {claim.get('id', index)!r} is not pass or scoped_out.",
                    "blocks": str(claim.get("blocks", "")),
                    "next_action": str(claim.get("next_action") or "return_to_worldguard_or_scope_out_claim"),
                }
            )
    return status, gaps


def validate_closure(
    bundle: Any,
    source_path: str,
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    reporter = Reporter()
    checked_bundle = check_bundle_shape(bundle, reporter)
    base_path = Path(source_path)
    checks = checked_bundle.get("checks") if isinstance(checked_bundle.get("checks"), list) else []
    route_decision: dict[str, Any] | None = None
    try:
        route_decision = storyline_route_check.compile_route_decision(
            {
                "artifact_type": checked_bundle.get("requested_artifact"),
                "prose_phase": checked_bundle.get("prose_phase"),
            }
        )
    except storyline_route_check.RouteBlocked as exc:
        reporter.error(exc.code, exc.field or "route_decision", exc.message, "route")
    required_surfaces = required_surfaces_from_route(route_decision) if route_decision is not None else []
    check_required_surfaces(checks, required_surfaces, reporter)

    closure_status = "passed"
    completed_evidence: list[dict[str, Any]] = []
    unresolved_gaps: list[dict[str, Any]] = []
    skipped_checks: list[dict[str, Any]] = []
    stale_evidence: list[dict[str, Any]] = []

    for index, check in enumerate(checks):
        check_status, evidence, gaps, skipped, stale = evaluate_check(
            base_path,
            check,
            index,
            reporter,
            repository_root=repository_root,
        )
        closure_status = escalate(closure_status, check_status)
        if evidence:
            completed_evidence.append(evidence)
        unresolved_gaps.extend(gaps)
        skipped_checks.extend(skipped)
        stale_evidence.extend(stale)

    gap_status, declared_gaps = evaluate_unresolved_gaps(checked_bundle.get("unresolved_gaps"))
    closure_status = escalate(closure_status, gap_status)
    unresolved_gaps.extend(declared_gaps)

    downgrade_status, downgraded_work = evaluate_downgrades(checked_bundle)
    closure_status = escalate(closure_status, downgrade_status)

    wg_status, wg_gaps = evaluate_worldguard_claims(checked_bundle.get("worldguard_claims"))
    closure_status = escalate(closure_status, wg_status)
    unresolved_gaps.extend(wg_gaps)

    if reporter.error_count:
        closure_status = "blocked"

    limitations = checked_bundle.get("limitations") if isinstance(checked_bundle.get("limitations"), list) else []
    next_actions = checked_bundle.get("next_actions") if isinstance(checked_bundle.get("next_actions"), list) else []
    if closure_status != "passed" and not next_actions:
        next_actions = ["Repair or scope unresolved closure gaps, then rerun closure aggregation."]

    return {
        "schema_version": "storyline-design.storyline_closure_check.report.v1",
        "source_path": source_path,
        "passed": closure_status == "passed",
        "closure_status": closure_status,
        "requested_artifact": str(checked_bundle.get("requested_artifact", "")),
        "prose_phase": str(checked_bundle.get("prose_phase", "")),
        "route_decision": route_decision,
        "required_surfaces": required_surfaces,
        "claim_boundary": str(checked_bundle.get("claim_boundary", "")),
        "summary": {
            "error_count": reporter.error_count,
            "warning_count": reporter.warning_count,
            "issue_count": len(reporter.issues),
            "check_count": len(checks),
            "completed_evidence_count": len(completed_evidence),
            "unresolved_gap_count": len(unresolved_gaps),
            "skipped_check_count": len(skipped_checks),
            "stale_evidence_count": len(stale_evidence),
            "downgraded_work_count": len(downgraded_work),
        },
        "completed_evidence": completed_evidence,
        "unresolved_gaps": unresolved_gaps,
        "deferred_or_downgraded_work": downgraded_work,
        "skipped_checks": skipped_checks,
        "stale_evidence": stale_evidence,
        "limitations": [str(item) for item in limitations],
        "next_actions": [str(item) for item in next_actions],
        "issues": reporter.issues,
    }


def error_report(source_path: str, code: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": "storyline-design.storyline_closure_check.report.v1",
        "source_path": source_path,
        "passed": False,
        "closure_status": "blocked",
        "requested_artifact": "",
        "claim_boundary": "",
        "summary": {
            "error_count": 1,
            "warning_count": 0,
            "issue_count": 1,
            "check_count": 0,
            "completed_evidence_count": 0,
            "unresolved_gap_count": 1,
            "skipped_check_count": 0,
            "stale_evidence_count": 0,
            "downgraded_work_count": 0,
        },
        "completed_evidence": [],
        "unresolved_gaps": [
            {
                "surface": "closure",
                "status": "blocked",
                "gap": message,
                "blocks": "closure",
                "next_action": "repair_closure_input",
            }
        ],
        "deferred_or_downgraded_work": [],
        "skipped_checks": [],
        "stale_evidence": [],
        "limitations": [],
        "next_actions": ["Repair closure input and rerun storyline_closure_check.py."],
        "issues": [
            {
                "severity": "error",
                "code": code,
                "path": source_path,
                "message": message,
                "surface": "closure",
            }
        ],
    }


def print_text_report(report: dict[str, Any]) -> None:
    print(f"Storyline closure check: {report['closure_status']}")
    print(f"Source: {report['source_path']}")
    print(f"Requested artifact: {report['requested_artifact']}")
    print(f"Claim boundary: {report['claim_boundary']}")
    print(
        "Evidence: "
        f"{report['summary']['completed_evidence_count']} completed, "
        f"{report['summary']['unresolved_gap_count']} unresolved gap(s), "
        f"{report['summary']['downgraded_work_count']} downgrade(s)"
    )
    for issue in report["issues"]:
        surface_suffix = f" surface={issue['surface']}" if "surface" in issue else ""
        print(f"- [{issue['severity']}] {issue['code']} at {issue['path']}{surface_suffix}: {issue['message']}")
    for gap in report["unresolved_gaps"]:
        print(f"- [gap] {gap['surface']} {gap['status']}: {gap['gap']} -> {gap['next_action']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggregate StorylineDesign evidence into a closure status.")
    parser.add_argument("input", help="Path to a closure evidence bundle JSON file.")
    parser.add_argument(
        "--repository-root",
        default="",
        help="Explicit containment root for content-addressed Guard evidence (required in installed layouts without .git).",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON report.")
    args = parser.parse_args(argv)

    path = Path(args.input)
    try:
        payload = load_json(path)
    except OSError as exc:
        report = error_report(str(path), "read_error", str(exc))
    except json.JSONDecodeError as exc:
        report = error_report(str(path), "json_decode_error", f"{exc.msg} at line {exc.lineno}, column {exc.colno}")
    else:
        report = validate_closure(
            payload,
            str(path),
            repository_root=args.repository_root or None,
        )

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text_report(report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
