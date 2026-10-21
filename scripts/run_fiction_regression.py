#!/usr/bin/env python3
"""Run the single Logic Writing fiction-route regression owner."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


# The model-mesh and Guard-lifecycle owners intentionally exercise many native
# child checks.  A single 180-second limit was shorter than the declared finite
# matrix and caused the parent to crash with an unhandled TimeoutExpired.  Keep
# each budget finite, explicit, and large enough for the work it owns.
CASE_TIMEOUT_SECONDS = {
    "route": 120,
    "native": 300,
    "longform": 300,
    "guard-lifecycle": 600,
    "model-mesh": 900,
    "installation-parity": 120,
}




def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value




def _run_case(command: list[str], cwd: Path, timeout_seconds: int) -> dict[str, object]:
    """Run one owner with a bounded wait; a timeout kills it and fails the case."""

    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        stdout, stderr = process.communicate(timeout=30)
    return {
        "returncode": process.returncode,
        "stdout": _text(stdout),
        "stderr": _text(stderr),
        "timed_out": timed_out,
        "timeout_seconds": timeout_seconds,
    }


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
        completed = _run_case(command, root, CASE_TIMEOUT_SECONDS[case_id])
        returncode = completed["returncode"]
        timed_out = bool(completed["timed_out"])
        # A timed-out owner is always a failed regression result.
        passed = returncode == 0 and not timed_out
        results.append({
            "case_id": case_id,
            "passed": passed,
            "returncode": returncode,
            "timed_out": timed_out,
            "timeout_seconds": completed["timeout_seconds"],
            "stdout_sha256": hashlib.sha256(str(completed["stdout"]).encode("utf-8")).hexdigest(),
            "stdout_tail": "" if passed else str(completed["stdout"])[-4000:],
            "stderr_tail": str(completed["stderr"])[-4000:],
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
