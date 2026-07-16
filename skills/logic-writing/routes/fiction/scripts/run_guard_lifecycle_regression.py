#!/usr/bin/env python3
"""Run StorylineDesign universal Guard lifecycle regression matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


UNIVERSAL_GUARD_SURFACES = [
    "flowguard_process",
    "traceguard_storyline",
    "worldguard_story_claims",
    "logicguard_theme_support",
    "sourceguard_canon_support",
]
DEFAULT_REQUIRED_SURFACES = [
    *UNIVERSAL_GUARD_SURFACES,
    "ledger",
    "turning_point",
    "scene_contract",
    "promise_payoff",
]
COMPACT_REQUIRED_SURFACES = [
    *UNIVERSAL_GUARD_SURFACES,
    "compact_story_movement",
    "main_promise_boundary",
]
LONGFORM_REQUIRED_SURFACES = [
    *UNIVERSAL_GUARD_SURFACES,
    "novel_ledger",
    "story_contribution",
    "chapter_interface",
    "prose_blueprint",
    "promise_payoff",
    "voice_style",
]
ARTIFACT_MATRIX = [
    ("micro_story", COMPACT_REQUIRED_SURFACES),
    ("short_story", DEFAULT_REQUIRED_SURFACES),
    ("chapter_batch", LONGFORM_REQUIRED_SURFACES),
]
MUTATION_MATRIX = ["missing", "stale", "prose_only", "not_applicable_without_reason"]
RECEIPT_MUTATION_MATRIX = [
    "inline_report",
    "missing_receipt",
    "stale_receipt",
    "wrong_owner",
    "wrong_input",
    "receipt_hash",
]
GUARD_SPECS = {
    "flowguard_process": {
        "guard_id": "flowguard",
        "native_owner": "flowguard-development-process-flow",
        "route_id": "development_process_flow",
        "check_id": "flowguard.development_process_flow.terminal",
        "tool_version": "0.55.0",
        "status": "passed",
    },
    "traceguard_storyline": {
        "guard_id": "traceguard",
        "native_owner": "traceguard",
        "route_id": "traceguard",
        "check_id": "traceguard.storyline_terminal",
        "tool_version": "0.4.3",
        "status": "passed",
    },
    "worldguard_story_claims": {
        "guard_id": "worldguard",
        "native_owner": "worldguard",
        "route_id": "worldguard",
        "check_id": "worldguard.story_claims_terminal",
        "tool_version": "0.1.2",
        "status": "passed",
    },
    "logicguard_theme_support": {
        "guard_id": "logicguard",
        "native_owner": "logicguard",
        "route_id": "logicguard",
        "check_id": "logicguard.theme_support_applicability",
        "tool_version": "0.17.4",
        "status": "not_applicable_with_reason",
    },
    "sourceguard_canon_support": {
        "guard_id": "sourceguard",
        "native_owner": "sourceguard",
        "route_id": "sourceguard",
        "check_id": "sourceguard.canon_support_applicability",
        "tool_version": "0.4.2",
        "status": "not_applicable_with_reason",
    },
}


def default_skill_root(repo_root: Path) -> Path:
    if (repo_root / "SKILL.md").exists() and (repo_root / "scripts").exists():
        return repo_root
    return repo_root / "skills" / "logic-writing" / "routes" / "fiction"


def script(skill_root: Path, name: str) -> str:
    return str(skill_root / "scripts" / name)


def fixture(skill_root: Path, relative: str) -> str:
    return str(skill_root / "examples" / relative)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_ref(path: Path, relative_to: Path) -> str:
    relative = Path(os.path.relpath(path.resolve(), relative_to.resolve())).as_posix()
    return f"file:{relative};sha256:{sha256_file(path)}"


def fixture_input_fingerprint(artifact: str, surface: str) -> str:
    digest = hashlib.sha256(f"{artifact}|{surface}|native-owner-input-v1".encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def guard_claim_boundary(surface: str, artifact: str, status: str) -> str:
    if surface == "logicguard_theme_support":
        return f"No material theme, moral, or ending-interpretation claim exists in the {artifact} matrix input."
    if surface == "sourceguard_canon_support":
        return f"No user canon, prior draft, adaptation source, historical fact, or external source constrains the {artifact} matrix input."
    return f"{surface} native terminal receipt covers only the current {artifact} matrix input."


def build_guard_check(surface: str, artifact: str, case_root: Path) -> dict[str, Any]:
    spec = GUARD_SPECS[surface]
    status = str(spec["status"])
    fingerprint = fixture_input_fingerprint(artifact, surface)
    claim_boundary = guard_claim_boundary(surface, artifact, status)
    receipt_id = f"{artifact}-{surface}-terminal"
    receipt_path = case_root / "receipts" / f"{surface}.json"
    handoff_path = case_root / "handoffs" / f"{surface}.json"
    receipt = {
        "schema_version": f"{spec['guard_id']}.native_terminal_receipt.v1",
        "receipt_id": receipt_id,
        "guard_id": spec["guard_id"],
        "surface": surface,
        "native_owner": spec["native_owner"],
        "route_id": spec["route_id"],
        "check_id": spec["check_id"],
        "tool_version": spec["tool_version"],
        "input_fingerprint": fingerprint,
        "terminal": True,
        "immutable": True,
        "freshness": "current",
        "status": status,
        "claim_boundary": claim_boundary,
    }
    write_json(receipt_path, receipt)
    handoff = {
        "schema_version": "storyline-design.guard_handoff.v1",
        "surface": surface,
        "guard_id": spec["guard_id"],
        "native_owner": spec["native_owner"],
        "native_route_id": spec["route_id"],
        "native_check_id": spec["check_id"],
        "tool_version": spec["tool_version"],
        "receipt_schema_version": receipt["schema_version"],
        "input_fingerprint": fingerprint,
        "terminal_receipt_id": receipt_id,
        "terminal_receipt_ref": content_ref(receipt_path, handoff_path.parent),
        "terminal_status": status,
        "claim_boundary": claim_boundary,
    }
    write_json(handoff_path, handoff)
    check: dict[str, Any] = {
        "surface": surface,
        "check_name": surface.replace("_", "-"),
        "status": status,
        "required": True,
        "evidence_ref": content_ref(handoff_path, case_root),
        "input_fingerprint": fingerprint,
    }
    if status == "not_applicable_with_reason":
        check.update(
            {
                "not_applicable_reason": claim_boundary,
                "blocks_closure": False,
                "next_action": f"Run {spec['guard_id']} if the scoped claim is added.",
            }
        )
    return check


def check_for_surface(surface: str, artifact: str, case_root: Path) -> dict[str, Any]:
    if surface in GUARD_SPECS:
        return build_guard_check(surface, artifact, case_root)
    base = {
        "surface": surface,
        "check_name": surface.replace("_", "-"),
        "status": "passed",
        "required": True,
        "evidence_ref": f"evidence:{artifact}:{surface}",
    }
    base["child_report"] = {
        "schema_version": "storyline-design.guard_lifecycle_fixture_child.v1",
        "passed": True,
        "summary": {"error_count": 0},
    }
    return base


def base_storyline_bundle(artifact: str, required_surfaces: list[str], case_root: Path) -> dict[str, Any]:
    return {
        "schema_version": "storyline-design.closure_evidence_bundle.v1",
        "project_id": f"matrix-{artifact}",
        "requested_artifact": artifact,
        "prose_phase": "pre_draft",
        "claim_boundary": f"Generated matrix case for {artifact}; validates guard lifecycle closure shape.",
        "checks": [check_for_surface(surface, artifact, case_root) for surface in required_surfaces],
        "worldguard_claims": [{"id": f"wg-{artifact}", "worldguard_status": "pass", "closure_effect": "continue"}],
        "unresolved_gaps": [],
        "deferred_or_downgraded_work": [],
        "next_actions": [],
    }


def mutate_bundle(bundle: dict[str, Any], surface: str, mutation: str, case_root: Path) -> dict[str, Any]:
    payload = json.loads(json.dumps(bundle))
    checks = payload["checks"]
    if mutation == "missing":
        payload["checks"] = [check for check in checks if check.get("surface") != surface]
        return payload
    for check in checks:
        if check.get("surface") != surface:
            continue
        if mutation == "stale":
            check["status"] = "stale"
            check["stale"] = True
            check["stale_reason"] = f"{surface} evidence predates the current story model."
            check["next_action"] = f"refresh_{surface}"
        elif mutation == "prose_only":
            check["status"] = "passed"
            check["evidence_ref"] = "review:AI self-report says this surface is fine."
            check["blocks_closure"] = False
        elif mutation == "not_applicable_without_reason":
            check["status"] = "not_applicable_with_reason"
            check["evidence_ref"] = "n/a"
            check["blocks_closure"] = False
            check["next_action"] = ""
            check.pop("not_applicable_reason", None)
        elif mutation == "inline_report":
            check["child_report"] = {"passed": True, "status": "passed"}
        elif mutation == "wrong_input":
            check["input_fingerprint"] = f"sha256:{'f' * 64}"
        elif mutation in {"missing_receipt", "stale_receipt", "wrong_owner", "receipt_hash"}:
            handoff_path = case_root / "handoffs" / f"{surface}.json"
            receipt_path = case_root / "receipts" / f"{surface}.json"
            handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
            if mutation == "missing_receipt":
                receipt_path.unlink()
            elif mutation == "stale_receipt":
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                receipt["freshness"] = "stale"
                write_json(receipt_path, receipt)
                handoff["terminal_receipt_ref"] = content_ref(receipt_path, handoff_path.parent)
                write_json(handoff_path, handoff)
            elif mutation == "wrong_owner":
                wrong_owner = "sourceguard" if surface != "sourceguard_canon_support" else "flowguard-development-process-flow"
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                receipt["native_owner"] = wrong_owner
                handoff["native_owner"] = wrong_owner
                write_json(receipt_path, receipt)
                handoff["terminal_receipt_ref"] = content_ref(receipt_path, handoff_path.parent)
                write_json(handoff_path, handoff)
            elif mutation == "receipt_hash":
                receipt_reference = str(handoff["terminal_receipt_ref"])
                handoff["terminal_receipt_ref"] = receipt_reference.rsplit(";sha256:", 1)[0] + f";sha256:{'0' * 64}"
                write_json(handoff_path, handoff)
            check["evidence_ref"] = content_ref(handoff_path, case_root)
        break
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def parse_json(stdout: str) -> Any:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


def run_argv(case_id: str, argv: list[str], cwd: Path, expected_exit_code: int, expected_issue_codes: set[str] | None = None) -> dict[str, Any]:
    completed = subprocess.run(argv, cwd=cwd, text=True, capture_output=True)
    payload = parse_json(completed.stdout)
    observed_codes: set[str] = set()
    if isinstance(payload, dict) and isinstance(payload.get("issues"), list):
        observed_codes = {
            str(issue.get("code"))
            for issue in payload["issues"]
            if isinstance(issue, dict) and issue.get("code")
        }
    passed = completed.returncode == expected_exit_code
    if expected_issue_codes and not (observed_codes & expected_issue_codes):
        passed = False
    return {
        "id": case_id,
        "argv": argv,
        "expected_exit_code": expected_exit_code,
        "actual_exit_code": completed.returncode,
        "passed": passed,
        "expected_issue_codes": sorted(expected_issue_codes) if expected_issue_codes else [],
        "observed_issue_codes": sorted(observed_codes),
        "stdout_json": payload,
        "stderr": completed.stderr,
    }


def static_cases(repo_root: Path, skill_root: Path) -> list[dict[str, Any]]:
    storyline = script(skill_root, "storyline_closure_check.py")
    longform = script(skill_root, "longform_closure_check.py")
    cases: list[dict[str, Any]] = [
        {
            "id": "positive.static_compact_guard_pass",
            "argv": [
                sys.executable,
                storyline,
                fixture(skill_root, "guard_lifecycle_cases/compact-pass.json"),
                "--repository-root",
                str(repo_root),
                "--json",
            ],
            "expected_exit_code": 0,
        },
        {
            "id": "positive.short_story_project",
            "argv": [
                sys.executable,
                storyline,
                fixture(skill_root, "short_story_project/expected-closure.json"),
                "--repository-root",
                str(repo_root),
                "--json",
            ],
            "expected_exit_code": 0,
        },
        {
            "id": "positive.longform_final_prose",
            "argv": [
                sys.executable,
                longform,
                fixture(skill_root, "longform_novel_project/longform-final-prose-closure.json"),
                "--repo-root",
                str(repo_root),
                "--json",
            ],
            "expected_exit_code": 0,
        },
    ]
    negative_expectations = {
        "compact-missing-flowguard.json": {"missing_required_surface"},
        "compact-missing-traceguard.json": {"missing_required_surface"},
        "compact-bad-worldguard-scopeout.json": {"fictional_world_auto_scopeout"},
        "compact-missing-logicguard.json": {"missing_required_surface"},
        "compact-missing-sourceguard.json": {"missing_required_surface"},
        "compact-prose-only-evidence.json": {"prose_only_evidence"},
        "compact-stale-flowguard.json": set(),
    }
    for filename, expected_codes in negative_expectations.items():
        cases.append(
            {
                "id": f"negative.static_{Path(filename).stem}",
                "argv": [
                    sys.executable,
                    storyline,
                    fixture(skill_root, f"guard_lifecycle_cases/{filename}"),
                    "--repository-root",
                    str(repo_root),
                    "--json",
                ],
                "expected_exit_code": 1,
                "expected_issue_codes": expected_codes,
            }
        )
    return cases


def dynamic_matrix_cases(repo_root: Path, skill_root: Path) -> list[dict[str, Any]]:
    storyline = script(skill_root, "storyline_closure_check.py")
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix=".storyline-guard-matrix-", dir=repo_root) as temp_dir:
        temp_root = Path(temp_dir)
        for artifact, required_surfaces in ARTIFACT_MATRIX:
            positive_root = temp_root / f"{artifact}-positive"
            positive_path = positive_root / "closure.json"
            write_json(positive_path, base_storyline_bundle(artifact, required_surfaces, positive_root))
            results.append(
                run_argv(
                    f"positive.matrix_{artifact}",
                    [
                        sys.executable,
                        storyline,
                        str(positive_path),
                        "--repository-root",
                        str(repo_root),
                        "--json",
                    ],
                    repo_root,
                    0,
                )
            )
            for surface in UNIVERSAL_GUARD_SURFACES:
                for mutation in MUTATION_MATRIX + RECEIPT_MUTATION_MATRIX:
                    case_root = temp_root / f"{artifact}-{surface}-{mutation}"
                    path = case_root / "closure.json"
                    payload = base_storyline_bundle(artifact, required_surfaces, case_root)
                    write_json(path, mutate_bundle(payload, surface, mutation, case_root))
                    expected_codes: set[str] | None = None
                    if mutation == "missing":
                        expected_codes = {"missing_required_surface"}
                    elif mutation == "prose_only":
                        expected_codes = {"prose_only_evidence"}
                    elif mutation == "not_applicable_without_reason":
                        expected_codes = {"missing_required_field", "missing_not_applicable_reason"}
                    elif mutation == "inline_report":
                        expected_codes = {"guard_inline_report_forbidden"}
                    elif mutation == "missing_receipt":
                        expected_codes = {"guard_receipt_content_file_missing"}
                    elif mutation == "stale_receipt":
                        expected_codes = {"guard_receipt_stale"}
                    elif mutation == "wrong_owner":
                        expected_codes = {"guard_native_owner_mismatch"}
                    elif mutation == "wrong_input":
                        expected_codes = {"guard_input_fingerprint_mismatch"}
                    elif mutation == "receipt_hash":
                        expected_codes = {"guard_receipt_content_hash_mismatch"}
                    results.append(
                        run_argv(
                            f"negative.matrix_{artifact}.{surface}.{mutation}",
                            [
                                sys.executable,
                                storyline,
                                str(path),
                                "--repository-root",
                                str(repo_root),
                                "--json",
                            ],
                            repo_root,
                            1,
                            expected_codes,
                        )
                    )
        fiction_root = temp_root / "fiction-worldguard-auto-scopeout"
        fiction_path = fiction_root / "closure.json"
        fiction_payload = base_storyline_bundle("short_story", DEFAULT_REQUIRED_SURFACES, fiction_root)
        for check in fiction_payload["checks"]:
            if check.get("surface") == "worldguard_story_claims":
                check["status"] = "not_applicable_with_reason"
                check["evidence_ref"] = "reason: because the story is fictional."
                check["blocks_closure"] = False
                check["next_action"] = "No WorldGuard action because fiction."
        fiction_payload["worldguard_claims"] = []
        write_json(fiction_path, fiction_payload)
        results.append(
            run_argv(
                "negative.matrix_worldguard_fiction_only_scopeout",
                [
                    sys.executable,
                    storyline,
                    str(fiction_path),
                    "--repository-root",
                    str(repo_root),
                    "--json",
                ],
                repo_root,
                1,
                {"fictional_world_auto_scopeout"},
            )
        )
    return results


def build_report(repo_root: Path, skill_root: Path) -> dict[str, Any]:
    case_results = [
        run_argv(
            case["id"],
            case["argv"],
            repo_root,
            case["expected_exit_code"],
            case.get("expected_issue_codes"),
        )
        for case in static_cases(repo_root, skill_root)
    ]
    case_results.extend(dynamic_matrix_cases(repo_root, skill_root))
    failures = [result for result in case_results if not result["passed"]]
    return {
        "schema_version": "storyline-design.guard_lifecycle_regression.report.v1",
        "repo_root": str(repo_root),
        "skill_root": str(skill_root),
        "passed": not failures,
        "matrix_dimensions": {
            "artifact_sizes": [artifact for artifact, _ in ARTIFACT_MATRIX],
            "guard_surfaces": UNIVERSAL_GUARD_SURFACES,
            "failure_mutations": MUTATION_MATRIX + RECEIPT_MUTATION_MATRIX + ["fictional_world_auto_scopeout"],
        },
        "summary": {
            "case_count": len(case_results),
            "passed_count": len(case_results) - len(failures),
            "failed_count": len(failures),
        },
        "results": case_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run StorylineDesign universal Guard lifecycle regression matrix.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--skill-root", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    skill_root = Path(args.skill_root).resolve() if args.skill_root else default_skill_root(repo_root).resolve()
    report = build_report(repo_root, skill_root)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Guard lifecycle regression: {'passed' if report['passed'] else 'failed'}")
        for result in report["results"]:
            status = "ok" if result["passed"] else "fail"
            print(f"- {status}: {result['id']} exit {result['actual_exit_code']} expected {result['expected_exit_code']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
