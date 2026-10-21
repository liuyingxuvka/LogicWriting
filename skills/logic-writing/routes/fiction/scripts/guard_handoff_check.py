#!/usr/bin/env python3
"""Validate content-addressed handoffs to Guard-owned terminal receipts.

Storyline Design verifies receipt identity and current input binding only.  It
does not execute a Guard or reinterpret any Guard-owned domain conclusion.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from evidence_identity import (
    EvidenceIdentityError,
    parse_sha256_value,
    repository_root_for,
    verify_content_reference,
)


HANDOFF_SCHEMA_VERSION = "storyline-design.guard_handoff.v1"
REPORT_SCHEMA_VERSION = "storyline-design.guard_handoff_check.report.v1"
TERMINAL_STATUSES = {"passed", "not_applicable_with_reason", "scoped_out"}
EXPECTED_GUARD_BY_SURFACE = {
    "flowguard_process": "flowguard",
    "traceguard_storyline": "traceguard",
    "worldguard_story_claims": "worldguard",
    "logicguard_theme_support": "logicguard",
    "sourceguard_canon_support": "sourceguard",
}
IDENTITY_FIELDS = {
    "surface": "surface",
    "guard_id": "guard_id",
    "native_owner": "native_owner",
    "native_route_id": "route_id",
    "native_check_id": "check_id",
    "tool_version": "tool_version",
    "input_fingerprint": "input_fingerprint",
    "terminal_receipt_id": "receipt_id",
    "terminal_status": "status",
    "claim_boundary": "claim_boundary",
}


class Reporter:
    def __init__(self) -> None:
        self.issues: list[dict[str, str]] = []

    def error(self, code: str, path: str, message: str) -> None:
        self.issues.append({"severity": "error", "code": code, "path": path, "message": message})

    def identity_error(self, exc: EvidenceIdentityError, *, prefix: str, path: str) -> None:
        self.error(f"{prefix}_{exc.code}", path, exc.message)

    @property
    def error_count(self) -> int:
        return len(self.issues)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _normalize(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _owner_matches_guard(owner: Any, guard_id: str) -> bool:
    if not isinstance(owner, str):
        return False
    normalized_owner = owner.strip().lower()
    return normalized_owner == guard_id or any(
        normalized_owner.startswith(f"{guard_id}{separator}") for separator in ("-", "_", ".", ":", "/")
    )


def _load_json(path: Path, reporter: Reporter, *, code_prefix: str, field_path: str) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        reporter.error(f"{code_prefix}_read_error", field_path, f"Cannot read {path}: {exc}")
    except json.JSONDecodeError as exc:
        reporter.error(
            f"{code_prefix}_invalid_json",
            field_path,
            f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
        )
    return None


def _identity_report(
    *,
    source_path: str,
    expected_surface: str | None,
    reporter: Reporter,
    handoff: dict[str, Any] | None = None,
    receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    handoff = handoff or {}
    receipt = receipt or {}
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "source_path": source_path,
        "passed": reporter.error_count == 0,
        "expected_surface": expected_surface or "",
        "summary": {
            "error_count": reporter.error_count,
            "issue_count": len(reporter.issues),
            "handoff_checked": bool(handoff),
            "terminal_receipt_checked": bool(receipt),
        },
        "handoff": {
            "schema_version": str(handoff.get("schema_version", "")),
            "surface": str(handoff.get("surface", "")),
            "guard_id": str(handoff.get("guard_id", "")),
            "native_owner": str(handoff.get("native_owner", "")),
            "native_route_id": str(handoff.get("native_route_id", "")),
            "native_check_id": str(handoff.get("native_check_id", "")),
            "tool_version": str(handoff.get("tool_version", "")),
            "input_fingerprint": str(handoff.get("input_fingerprint", "")),
            "terminal_receipt_id": str(handoff.get("terminal_receipt_id", "")),
            "terminal_status": str(handoff.get("terminal_status", "")),
            "claim_boundary": str(handoff.get("claim_boundary", "")),
        },
        "terminal_receipt": {
            "schema_version": str(receipt.get("schema_version", "")),
            "receipt_id": str(receipt.get("receipt_id", "")),
            "guard_id": str(receipt.get("guard_id", "")),
            "native_owner": str(receipt.get("native_owner", "")),
            "route_id": str(receipt.get("route_id", "")),
            "check_id": str(receipt.get("check_id", "")),
            "tool_version": str(receipt.get("tool_version", "")),
            "input_fingerprint": str(receipt.get("input_fingerprint", "")),
            "status": str(receipt.get("status", "")),
            "freshness": str(receipt.get("freshness", "")),
            "claim_boundary": str(receipt.get("claim_boundary", "")),
        },
        "issues": reporter.issues,
        "claim_boundary": (
            "Validates a content-addressed Guard handoff and terminal receipt identity. "
            "It does not execute the Guard or re-evaluate Guard-owned domain logic."
        ),
    }


def validate(
    payload: Any,
    source_path: str,
    repository_root: str | Path | None = None,
    expected_surface: str | None = None,
    expected_input_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Validate one already-opened handoff and its referenced terminal receipt."""

    reporter = Reporter()
    if not isinstance(payload, dict):
        reporter.error("invalid_root_type", "$", "Guard handoff must be a JSON object.")
        return _identity_report(source_path=source_path, expected_surface=expected_surface, reporter=reporter)

    if "passed" in payload:
        reporter.error(
            "embedded_pass_boolean_forbidden",
            "passed",
            "Guard handoffs must consume terminal status from the native receipt, not embed a passed boolean.",
        )
    if payload.get("schema_version") != HANDOFF_SCHEMA_VERSION:
        reporter.error("invalid_schema_version", "schema_version", f"Expected {HANDOFF_SCHEMA_VERSION}.")

    required_fields = (
        "surface",
        "guard_id",
        "native_owner",
        "native_route_id",
        "native_check_id",
        "tool_version",
        "receipt_schema_version",
        "input_fingerprint",
        "terminal_receipt_id",
        "terminal_receipt_ref",
        "terminal_status",
        "claim_boundary",
    )
    for field in required_fields:
        if not _nonempty(payload.get(field)):
            reporter.error("missing_required_field", field, f"Guard handoff requires non-empty {field}.")

    surface = str(payload.get("surface", ""))
    guard_id = str(payload.get("guard_id", "")).strip().lower()
    expected_guard = EXPECTED_GUARD_BY_SURFACE.get(surface)
    if expected_guard is None:
        reporter.error("unknown_guard_surface", "surface", f"Unknown Guard handoff surface {surface!r}.")
    elif guard_id != expected_guard:
        reporter.error(
            "guard_surface_owner_mismatch",
            "guard_id",
            f"Surface {surface!r} is owned by {expected_guard!r}, not {guard_id!r}.",
        )
    if expected_surface is not None and surface != expected_surface:
        reporter.error(
            "guard_surface_mismatch",
            "surface",
            f"Expected handoff surface {expected_surface!r}, observed {surface!r}.",
        )
    if expected_guard and not _owner_matches_guard(payload.get("native_owner"), expected_guard):
        reporter.error(
            "guard_native_owner_mismatch",
            "native_owner",
            f"Native owner {payload.get('native_owner')!r} does not belong to {expected_guard!r}.",
        )

    terminal_status = _normalize(payload.get("terminal_status"))
    if terminal_status not in TERMINAL_STATUSES:
        reporter.error(
            "guard_terminal_status_not_consumable",
            "terminal_status",
            f"Terminal status must be one of {sorted(TERMINAL_STATUSES)}.",
        )

    input_fingerprint = ""
    try:
        input_fingerprint = parse_sha256_value(payload.get("input_fingerprint"), path="input_fingerprint")
    except EvidenceIdentityError as exc:
        reporter.error("invalid_guard_input_fingerprint", exc.path, exc.message)
    if expected_input_fingerprint is not None:
        try:
            expected_digest = parse_sha256_value(expected_input_fingerprint, path="expected_input_fingerprint")
        except EvidenceIdentityError as exc:
            reporter.error("invalid_expected_input_fingerprint", exc.path, exc.message)
        else:
            if input_fingerprint and input_fingerprint != expected_digest:
                reporter.error(
                    "guard_input_fingerprint_mismatch",
                    "input_fingerprint",
                    "Guard handoff input fingerprint does not match the closure owner's current expected input.",
                )

    try:
        root = repository_root_for(source_path, repository_root)
    except EvidenceIdentityError as exc:
        reporter.identity_error(exc, prefix="guard_receipt", path="terminal_receipt_ref")
        return _identity_report(
            source_path=source_path,
            expected_surface=expected_surface,
            reporter=reporter,
            handoff=payload,
        )

    receipt_identity: dict[str, str] | None = None
    try:
        receipt_identity = verify_content_reference(payload.get("terminal_receipt_ref"), source_path, root)
    except EvidenceIdentityError as exc:
        reporter.identity_error(exc, prefix="guard_receipt", path="terminal_receipt_ref")

    receipt: Any = None
    if receipt_identity is not None:
        receipt_path = root / receipt_identity["repository_path"]
        receipt = _load_json(receipt_path, reporter, code_prefix="guard_receipt", field_path="terminal_receipt_ref")
    if receipt is not None and not isinstance(receipt, dict):
        reporter.error("guard_receipt_invalid_root_type", "terminal_receipt_ref", "Terminal receipt must be a JSON object.")
        receipt = None

    if isinstance(receipt, dict):
        if "passed" in receipt:
            reporter.error(
                "embedded_pass_boolean_forbidden",
                "terminal_receipt_ref.passed",
                "Terminal receipt must expose native terminal status, not an embedded passed boolean.",
            )
        receipt_schema = str(receipt.get("schema_version", ""))
        if receipt_schema != payload.get("receipt_schema_version"):
            reporter.error(
                "guard_receipt_schema_mismatch",
                "receipt_schema_version",
                "Handoff receipt_schema_version does not match the referenced receipt.",
            )
        if expected_guard and not receipt_schema.startswith(f"{expected_guard}."):
            reporter.error(
                "guard_receipt_schema_owner_mismatch",
                "receipt_schema_version",
                f"Receipt schema {receipt_schema!r} is not owned by {expected_guard!r}.",
            )
        for handoff_field, receipt_field in IDENTITY_FIELDS.items():
            if payload.get(handoff_field) != receipt.get(receipt_field):
                reporter.error(
                    f"guard_receipt_{receipt_field}_mismatch",
                    f"terminal_receipt_ref.{receipt_field}",
                    f"Receipt {receipt_field} does not match handoff {handoff_field}.",
                )
        if receipt.get("terminal") is not True:
            reporter.error("guard_receipt_not_terminal", "terminal_receipt_ref.terminal", "Receipt must declare terminal=true.")
        if receipt.get("immutable") is not True:
            reporter.error("guard_receipt_not_immutable", "terminal_receipt_ref.immutable", "Receipt must declare immutable=true.")
        if receipt.get("freshness") != "current":
            reporter.error("guard_receipt_stale", "terminal_receipt_ref.freshness", "Receipt freshness must be current.")
        if _normalize(receipt.get("status")) not in TERMINAL_STATUSES:
            reporter.error(
                "guard_receipt_status_not_consumable",
                "terminal_receipt_ref.status",
                f"Receipt status must be one of {sorted(TERMINAL_STATUSES)}.",
            )

    return _identity_report(
        source_path=source_path,
        expected_surface=expected_surface,
        reporter=reporter,
        handoff=payload,
        receipt=receipt if isinstance(receipt, dict) else None,
    )


def validate_reference(
    reference: Any,
    source_path: str,
    expected_surface: str,
    repository_root: str | Path | None = None,
    expected_input_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Open a content-addressed handoff, then validate its native receipt."""

    reporter = Reporter()
    try:
        root = repository_root_for(source_path, repository_root)
    except EvidenceIdentityError as exc:
        reporter.identity_error(exc, prefix="guard_handoff", path="evidence_ref")
        return _identity_report(source_path=source_path, expected_surface=expected_surface, reporter=reporter)
    try:
        identity = verify_content_reference(reference, source_path, root)
    except EvidenceIdentityError as exc:
        reporter.identity_error(exc, prefix="guard_handoff", path="evidence_ref")
        return _identity_report(source_path=source_path, expected_surface=expected_surface, reporter=reporter)

    handoff_path = root / identity["repository_path"]
    payload = _load_json(handoff_path, reporter, code_prefix="guard_handoff", field_path="evidence_ref")
    if payload is None:
        return _identity_report(source_path=str(handoff_path), expected_surface=expected_surface, reporter=reporter)
    report = validate(
        payload,
        str(handoff_path),
        repository_root=root,
        expected_surface=expected_surface,
        expected_input_fingerprint=expected_input_fingerprint,
    )
    report["handoff_reference"] = identity
    return report


def _load_input(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a Guard handoff and its immutable terminal receipt.")
    parser.add_argument("input", help="Path to the Guard handoff JSON file.")
    parser.add_argument("--expected-surface", default="")
    parser.add_argument("--expected-input-fingerprint", default="")
    parser.add_argument("--repository-root", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    input_path = Path(args.input).expanduser()
    try:
        payload = _load_input(input_path)
    except OSError as exc:
        reporter = Reporter()
        reporter.error("read_error", str(input_path), str(exc))
        report = _identity_report(
            source_path=str(input_path),
            expected_surface=args.expected_surface or None,
            reporter=reporter,
        )
    except json.JSONDecodeError as exc:
        reporter = Reporter()
        reporter.error("json_decode_error", str(input_path), f"{exc.msg} at line {exc.lineno}, column {exc.colno}")
        report = _identity_report(
            source_path=str(input_path),
            expected_surface=args.expected_surface or None,
            reporter=reporter,
        )
    else:
        report = validate(
            payload,
            str(input_path),
            repository_root=args.repository_root or None,
            expected_surface=args.expected_surface or None,
            expected_input_fingerprint=args.expected_input_fingerprint or None,
        )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Guard handoff check: {'passed' if report['passed'] else 'failed'}")
        for issue in report["issues"]:
            print(f"- [{issue['severity']}] {issue['code']} at {issue['path']}: {issue['message']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
