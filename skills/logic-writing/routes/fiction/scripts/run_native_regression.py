#!/usr/bin/env python3
"""Run native Storyline owners not already owned by focused route/closure suites."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_case(repo_root: Path, case_id: str, args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    return {
        "case_id": case_id,
        "passed": completed.returncode == 0,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the remaining Storyline native-owner matrix once.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    repo = Path(args.repo_root).resolve()
    skill = "skills/logic-writing/routes/fiction"
    scripts = f"{skill}/scripts"
    short = f"{skill}/examples/short_story_project"
    longform = f"{skill}/examples/longform_novel_project"
    cases = [
        ("documentation", [f"{scripts}/doc_contract_check.py", "--skill-root", "skills/logic-writing", "--json"]),
        ("reader-room-guidance", [f"{scripts}/reader_room_guidance_check.py", "--check", "all", "--json"]),
        ("short-story-ledger", [f"{scripts}/story_ledger_check.py", f"{short}/story-ledger.yaml", "--json"]),
        ("short-turning-points", [f"{scripts}/turning_point_check.py", f"{short}/story-ledger.yaml", "--json"]),
        ("short-scene-contracts", [f"{scripts}/scene_contract_check.py", f"{short}/story-ledger.yaml", "--json"]),
        ("short-promises", [f"{scripts}/promise_payoff_check.py", f"{short}/story-ledger.yaml", "--json"]),
        ("novel-ledger", [f"{scripts}/novel_ledger_check.py", f"{longform}/novel-ledger.json", "--json"]),
        ("story-contribution", [f"{scripts}/story_contribution_check.py", f"{longform}/novel-ledger.json", "--json"]),
        ("chapter-interfaces", [f"{scripts}/chapter_interface_check.py", f"{longform}/chapter-interfaces.json", "--json"]),
        ("longform-promises", [f"{scripts}/promise_payoff_check.py", f"{longform}/promise-payoff.json", "--json"]),
        ("voice-style", [f"{scripts}/voice_style_continuity_check.py", f"{longform}/voice-style-report.json", "--json"]),
    ]
    results = [run_case(repo, case_id, command) for case_id, command in cases]
    report = {
        "schema_version": "storyline-design.native_regression.report.v1",
        "passed": all(row["passed"] for row in results),
        "summary": {"case_count": len(results), "failed_count": sum(not row["passed"] for row in results)},
        "results": results,
        "claim_boundary": "This owner runs native surfaces not already owned by route, Guard, longform, mesh, or installation checks.",
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Native regression: {'passed' if report['passed'] else 'failed'}")
        for row in results:
            print(f"- {'ok' if row['passed'] else 'failed'}: {row['case_id']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
