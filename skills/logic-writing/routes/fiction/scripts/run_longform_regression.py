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
    longform = "longform_novel_project"
    failures = "longform_failure_cases"
    commands: list[dict[str, Any]] = [
        {
            "id": "positive.novel_ledger",
            "argv": [sys.executable, script(repo_root, "novel_ledger_check.py"), fixture(repo_root, f"{longform}/novel-ledger.json"), "--json"],
            "expected_exit_code": 0,
        },
        {
            "id": "positive.story_contribution",
            "argv": [sys.executable, script(repo_root, "story_contribution_check.py"), fixture(repo_root, f"{longform}/novel-ledger.json"), "--json"],
            "expected_exit_code": 0,
        },
        {
            "id": "positive.promise_payoff",
            "argv": [sys.executable, script(repo_root, "promise_payoff_check.py"), fixture(repo_root, f"{longform}/promise-payoff.json"), "--json"],
            "expected_exit_code": 0,
        },
        {
            "id": "positive.chapter_interface",
            "argv": [sys.executable, script(repo_root, "chapter_interface_check.py"), fixture(repo_root, f"{longform}/chapter-interfaces.json"), "--json"],
            "expected_exit_code": 0,
        },
        {
            "id": "positive.voice_style",
            "argv": [sys.executable, script(repo_root, "voice_style_continuity_check.py"), fixture(repo_root, f"{longform}/voice-style-report.json"), "--json"],
            "expected_exit_code": 0,
        },
        {
            "id": "positive.model_prose_binding",
            "argv": [sys.executable, script(repo_root, "model_prose_binding_check.py"), fixture(repo_root, f"{longform}/model-prose-binding.json"), "--json"],
            "expected_exit_code": 0,
        },
        {
            "id": "positive.semantic_review",
            "argv": [sys.executable, script(repo_root, "semantic_review_check.py"), fixture(repo_root, f"{longform}/semantic-review.json"), "--json"],
            "expected_exit_code": 0,
        },
        {
            "id": "negative.semantic_review_incomplete_contract",
            "argv": [sys.executable, script(repo_root, "semantic_review_check.py"), fixture(repo_root, f"{failures}/semantic-review-incomplete-contract.json"), "--json"],
            "expected_exit_code": 1,
            "expected_issue_codes": {"missing_rubric_dimension", "passed_with_blocking_scope"},
        },
        {
            "id": "positive.longform_closure",
            "argv": [sys.executable, script(repo_root, "longform_closure_check.py"), fixture(repo_root, f"{longform}/longform-final-prose-closure.json"), "--json"],
            "expected_exit_code": 0,
        },
        {
            "id": "path.absolute_positive_closure_from_repo",
            "argv": [sys.executable, script(repo_root, "longform_closure_check.py"), str((repo_root / "skills" / "logic-writing" / "routes" / "fiction" / "examples" / longform / "longform-final-prose-closure.json").resolve()), "--json"],
            "expected_exit_code": 0,
        },
        {
            "id": "negative.substitute_reverse_outline_as_ledger",
            "argv": [sys.executable, script(repo_root, "longform_closure_check.py"), fixture(repo_root, f"{failures}/substitute-reverse-outline-as-ledger.json"), "--json"],
            "expected_exit_code": 1,
        },
        {
            "id": "negative.weak_reverse_outline_direct",
            "argv": [sys.executable, script(repo_root, "longform_closure_check.py"), fixture(repo_root, f"{failures}/weak-reverse-outline.json"), "--json"],
            "expected_exit_code": 1,
        },
        {
            "id": "negative.markdown_surface_substitution",
            "argv": [sys.executable, script(repo_root, "longform_closure_check.py"), fixture(repo_root, f"{failures}/markdown-model-surface-substitution.json"), "--json"],
            "expected_exit_code": 1,
        },
        {
            "id": "negative.final_prose_fake_ai_review",
            "argv": [sys.executable, script(repo_root, "longform_closure_check.py"), fixture(repo_root, f"{failures}/final-prose-fake-ai-review.json"), "--json"],
            "expected_exit_code": 1,
            "expected_issue_codes": {"invalid_content_reference"},
        },
        {
            "id": "negative.final_prose_hash_mismatch",
            "argv": [sys.executable, script(repo_root, "longform_closure_check.py"), fixture(repo_root, f"{failures}/final-prose-hash-mismatch.json"), "--json"],
            "expected_exit_code": 1,
            "expected_issue_codes": {"content_hash_mismatch"},
        },
        {
            "id": "negative.final_prose_missing_artifact",
            "argv": [sys.executable, script(repo_root, "longform_closure_check.py"), fixture(repo_root, f"{failures}/final-prose-missing-artifact.json"), "--json"],
            "expected_exit_code": 1,
            "expected_issue_codes": {"missing_final_prose_surface"},
        },
        {
            "id": "negative.final_prose_missing_source_requirements",
            "argv": [sys.executable, script(repo_root, "longform_closure_check.py"), fixture(repo_root, f"{failures}/final-prose-missing-source-requirements.json"), "--json"],
            "expected_exit_code": 1,
            "expected_issue_codes": {"missing_final_prose_surface"},
        },
        {
            "id": "negative.final_prose_nonexistent_manuscript",
            "argv": [sys.executable, script(repo_root, "longform_closure_check.py"), fixture(repo_root, f"{failures}/final-prose-nonexistent-manuscript.json"), "--json"],
            "expected_exit_code": 1,
            "expected_issue_codes": {"content_file_missing"},
        },
        {
            "id": "negative.final_prose_stale_semantic_review",
            "argv": [sys.executable, script(repo_root, "longform_closure_check.py"), fixture(repo_root, f"{failures}/final-prose-stale-semantic-review.json"), "--json"],
            "expected_exit_code": 1,
            "expected_issue_codes": {"stale_semantic_review"},
        },
        {
            "id": "negative.final_prose_stale_model_binding",
            "argv": [sys.executable, script(repo_root, "longform_closure_check.py"), fixture(repo_root, f"{failures}/final-prose-stale-model-binding.json"), "--json"],
            "expected_exit_code": 1,
            "expected_issue_codes": {"stale_model_prose_binding"},
        },
        {
            "id": "negative.final_chapter_prose_bypass",
            "argv": [sys.executable, script(repo_root, "longform_closure_check.py"), fixture(repo_root, f"{failures}/final-chapter-prose-bypass.json"), "--json"],
            "expected_exit_code": 1,
            "expected_issue_codes": {"missing_final_prose_surface"},
        },
        {
            "id": "negative.final_volume_prose_bypass",
            "argv": [sys.executable, script(repo_root, "longform_closure_check.py"), fixture(repo_root, f"{failures}/final-volume-prose-bypass.json"), "--json"],
            "expected_exit_code": 1,
            "expected_issue_codes": {"missing_final_prose_surface"},
        },
        {
            "id": "negative.longform_closure_missing_interface",
            "argv": [sys.executable, script(repo_root, "longform_closure_check.py"), fixture(repo_root, f"{failures}/longform-closure-missing-interface.json"), "--json"],
            "expected_exit_code": 1,
        },
        {
            "id": "negative.fake_chapter_interface",
            "argv": [sys.executable, script(repo_root, "chapter_interface_check.py"), fixture(repo_root, f"{failures}/fake-chapter-interface.json"), "--json"],
            "expected_exit_code": 1,
        },
        {
            "id": "negative.unresolved_key_promise",
            "argv": [sys.executable, script(repo_root, "novel_ledger_check.py"), fixture(repo_root, f"{failures}/unresolved-key-promise.json"), "--json"],
            "expected_exit_code": 1,
        },
        {
            "id": "negative.missing_material_continuity",
            "argv": [sys.executable, script(repo_root, "novel_ledger_check.py"), fixture(repo_root, f"{failures}/missing-material-continuity.json"), "--json"],
            "expected_exit_code": 1,
        },
        {
            "id": "negative.orphan_chapter",
            "argv": [sys.executable, script(repo_root, "story_contribution_check.py"), fixture(repo_root, f"{failures}/orphan-chapter.json"), "--json"],
            "expected_exit_code": 1,
        },
        {
            "id": "negative.pov_drift",
            "argv": [sys.executable, script(repo_root, "voice_style_continuity_check.py"), fixture(repo_root, f"{failures}/pov-drift.json"), "--json"],
            "expected_exit_code": 1,
        },
        {
            "id": "negative.unbound_prose_span",
            "argv": [sys.executable, script(repo_root, "model_prose_binding_check.py"), fixture(repo_root, f"{failures}/unbound-prose-span.json"), "--json"],
            "expected_exit_code": 1,
        },
        {
            "id": "negative.unrealized_model_ref",
            "argv": [sys.executable, script(repo_root, "model_prose_binding_check.py"), fixture(repo_root, f"{failures}/unrealized-model-ref.json"), "--json"],
            "expected_exit_code": 1,
        },
        {
            "id": "negative.duplicate_binding_without_delta",
            "argv": [sys.executable, script(repo_root, "model_prose_binding_check.py"), fixture(repo_root, f"{failures}/duplicate-binding-without-delta.json"), "--json"],
            "expected_exit_code": 1,
        },
        {
            "id": "negative.smooth_reveal_without_resistance",
            "argv": [sys.executable, script(repo_root, "model_prose_binding_check.py"), fixture(repo_root, f"{failures}/smooth-reveal-without-resistance.json"), "--json"],
            "expected_exit_code": 1,
        },
        {
            "id": "negative.premature_hypothesis_collapse",
            "argv": [sys.executable, script(repo_root, "model_prose_binding_check.py"), fixture(repo_root, f"{failures}/premature-hypothesis-collapse.json"), "--json"],
            "expected_exit_code": 1,
        },
        {
            "id": "negative.term_register_owner_drift",
            "argv": [sys.executable, script(repo_root, "model_prose_binding_check.py"), fixture(repo_root, f"{failures}/term-register-owner-drift.json"), "--json"],
            "expected_exit_code": 1,
        },
        {
            "id": "negative.length_outlier_without_binding_review",
            "argv": [sys.executable, script(repo_root, "model_prose_binding_check.py"), fixture(repo_root, f"{failures}/length-outlier-without-binding-review.json"), "--json"],
            "expected_exit_code": 1,
        },
        {
            "id": "negative.final_prose_missing_model_prose_binding",
            "argv": [sys.executable, script(repo_root, "longform_closure_check.py"), fixture(repo_root, f"{failures}/final-prose-missing-model-prose-binding.json"), "--json"],
            "expected_exit_code": 1,
            "expected_issue_codes": {"missing_final_prose_surface"},
        },
    ]
    failure_path = current_failure_path()
    if failure_path is not None:
        commands.append(
            {
                "id": "current_failure.external_final_closure",
                "argv": [sys.executable, script(repo_root, "longform_closure_check.py"), str(failure_path), "--json"],
                "expected_exit_code": 1,
                "expected_any_issue_codes": {"surface_evidence_invalid", "surface_evidence_not_local_json", "invalid_content_reference"},
            }
        )
    repository_aware_checks = {
        "longform_closure_check.py",
        "model_prose_binding_check.py",
        "semantic_review_check.py",
    }
    for command in commands:
        argv = command["argv"]
        if Path(argv[1]).name in repository_aware_checks:
            argv.extend(["--repo-root", str(repo_root)])
    return commands


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
            print(f"- {status}: {result['id']} exit {result['actual_exit_code']} expected {result['expected_exit_code']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
