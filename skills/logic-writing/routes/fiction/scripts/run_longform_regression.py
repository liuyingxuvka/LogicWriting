#!/usr/bin/env python3
"""Run StorylineDesign Longform Mode positive and negative regressions."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


CURRENT_FAILURE_ENV = "STORYLINE_DESIGN_CURRENT_FAILURE"


def current_failure_path() -> Path | None:
    value = os.environ.get(CURRENT_FAILURE_ENV, "").strip()
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def script(repo_root: Path, name: str) -> str:
    return str(repo_root / "skills" / "logic-writing" / "routes" / "fiction" / "scripts" / name)


def fixture(repo_root: Path, relative: str) -> str:
    return str(repo_root / "skills" / "logic-writing" / "routes" / "fiction" / "examples" / relative)


def command_matrix(repo_root: Path) -> list[dict[str, Any]]:
    positive = "longform_novel_project"
    negative = "longform_failure_cases"
    rows = []
    for owner, filename in (("novel_ledger", "novel-ledger.json"), ("story_contribution", "novel-ledger.json"),
                            ("promise_payoff", "promise-payoff.json"), ("chapter_interface", "chapter-interfaces.json"),
                            ("voice_style_continuity", "voice-style-report.json"), ("longform_closure", "project-mesh.json")):
        rows.append(dict(id="positive."+owner, argv=[sys.executable, script(repo_root, owner+"_check.py"), fixture(repo_root, positive+"/"+filename), "--json"], expected_exit_code=0))
    for name, owner, code in (("fake-chapter-interface", "chapter_interface", None),
                              ("unresolved-key-promise", "novel_ledger", "unresolved_key_or_major_promise"),
                              ("missing-material-continuity", "novel_ledger", "missing_continuity"),
                              ("orphan-chapter", "story_contribution", "unit_not_in_plan:novel_ledger:chapter-orphan"),
                              ("pov-drift", "voice_style_continuity", "blocking_voice_style_drift")):
        row = dict(id="negative."+name, argv=[sys.executable, script(repo_root, owner+"_check.py"), fixture(repo_root, negative+"/"+name+".json"), "--json"], expected_exit_code=1)
        if code: row["expected_issue_codes"] = {code}
        rows.append(row)
    failure_path = current_failure_path()
    if failure_path is not None:
        rows.append(dict(id="current_failure.external_final_closure",
            argv=[sys.executable, script(repo_root, "longform_closure_check.py"), str(failure_path), "--json"],
            expected_exit_code=1, require_domain_rejection=True))
    return rows


def reader_chain_result(repo_root: Path) -> dict[str, Any]:
    """Run the standard eight-step interface against the existing exact manuscript."""
    import shutil
    import tempfile
    with tempfile.TemporaryDirectory(prefix="fiction-reader-chain-") as tmp:
        target = Path(tmp)/"project"
        shutil.copytree(Path(fixture(repo_root,"longform_novel_project")), target)
        common = repo_root/"skills/logic-writing/scripts"
        steps = ((common/"select_route.py", "route-request.json", "route-decision.json"),
                 (common/"build_reader_brief.py", "brief-request.json", "reader-brief.json"),
                 (common/"build_artifact_map.py", "map-request.json", "artifact-map.json"),
                 (common/"validate_shared_writing.py", "shared-writing.json", "shared-writing-result.json"),
                 (common/"audit_reader_output.py", "audit-request.json", "audit.json"),
                 (Path(script(repo_root,"validate_fiction_artifact.py")), "route-review.json", "route-review-result.json"),
                 (common/"derive_closure.py", "closure-input.json", "closure.json"))
        results=[]
        for owner, source, output in steps:
            done=subprocess.run([sys.executable,str(owner),"--input",str(target/source),"--output",str(target/output)],cwd=target,text=True,capture_output=True)
            results.append(dict(step=owner.name,exit_code=done.returncode,stderr=done.stderr))
            if done.returncode:
                results[-1]["result"] = parse_json((target/output).read_text()) if (target/output).is_file() else None
                break
        return dict(id="positive.standard_reader_chain",passed=len(results)==len(steps) and all(row["exit_code"]==0 for row in results),steps=results)


def parse_json(stdout: str) -> Any:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


def run_case(case: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    completed = subprocess.run(case["argv"], cwd=repo_root, text=True, capture_output=True)
    payload = parse_json(completed.stdout)
    expected = case["expected_exit_code"]
    passed = completed.returncode == expected
    expected_codes = case.get("expected_issue_codes")
    expected_any_codes = case.get("expected_any_issue_codes")
    observed_codes: set[str] = set()
    if isinstance(payload, dict) and isinstance(payload.get("issues"), list):
        observed_codes = {
            str(issue.get("code"))
            for issue in payload["issues"]
            if isinstance(issue, dict) and issue.get("code")
        }
    # Loading failures do not prove a domain rejection.  The named binding
    # families also need valid input around their intended domain defect;
    # schema-negative cases owned by other validators keep their own oracles.
    invalid_input_codes = {
        "read_error", "json_decode_error", "invalid_root_type", "invalid_type",
        "invalid_schema_version", "missing_required_field", "missing_required_list",
        "invalid_row_type", "missing_binding_rows", "invalid_decision",
    }
    if expected != 0 and observed_codes & {"read_error", "json_decode_error"}:
        passed = False
    if case.get("require_domain_rejection") and (
        not observed_codes or observed_codes & (invalid_input_codes | {
            "missing_surfaces", "retired_closure_field", "surface_read_error"
        })
    ):
        passed = False
    if expected_codes and not set(expected_codes).issubset(observed_codes):
        passed = False
    if expected_any_codes and not (observed_codes & set(expected_any_codes)):
        passed = False
    return {
        "id": case["id"],
        "argv": case["argv"],
        "expected_exit_code": expected,
        "actual_exit_code": completed.returncode,
        "passed": passed,
        "expected_issue_codes": sorted(expected_codes) if expected_codes else [],
        "expected_any_issue_codes": sorted(expected_any_codes) if expected_any_codes else [],
        "observed_issue_codes": sorted(observed_codes),
        "stdout_json": payload,
        "stderr": completed.stderr,
    }


def build_report(repo_root: Path) -> dict[str, Any]:
    cases = command_matrix(repo_root)
    results = [run_case(case, repo_root) for case in cases]
    results.append(reader_chain_result(repo_root))
    failures = [result for result in results if not result["passed"]]
    return {
        "schema_version": "storyline-design.longform_regression.report.v1",
        "repo_root": str(repo_root),
        "passed": not failures,
        "summary": {
            "case_count": len(results),
            "passed_count": len(results) - len(failures),
            "failed_count": len(failures),
            "current_failure_case_included": current_failure_path() is not None,
        },
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run StorylineDesign long-form regression matrix.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = build_report(Path(args.repo_root).resolve())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Longform regression: {'passed' if report['passed'] else 'failed'}")
        for result in report["results"]:
            status = "ok" if result["passed"] else "fail"
            print(f"- {status}: {result['id']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
