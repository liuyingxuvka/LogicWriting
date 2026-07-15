"""Smoke-test the three installed Logic Writing ownership decisions."""

from __future__ import annotations

import argparse
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
            request = {
                "request_id": f"request:installed-smoke:{index}",
                "decision_id": f"decision:installed-smoke:{index}",
                "decided_at": "2026-07-15T00:00:00Z",
                "terminal_deliverable": {
                    "kind": kind,
                    "description": "Representative installed-skill route smoke scenario",
                    "acceptance_criteria": ["Select one final owner."],
                },
                "scope_class": "substantive",
                "substantial_research_required": research,
                "constraints": {},
                "material_assumptions": [],
            }
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
