"""Read-only quality consumer for a completed local benchmark.

The consumer never starts Codex and never fills missing scores.  It validates
the producer manifest, current frozen plan, byte hashes, 48 writer/48 judge
counts, and the explicit nine-of-twelve quality gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = ROOT / "skills" / "logic-writing" / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

from _common import fingerprint  # noqa: E402
from run_writing_quality_benchmark import CASE_COUNT, REPEATS, VERSIONS, _bytes_fp, _read_json, _write_json  # noqa: E402


def _path(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise ValueError("producer manifest path is not a safe relative path")
    resolved = (root / Path(value)).resolve()
    resolved.relative_to(root.resolve())
    if resolved.is_symlink() or not resolved.is_file():
        raise ValueError(f"producer manifest file is missing or symlinked: {value}")
    return resolved


def check(root: Path, *, plan_path: Path, run_root: Path, dependency_producer: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    run_root = run_root.resolve()
    errors: list[str] = []
    try:
        plan = _read_json(plan_path.resolve())
        manifest = _read_json(run_root / "output-manifest.json")
        result = _read_json(run_root / "run_result.json")
        summary = _read_json(run_root / "summary.json")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return {"check": "writing-quality-run", "status": "incomplete", "errors": [f"quality producer output unavailable: {exc}"], "quality_claim_status": "incomplete"}
    if not isinstance(plan, dict) or not isinstance(manifest, dict) or not isinstance(result, dict) or not isinstance(summary, dict):
        errors.append("plan, manifest, result, and summary must all be objects")
        plan = plan if isinstance(plan, dict) else {}
        manifest = manifest if isinstance(manifest, dict) else {}
    if manifest.get("schema_version") != "logic-writing.execution-quality-output.v1":
        errors.append("producer output manifest schema is not current")
    if manifest.get("producer_check_id") != "check.reader.execution-quality-producer":
        errors.append("producer output manifest belongs to a different owner")
    if manifest.get("evidence_mode") != "real_execution":
        errors.append("protocol-only output cannot satisfy the real quality consumer")
    if manifest.get("frozen_plan_fingerprint") != fingerprint(plan):
        # The portable backend plan is the input contract; the producer also
        # freezes a materialized benchmark_plan.json with case and rubric
        # fingerprints.  Accept that materialized plan only when it is the
        # manifest's exact immutable plan and carries the supplied backend
        # settings/source identity.
        materialized_path = run_root / "benchmark_plan.json"
        try:
            materialized = _read_json(materialized_path)
        except (OSError, UnicodeError, json.JSONDecodeError):
            materialized = None
        if not isinstance(materialized, dict) or manifest.get("frozen_plan_fingerprint") != fingerprint(materialized):
            errors.append("producer output is bound to a different frozen plan")
        elif any(materialized.get(key) != plan.get(key) for key in ("model_id", "reasoning_effort", "cli_version", "cli_sha256")):
            errors.append("materialized benchmark plan changed the portable backend settings")
    effective_plan = plan
    if plan.get("source_manifest_fingerprint") is None and (run_root / "benchmark_plan.json").is_file():
        try:
            candidate_plan = _read_json(run_root / "benchmark_plan.json")
            if isinstance(candidate_plan, dict) and manifest.get("frozen_plan_fingerprint") == fingerprint(candidate_plan):
                effective_plan = candidate_plan
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
    if effective_plan.get("source_manifest_fingerprint") != manifest.get("source_manifest_fingerprint"):
        errors.append("producer output source manifest is stale")
    if dependency_producer and dependency_producer != manifest.get("producer_check_id"):
        errors.append("dependency producer does not match the current output")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        errors.append("producer output manifest has no files")
    else:
        for item in files:
            if not isinstance(item, dict):
                errors.append("producer manifest contains a non-object file entry")
                continue
            try:
                path = _path(run_root, item.get("path"))
                if item.get("sha256") != _bytes_fp(path.read_bytes()):
                    errors.append(f"file hash mismatch: {item.get('path')}")
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
    writers = _read_json(run_root / "writers.json") if (run_root / "writers.json").is_file() else []
    judges = _read_json(run_root / "judges.json") if (run_root / "judges.json").is_file() else []
    if not isinstance(writers, list) or len(writers) != CASE_COUNT * REPEATS * len(VERSIONS):
        errors.append("producer does not contain exactly 48 writer rows")
    if not isinstance(judges, list) or len(judges) != CASE_COUNT * REPEATS * 2:
        errors.append("producer does not contain exactly 48 judge rows")
    if isinstance(writers, list) and any(row.get("status") != "completed" for row in writers if isinstance(row, dict)):
        errors.append("one or more writer rows are not completed")
    if isinstance(judges, list) and any(row.get("status") != "completed" for row in judges if isinstance(row, dict)):
        errors.append("one or more judge rows are not completed and parseable")
    if manifest.get("terminal_status") != "completed":
        errors.append("producer terminal status is not completed")
    if summary.get("status") != "passed" or int(summary.get("improved_case_count", 0)) < 9:
        errors.append("the explicit nine-of-twelve quality gate did not pass")
    status = "passed" if not errors else "failed"
    return {
        "check": "writing-quality-run", "status": status, "errors": errors,
        "quality_claim_status": "passed" if status == "passed" else "incomplete",
        "writer_count": manifest.get("writer_count"), "judge_count": manifest.get("judge_count"),
        "improved_case_count": summary.get("improved_case_count"),
        "producer_output_manifest_fingerprint": manifest.get("manifest_fingerprint"),
        "claim_boundary": "This consumer checks one bounded twelve-case local comparison; it does not generalize the result to arbitrary topics or models.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--plan", type=Path, required=False)
    parser.add_argument("--run-root", type=Path, required=False)
    parser.add_argument("--dependency-producer")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    plan = args.plan or (args.root / "tests/fixtures/writing_quality/local-backend-plan.json")
    run_root = args.run_root or Path(__import__("os").environ.get("LW_VALIDATION_ATTEMPT_ROOT", str(args.root / "run-artifacts" / "reader-execution-quality-producer")))
    report = check(args.root, plan_path=plan, run_root=run_root, dependency_producer=args.dependency_producer)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"writing quality consumer: {report['status']}")
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
