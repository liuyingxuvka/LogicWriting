#!/usr/bin/env python3
"""Validate Longform Mode chapter interfaces, prose blueprints, and reverse outlines."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import storyline_route_check


PASS_STATUSES = {"pass", "passed"}
BAD_BRIDGES = {"", "tbd", "todo", "n/a", "na", "unknown", "placeholder", "continues the story", "sets up the next chapter", "next chapter continues", "..."}
HOOK_ROLES = {"none", "setup", "pressure_forward", "cliffhanger", "quiet_bridge", "payoff_delay", "volume_hook"}


class Reporter:
    def __init__(self) -> None:
        self.issues: list[dict[str, str]] = []

    def error(self, code: str, path: str, message: str) -> None:
        self.issues.append({"severity": "error", "code": code, "path": path, "message": message})

    @property
    def error_count(self) -> int:
        return len(self.issues)


def norm(value: Any) -> str:
    return " ".join(value.strip().lower().split()) if isinstance(value, str) else ""


def blank(value: Any) -> bool:
    return norm(value) in BAD_BRIDGES


def collection(payload: Any, key: str) -> list[Any]:
    if isinstance(payload, dict) and isinstance(payload.get(key), list):
        return payload[key]
    if isinstance(payload, dict) and isinstance(payload.get("chapter_interface_bundle"), dict) and isinstance(payload["chapter_interface_bundle"].get(key), list):
        return payload["chapter_interface_bundle"][key]
    return []


def check_list(value: Any, path: str, reporter: Reporter) -> None:
    if not isinstance(value, list):
        reporter.error("invalid_type", path, "Expected list.")
    elif not value:
        reporter.error("empty_required_list", path, "Required list is empty.")


def check_interface(item: Any, path: str, reporter: Reporter) -> str:
    if not isinstance(item, dict):
        reporter.error("invalid_row_type", path, "Chapter interface must be an object.")
        return ""
    required_str = ["id", "chapter_id", "previous_chapter_id", "next_chapter_id", "previous_output", "current_input", "hook_role", "status"]
    required_lists = ["reader_state_before", "reader_state_after", "unresolved_tension_in", "unresolved_tension_out", "promise_movements", "arc_movements", "evidence_refs"]
    for field in required_str:
        value = item.get(field)
        if not isinstance(value, str):
            reporter.error("missing_required_field", f"{path}.{field}", "Required string field is missing.")
        elif blank(value) and field in {"previous_output", "current_input"}:
            reporter.error("fake_or_missing_handoff", f"{path}.{field}", "Adjacent chapter handoff must be concrete, not generic placeholder text.")
        elif not value.strip():
            reporter.error("empty_required_field", f"{path}.{field}", "Required string field is empty.")
    for field in required_lists:
        check_list(item.get(field), f"{path}.{field}", reporter)
    if isinstance(item.get("hook_role"), str) and item["hook_role"] not in HOOK_ROLES:
        reporter.error("invalid_hook_role", f"{path}.hook_role", f"Unknown hook role {item['hook_role']!r}.")
    if item.get("status") not in PASS_STATUSES:
        reporter.error("interface_not_passed", f"{path}.status", "Chapter interface must pass for positive validation.")
    return item.get("chapter_id", "") if isinstance(item.get("chapter_id"), str) else ""


def check_blueprints(items: list[Any], chapter_ids: set[str], reporter: Reporter) -> None:
    if not items:
        reporter.error("missing_blueprints", "prose_blueprints", "At least one prose blueprint is required.")
        return
    for index, item in enumerate(items):
        path = f"prose_blueprints[{index}]"
        if not isinstance(item, dict):
            reporter.error("invalid_row_type", path, "Blueprint must be an object.")
            continue
        for field in ("id", "chapter_id", "source_interface_id", "prose_scope", "pov", "tense", "status"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                reporter.error("missing_required_field", f"{path}.{field}", "Required blueprint field is missing.")
        for field in ("scene_order", "required_reader_experience", "must_include", "must_not_include", "voice_style_refs"):
            check_list(item.get(field), f"{path}.{field}", reporter)
        if item.get("chapter_id") not in chapter_ids:
            reporter.error("blueprint_without_interface", f"{path}.chapter_id", "Blueprint chapter_id has no matching chapter interface.")
        if item.get("status") not in PASS_STATUSES:
            reporter.error("blueprint_not_passed", f"{path}.status", "Blueprint must pass for positive validation.")


def check_reverse_outlines(items: list[Any], chapter_ids: set[str], reporter: Reporter) -> None:
    if not items:
        reporter.error("missing_reverse_outlines", "reverse_outlines", "Reverse outline evidence is required when chapter prose can be closed.")
        return
    for index, item in enumerate(items):
        path = f"reverse_outlines[{index}]"
        if not isinstance(item, dict):
            reporter.error("invalid_row_type", path, "Reverse outline must be an object.")
            continue
        for field in ("id", "chapter_id", "source_draft_ref", "model_alignment", "status"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                reporter.error("missing_required_field", f"{path}.{field}", "Required reverse-outline field is missing.")
        for field in ("observed_events", "observed_reader_state_after", "observed_promise_movements", "observed_arc_movements", "drift"):
            if not isinstance(item.get(field), list):
                reporter.error("invalid_type", f"{path}.{field}", "Expected list.")
        if "model_prose_binding_refs" in item and not isinstance(item.get("model_prose_binding_refs"), list):
            reporter.error("invalid_type", f"{path}.model_prose_binding_refs", "Expected list.")
        if "binding_drift" in item:
            if not isinstance(item.get("binding_drift"), list):
                reporter.error("invalid_type", f"{path}.binding_drift", "Expected list.")
            elif item.get("binding_drift"):
                reporter.error("unresolved_binding_drift", f"{path}.binding_drift", "Reverse outline binding drift must be resolved before positive validation.")
        if item.get("chapter_id") not in chapter_ids:
            reporter.error("reverse_outline_without_interface", f"{path}.chapter_id", "Reverse outline chapter_id has no matching chapter interface.")
        if item.get("model_alignment") not in PASS_STATUSES or item.get("status") not in PASS_STATUSES:
            reporter.error("reverse_outline_not_passed", f"{path}.status", "Reverse outline must align with the model.")


def validate(payload: Any, source_path: str) -> dict[str, Any]:
    reporter = Reporter()
    route_decision: dict[str, Any] | None = None
    if not isinstance(payload, dict):
        reporter.error("invalid_root_type", "$", "Current chapter-interface evidence must be one object.")
        payload = {}
    if payload.get("schema_version") != "storyline-design.chapter_interfaces.v2":
        reporter.error("invalid_schema_version", "schema_version", "Expected storyline-design.chapter_interfaces.v2.")
    for field in ("project_id", "model_revision"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            reporter.error("missing_required_field", field, "Current project identity field is required.")
    try:
        route_decision = storyline_route_check.compile_route_decision(payload)
    except storyline_route_check.RouteBlocked as exc:
        reporter.error(exc.code, exc.field or "route_decision", exc.message)
    if route_decision is not None and route_decision.get("route_id") != "route:longform":
        reporter.error("route_not_longform", "artifact_type", "Chapter-interface bundles require the canonical longform route.")
    interfaces = collection(payload, "chapter_interfaces")
    blueprints = collection(payload, "prose_blueprints")
    outlines = collection(payload, "reverse_outlines")
    chapter_ids: set[str] = set()
    if not interfaces:
        reporter.error("missing_chapter_interfaces", "chapter_interfaces", "At least one chapter interface is required.")
    for index, item in enumerate(interfaces):
        chapter_id = check_interface(item, f"chapter_interfaces[{index}]", reporter)
        if chapter_id:
            chapter_ids.add(chapter_id)
    check_blueprints(blueprints, chapter_ids, reporter)
    if route_decision is not None and route_decision.get("prose_phase") in {"post_draft", "final_prose"}:
        check_reverse_outlines(outlines, chapter_ids, reporter)
    elif outlines:
        check_reverse_outlines(outlines, chapter_ids, reporter)
    return {
        "schema_version": "storyline-design.chapter_interface_check.report.v1",
        "source_path": source_path,
        "project_id": payload.get("project_id", ""),
        "model_revision": payload.get("model_revision", ""),
        "route_decision": route_decision,
        "passed": reporter.error_count == 0,
        "summary": {"error_count": reporter.error_count, "issue_count": len(reporter.issues), "interface_count": len(interfaces), "blueprint_count": len(blueprints), "reverse_outline_count": len(outlines)},
        "issues": reporter.issues,
    }


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate chapter interface and prose blueprint evidence.")
    parser.add_argument("input")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = load_json(Path(args.input))
    except OSError as exc:
        payload = {}
        report = validate(payload, args.input)
        report["issues"].append({"severity": "error", "code": "read_error", "path": args.input, "message": str(exc)})
        report["summary"]["error_count"] += 1
        report["passed"] = False
    except json.JSONDecodeError as exc:
        payload = {}
        report = validate(payload, args.input)
        report["issues"].append({"severity": "error", "code": "json_decode_error", "path": args.input, "message": f"{exc.msg} at line {exc.lineno}, column {exc.colno}"})
        report["summary"]["error_count"] += 1
        report["passed"] = False
    else:
        report = validate(payload, args.input)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Chapter interface check: {'passed' if report['passed'] else 'failed'}")
        for issue in report["issues"]:
            print(f"- [{issue['severity']}] {issue['code']} at {issue['path']}: {issue['message']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
