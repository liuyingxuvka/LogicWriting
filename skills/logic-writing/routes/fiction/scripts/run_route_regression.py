#!/usr/bin/env python3
"""Run the canonical Storyline route regression matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from storyline_route_check import RouteBlocked, compile_route_decision


def default_skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_case(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"route fixture must be an object: {path}")
    return payload


def _compiled_case_result(
    case_id: str,
    expected: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    mismatches: list[str] = []
    for field in (
        "status",
        "canonical_artifact",
        "alias_used",
        "route_id",
        "depth_tier",
        "closure_level",
        "prose_phase",
    ):
        if decision.get(field) != expected.get(field):
            mismatches.append(
                f"{field}: expected {expected.get(field)!r}, observed {decision.get(field)!r}"
            )
    surfaces = decision.get("required_surfaces")
    if not isinstance(surfaces, list):
        mismatches.append("required_surfaces is not a list")
        surfaces = []
    for surface in expected.get("required_surfaces_include", []):
        if surface not in surfaces:
            mismatches.append(f"required surface missing: {surface}")
    for surface in expected.get("required_surfaces_exclude", []):
        if surface in surfaces:
            mismatches.append(f"unexpected required surface: {surface}")
    return {
        "case_id": case_id,
        "expected_status": "compiled",
        "observed_status": decision.get("status"),
        "passed": not mismatches,
        "mismatches": mismatches,
        "decision": decision,
    }


def run_case(path: Path, taxonomy_path: Path) -> dict[str, Any]:
    fixture = load_case(path)
    case_id = fixture.get("case_id")
    request = fixture.get("request")
    expected = fixture.get("expected")
    if not isinstance(case_id, str) or not isinstance(request, dict) or not isinstance(expected, dict):
        return {
            "case_id": str(case_id or path.stem),
            "expected_status": "fixture_valid",
            "observed_status": "fixture_invalid",
            "passed": False,
            "mismatches": ["fixture requires string case_id plus request/expected objects"],
        }
    try:
        decision = compile_route_decision(request, taxonomy_path)
    except RouteBlocked as exc:
        if expected.get("status") == "blocked" and exc.code == expected.get("issue_code"):
            return {
                "case_id": case_id,
                "expected_status": "blocked",
                "observed_status": "blocked",
                "observed_issue_code": exc.code,
                "passed": True,
                "mismatches": [],
            }
        return {
            "case_id": case_id,
            "expected_status": expected.get("status"),
            "observed_status": "blocked",
            "observed_issue_code": exc.code,
            "passed": False,
            "mismatches": [
                f"expected {expected.get('status')!r}/{expected.get('issue_code')!r}, "
                f"observed blocked/{exc.code!r}"
            ],
        }
    if expected.get("status") == "blocked":
        return {
            "case_id": case_id,
            "expected_status": "blocked",
            "observed_status": "compiled",
            "passed": False,
            "mismatches": ["fail-closed fixture compiled a successful route"],
            "decision": decision,
        }
    return _compiled_case_result(case_id, expected, decision)


def review_taxonomy_contract(taxonomy_path: Path) -> dict[str, Any]:
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    canonical = taxonomy.get("canonical_artifacts")
    aliases = taxonomy.get("aliases")
    failures: list[str] = []
    compiled_pair_count = 0
    compiled_alias_count = 0
    if not isinstance(canonical, dict) or not isinstance(aliases, dict):
        return {
            "passed": False,
            "compiled_canonical_phase_pairs": 0,
            "compiled_aliases": 0,
            "failures": ["taxonomy must contain canonical_artifacts and aliases objects"],
        }
    for artifact_id, artifact in canonical.items():
        if not isinstance(artifact, dict) or not isinstance(artifact.get("allowed_prose_phases"), list):
            failures.append(f"canonical artifact has no phase list: {artifact_id}")
            continue
        for phase in artifact["allowed_prose_phases"]:
            try:
                decision = compile_route_decision(
                    {"artifact_type": artifact_id, "prose_phase": phase},
                    taxonomy_path,
                )
            except RouteBlocked as exc:
                failures.append(f"canonical pair blocked: {artifact_id}/{phase}: {exc.code}")
                continue
            compiled_pair_count += 1
            if decision.get("canonical_artifact") != artifact_id or decision.get("alias_used") is not False:
                failures.append(f"canonical pair compiled with wrong identity: {artifact_id}/{phase}")
    for alias, target in aliases.items():
        if alias in canonical:
            failures.append(f"alias shadows canonical artifact: {alias}")
            continue
        target_row = canonical.get(target)
        if not isinstance(target_row, dict):
            failures.append(f"alias points to unknown canonical artifact: {alias}->{target}")
            continue
        phases = target_row.get("allowed_prose_phases")
        if not isinstance(phases, list) or not phases:
            failures.append(f"alias target has no allowed phase: {alias}->{target}")
            continue
        try:
            decision = compile_route_decision(
                {"artifact_type": alias, "prose_phase": phases[0]},
                taxonomy_path,
            )
        except RouteBlocked as exc:
            failures.append(f"explicit alias blocked: {alias}->{target}: {exc.code}")
            continue
        compiled_alias_count += 1
        if decision.get("canonical_artifact") != target or decision.get("alias_used") is not True:
            failures.append(f"alias compiled with wrong identity: {alias}->{target}")
    return {
        "passed": not failures,
        "compiled_canonical_phase_pairs": compiled_pair_count,
        "compiled_aliases": compiled_alias_count,
        "failures": failures,
    }


def build_report(skill_root: Path) -> dict[str, Any]:
    taxonomy_path = skill_root / "references" / "artifact-taxonomy.json"
    case_root = skill_root / "examples" / "route_cases"
    case_paths = sorted(case_root.glob("*.json"))
    results = [run_case(path, taxonomy_path) for path in case_paths]
    failures = [result for result in results if not result["passed"]]
    taxonomy_contract = review_taxonomy_contract(taxonomy_path)
    required_cases = {
        "compact-micro-story",
        "novella-post-draft",
        "pre-draft-chapter-plan",
        "final-chapter-prose",
        "final-volume-prose",
        "explicit-alias-short-story",
        "unknown-artifact",
    }
    observed_cases = {str(result["case_id"]) for result in results}
    missing_required_cases = sorted(required_cases - observed_cases)
    return {
        "schema_version": "storyline-design.route-regression.report.v1",
        "passed": not failures and not missing_required_cases and taxonomy_contract["passed"],
        "summary": {
            "case_count": len(results),
            "passed_count": len(results) - len(failures),
            "failed_count": len(failures),
            "missing_required_cases": missing_required_cases,
        },
        "taxonomy_contract": taxonomy_contract,
        "results": results,
        "claim_boundary": (
            "This regression proves deterministic route compilation for the checked finite matrix. "
            "It does not prove that required story evidence is present or semantically adequate."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Storyline Design route regression fixtures.")
    parser.add_argument("--skill-root", default=str(default_skill_root()))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = build_report(Path(args.skill_root).resolve())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Route regression: {'passed' if report['passed'] else 'failed'}")
        for result in report["results"]:
            status = "ok" if result["passed"] else "fail"
            print(f"- {status}: {result['case_id']}")
            for mismatch in result.get("mismatches", []):
                print(f"  - {mismatch}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
