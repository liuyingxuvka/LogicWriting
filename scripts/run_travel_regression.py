#!/usr/bin/env python3
"""Run the single Logic Writing travel-route regression owner."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.repository_root).resolve()
    route = root / "skills" / "logic-writing" / "routes" / "travel"
    scripts = route / "scripts"
    examples = route / "examples"
    cases = [
        ("base-plan", [sys.executable, str(scripts / "validate_travel_plan.py"), str(examples / "good_city_couple_trip" / "plan.json"), "--repository-root", str(root), "--json"]),
        ("positive-branches", [sys.executable, str(scripts / "validate_positive_cases.py"), "--cases-dir", str(examples / "positive_cases"), "--repository-root", str(root), "--json"]),
        ("exact-negative-mutations", [sys.executable, str(scripts / "validate_failure_cases.py"), "--cases-dir", str(examples / "failure_cases"), "--repository-root", str(root), "--json"]),
        ("artifact-text-closure", [sys.executable, str(scripts / "validate_travel_text_outputs.py"), "--good-dir", str(examples / "good_text_outputs"), "--failure-dir", str(examples / "text_failure_cases"), "--repository-root", str(root), "--json"]),
    ]
    results = []
    for case_id, command in cases:
        completed = subprocess.run(
            command, cwd=root, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120, check=False,
        )
        results.append({
            "case_id": case_id,
            "passed": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout_sha256": hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
            "stdout_tail": "" if completed.returncode == 0 else completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        })
    report = {
        "schema_version": "logic-writing.travel-regression.v1",
        "owner": "check.travel.native",
        "passed": all(row["passed"] for row in results),
        "results": results,
        "claim_boundary": "Pass covers the declared travel fixtures and exact expected failures; live trip facts still require current source and hazard checks.",
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("Travel regression: " + ("passed" if report["passed"] else "failed"))
        for row in results:
            print(f"- {'ok' if row['passed'] else 'failed'}: {row['case_id']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
