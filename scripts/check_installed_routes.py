"""Smoke-test the three installed Logic Writing ownership decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from _release_common import emit, run


SCENARIOS = (
    ("investigation", "research_report", False, "investigation", []),
    ("academic-writing", "thesis_chapter", False, "academic-writing", []),
    ("academic-with-investigation-child", "thesis_chapter", True, "academic-writing", ["investigation"]),
)


def _fingerprint(value: dict) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _request(index: int, kind: str, research: bool) -> dict:
    intent = {
        "schema_version": "2.0", "artifact_mode": "create_new", "language": "en",
        "audience": "A representative installed-skill reader",
        "purpose": "Verify current route ownership.",
        "structure": {"mode": "route_selected", "requested_outline": []},
        "heading_policy": "route_selected", "list_policy": "prose_default",
        "style": {
            "voice": "clear", "formality": "neutral",
            "required_traits": ["coherent"], "forbidden_traits": ["workflow leakage"],
        },
        "extent": {"unit": "words", "minimum": 50, "target": 200, "maximum": 500},
        "artifact_format": "markdown", "citation_policy": "none",
        "table_policy": "allowed", "required_content": [],
        "forbidden_content": [], "reference_examples": [], "unresolved_choices": [],
    }
    intent["intent_fingerprint"] = _fingerprint(intent)
    deliverable = {
        "kind": kind,
        "description": "Representative installed-skill route smoke scenario",
        "acceptance_criteria": ["Select one final owner."],
    }
    deliverable["fingerprint"] = _fingerprint(deliverable)
    writing = {
        "schema_version": "2.0",
        "request_id": f"request:installed-smoke:{index}",
        "terminal_deliverable": deliverable,
        "reader_intent": intent,
    }
    writing["request_fingerprint"] = _fingerprint(writing)
    return {
        "writing_request": writing,
        "decision_id": f"decision:installed-smoke:{index}",
        "decided_at": "2026-07-29T00:00:00Z",
        "substantial_research_required": research,
        "material_assumptions": [],
    }


def check(skill_root: Path) -> dict:
    root = skill_root.resolve()
    findings: list[str] = []
    script = root / "scripts" / "select_route.py"
    if not script.is_file():
        return {"check": "installed-routes", "status": "failed", "findings": ["select_route_missing"]}
    results: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="logic-writing-route-smoke-") as temporary:
        work = Path(temporary)
        for index, (name, kind, research, owner, children) in enumerate(SCENARIOS, start=1):
            request = _request(index, kind, research)
            input_path = work / f"{index}-input.json"
            output_path = work / f"{index}-output.json"
            input_path.write_text(json.dumps(request), encoding="utf-8")
            completed = run(
                [sys.executable, str(script), "--input", str(input_path), "--output", str(output_path)],
                cwd=root,
            )
            if completed.returncode != 0 or not output_path.is_file():
                findings.append(f"scenario_execution_failed:{name}")
                continue
            value = json.loads(output_path.read_text(encoding="utf-8"))
            decision = value.get("route_decision", {})
            passed = decision.get("final_owner") == owner and decision.get("child_routes") == children
            if not passed:
                findings.append(f"scenario_owner_mismatch:{name}")
            results.append(
                {
                    "scenario": name,
                    "final_owner": decision.get("final_owner"),
                    "child_routes": decision.get("child_routes"),
                    "passed": passed,
                }
            )
    yaml = root / "agents" / "openai.yaml"
    if not yaml.is_file() or "$logic-writing" not in yaml.read_text(encoding="utf-8"):
        findings.append("installed_agent_entrypoint_missing")
    return {
        "check": "installed-routes",
        "status": "passed" if not findings else "failed",
        "scenarios": results,
        "findings": findings,
        "claim_boundary": "This smoke check proves installed route selection for three representative requests; it does not execute specialist research or write a final artifact.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return emit(check(args.skill_root), as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
