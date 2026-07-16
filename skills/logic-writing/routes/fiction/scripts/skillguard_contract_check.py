#!/usr/bin/env python3
"""Check StorylineDesign's sole current target-native SkillGuard authority."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


CURRENT_FILES = {
    "contract-source.json",
    "compiled-contract.json",
    "check-manifest.json",
}
FORMER_FILES = {
    "work-contract.json",
    "check_manifest.json",
}
REQUIRED_CHECK_IDS = {
    "check:storyline:model",
    "check:storyline:route-regression",
    "check:storyline:longform-regression",
    "check:storyline:guard-regression",
    "check:storyline:mesh-regression",
    "check:storyline:native-regression",
    "check:storyline:install-regression",
    "check:storyline:depth-route",
    "check:storyline:depth-workflow",
    "check:storyline:depth-validation",
    "check:storyline:depth-closure",
    "check:storyline:depth-positive",
    "check:storyline:depth-shallow",
}
IMPORTANT_OBLIGATIONS = {
    "obligation:storyline-design:route-authority",
    "obligation:storyline-design:real-artifact",
    "obligation:storyline-design:guard-receipt",
    "obligation:storyline-design:project-mesh",
    "obligation:storyline-design:claim-boundary",
}


class Reporter:
    def __init__(self) -> None:
        self.issues: list[dict[str, str]] = []
        self.evidence: list[dict[str, Any]] = []

    def error(self, code: str, path: str, message: str) -> None:
        self.issues.append({"severity": "error", "code": code, "path": path, "message": message})


def roots(value: Path) -> tuple[Path, Path, Path]:
    resolved = value.resolve()
    if resolved.name == ".skillguard":
        skill_root = resolved.parent
    else:
        skill_root = resolved
    if skill_root.name != "storyline-design":
        raise ValueError("target must be the storyline-design skill root or its .skillguard directory")
    repository_root = skill_root.parents[1]
    return repository_root, skill_root, skill_root / ".skillguard"


def load(path: Path, reporter: Reporter) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        reporter.error("current_file_unreadable", str(path), str(exc))
        return {}
    if not isinstance(payload, dict):
        reporter.error("current_file_not_object", str(path), "Current authority file must contain a JSON object.")
        return {}
    return payload


def skillguard_scripts() -> Path | None:
    candidates: list[Path] = []
    codex_home = os.environ.get("CODEX_HOME", "").strip()
    if codex_home:
        candidates.append(Path(codex_home) / "skills" / "skillguard" / "scripts")
    candidates.append(Path.home() / ".codex" / "skills" / "skillguard" / "scripts")
    return next((path for path in candidates if (path / "skillguard_compile.py").is_file()), None)


def run_json(command: list[str], cwd: Path, reporter: Reporter, code: str) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, check=False)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"stdout": completed.stdout, "stderr": completed.stderr}
    reporter.evidence.append({"code": code, "exit_code": completed.returncode, "result": payload})
    if completed.returncode != 0:
        reporter.error(code, "command", completed.stderr.strip() or completed.stdout.strip() or "SkillGuard command failed.")
    return payload if isinstance(payload, dict) else {}


def check_payloads(source: dict[str, Any], compiled: dict[str, Any], manifest: dict[str, Any], reporter: Reporter) -> None:
    expected = {
        "contract-source.json": (source, "skillguard.contract_source.v2"),
        "compiled-contract.json": (compiled, "skillguard.compiled_contract.v2"),
        "check-manifest.json": (manifest, "skillguard.check_manifest.v2"),
    }
    for name, (payload, schema) in expected.items():
        if payload.get("schema_version") != schema:
            reporter.error("schema_not_current", f".skillguard/{name}.schema_version", f"Expected {schema}.")
    if source.get("skill_id") != "storyline-design" or compiled.get("skill_id") != "storyline-design":
        reporter.error("skill_identity_mismatch", ".skillguard", "Source and compiled authority must identify storyline-design.")
    if source.get("integration_mode") != "native-integrated":
        reporter.error("integration_mode_mismatch", "contract-source.json.integration_mode", "Expected native-integrated.")
    depth = source.get("depth_profile")
    if not isinstance(depth, dict) or depth.get("schema_version") != "skillguard.depth_profile.v2" or depth.get("enforcement_level") != "enforced":
        reporter.error("depth_profile_not_current", "contract-source.json.depth_profile", "Expected one enforced skillguard.depth_profile.v2.")
        return
    if depth.get("native_owner_id") != "storyline-design.native-route":
        reporter.error("native_owner_mismatch", "contract-source.json.depth_profile.native_owner_id", "StorylineDesign must remain the native owner.")
    checks = source.get("checks") if isinstance(source.get("checks"), list) else []
    source_ids = {row.get("check_id") for row in checks if isinstance(row, dict)}
    missing = sorted(REQUIRED_CHECK_IDS - source_ids)
    if missing:
        reporter.error("required_check_missing", "contract-source.json.checks", ",".join(missing))
    manifest_checks = manifest.get("checks") if isinstance(manifest.get("checks"), list) else []
    manifest_ids = {row.get("check_id") for row in manifest_checks if isinstance(row, dict)}
    missing_manifest = sorted(REQUIRED_CHECK_IDS - manifest_ids)
    if missing_manifest:
        reporter.error("manifest_check_missing", "check-manifest.json.checks", ",".join(missing_manifest))
    calibration = depth.get("calibration") if isinstance(depth.get("calibration"), dict) else {}
    if set(calibration.get("important_obligation_ids", [])) != IMPORTANT_OBLIGATIONS:
        reporter.error("calibration_obligation_mismatch", "contract-source.json.depth_profile.calibration", "Calibration must cover the five target-important obligations.")
    positives = calibration.get("positive_cases") if isinstance(calibration.get("positive_cases"), list) else []
    shallows = calibration.get("shallow_cases") if isinstance(calibration.get("shallow_cases"), list) else []
    if len(positives) != 1 or positives[0].get("expected_status") != "EXECUTION_DEPTH_PASS" or positives[0].get("expected_blocker_code") != "none":
        reporter.error("positive_calibration_invalid", "contract-source.json.depth_profile.calibration.positive_cases", "Exactly one deep positive case is required.")
    if len(shallows) != 1 or shallows[0].get("expected_status") != "SHALLOW_BLOCKED" or shallows[0].get("expected_blocker_code") != "important_obligation_missing" or shallows[0].get("omitted_important_obligation_id") != "obligation:storyline-design:guard-receipt":
        reporter.error("shallow_calibration_invalid", "contract-source.json.depth_profile.calibration.shallow_cases", "The shallow case must omit only obligation:storyline-design:guard-receipt.")
    plan = manifest.get("content_impact_plan")
    health = plan.get("health") if isinstance(plan, dict) and isinstance(plan.get("health"), dict) else {}
    for key, value in health.items():
        if value:
            reporter.error("content_impact_plan_unhealthy", f"check-manifest.json.content_impact_plan.health.{key}", f"Expected empty health finding, got {value!r}.")


def build_report(value: Path) -> dict[str, Any]:
    reporter = Reporter()
    try:
        repository_root, skill_root, control_root = roots(value)
    except ValueError as exc:
        reporter.error("invalid_target_root", str(value), str(exc))
        return result(value, reporter)
    observed = {path.name for path in control_root.glob("*.json") if path.is_file()}
    for name in sorted(CURRENT_FILES - observed):
        reporter.error("current_authority_missing", f".skillguard/{name}", "Required current authority file is missing.")
    for name in sorted(FORMER_FILES & observed):
        reporter.error("former_authority_residual", f".skillguard/{name}", "Former runtime authority blocks current use; no compatibility route exists.")
    source = load(control_root / "contract-source.json", reporter)
    compiled = load(control_root / "compiled-contract.json", reporter)
    manifest = load(control_root / "check-manifest.json", reporter)
    if source and compiled and manifest:
        check_payloads(source, compiled, manifest, reporter)
    scripts = skillguard_scripts()
    if scripts is None:
        reporter.error("skillguard_runtime_missing", "toolchain", "Current SkillGuard scripts are not installed.")
    elif source and compiled and manifest:
        compile_result = run_json(
            [sys.executable, str(scripts / "skillguard_compile.py"), str(skill_root), "--repository-root", str(repository_root), "--check"],
            repository_root,
            reporter,
            "skillguard_compile_check",
        )
        if compile_result.get("decision") not in {"pass", None} and compile_result.get("ok") is not True:
            reporter.error("skillguard_compile_not_current", ".skillguard", "Compiler check did not report current parity.")
        authority = run_json(
            [sys.executable, str(scripts / "skillguard.py"), "check-runtime-authority", "--target", skill_root.relative_to(repository_root).as_posix(), "--target-root", str(repository_root), "--require-authority", "current"],
            repository_root,
            reporter,
            "skillguard_runtime_authority_check",
        )
        if authority.get("authority") != "current" or authority.get("decision") != "pass":
            reporter.error("runtime_authority_not_current", ".skillguard", f"Observed authority={authority.get('authority')!r} decision={authority.get('decision')!r}.")
    return result(skill_root, reporter)


def result(target: Path, reporter: Reporter) -> dict[str, Any]:
    return {
        "schema_version": "storyline-design.skillguard_contract_check.report.v2",
        "target": str(target),
        "passed": not reporter.issues,
        "summary": {"error_count": len(reporter.issues), "evidence_count": len(reporter.evidence)},
        "issues": reporter.issues,
        "evidence": reporter.evidence,
        "claim_boundary": "This check proves current static/runtime authority and compiler parity only; it does not substitute for an executed depth or closure receipt.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check StorylineDesign current SkillGuard authority.")
    parser.add_argument("target")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = build_report(Path(args.target))
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Storyline SkillGuard contract check: {'passed' if report['passed'] else 'failed'}")
        for issue in report["issues"]:
            print(f"- [{issue['severity']}] {issue['code']} at {issue['path']}: {issue['message']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
