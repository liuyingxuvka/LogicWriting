#!/usr/bin/env python3
"""Run the single Logic Writing fiction-route regression owner."""

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
    route = root / "skills" / "logic-writing" / "routes" / "fiction"
    scripts = route / "scripts"
    cases = [
        ("route", [sys.executable, str(scripts / "run_route_regression.py"), "--skill-root", str(route), "--json"]),
        ("native", [sys.executable, str(scripts / "run_native_regression.py"), "--repo-root", str(root), "--json"]),
        ("longform", [sys.executable, str(scripts / "run_longform_regression.py"), "--repo-root", str(root), "--json"]),
        ("guard-lifecycle", [sys.executable, str(scripts / "run_guard_lifecycle_regression.py"), "--repo-root", str(root), "--skill-root", str(route), "--json"]),
        ("model-mesh", [sys.executable, str(scripts / "run_story_model_mesh_regression.py"), "--project-root", str(route / "examples" / "longform_novel_project"), "--repo-root", str(root), "--json"]),
        ("installation-parity", [sys.executable, str(scripts / "run_installed_parity_regression.py")]),
    ]
    results = []
    for case_id, command in cases:
        completed = subprocess.run(
            command, cwd=root, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=180, check=False,
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
        "schema_version": "logic-writing.fiction-regression.v1",
        "owner": "check.fiction.native",
        "passed": all(row["passed"] for row in results),
        "results": results,
        "claim_boundary": "Pass covers the imported fiction route's declared finite matrices; literary quality outside those contracts remains human judgment.",
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("Fiction regression: " + ("passed" if report["passed"] else "failed"))
        for row in results:
            print(f"- {'ok' if row['passed'] else 'failed'}: {row['case_id']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
