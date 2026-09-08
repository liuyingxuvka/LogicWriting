"""Execute the complete local writer/judge acceptance producer.

This is the sole release owner that starts the 48 writers and 48 pair judges.
It delegates the actual loop to ``run_writing_quality_benchmark`` and then
writes a bounded output manifest for downstream consumers.  It never uses a
protocol fixture as a successful quality run and never searches for a remote
provider.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from run_writing_quality_benchmark import (  # noqa: E402
    CASE_COUNT,
    REPEATS,
    VERSIONS,
    _bytes_fp,
    _read_json,
    _write_json,
    run_benchmark,
)
from _common import fingerprint  # noqa: E402


PRODUCER_ID = "check.reader.execution-quality-producer"


def _file_entry(output_dir: Path, path: Path, *, role: str, case_id: str | None = None, repeat: int | None = None, version: str | None = None, judge_index: int | None = None) -> dict[str, Any]:
    relative = path.resolve().relative_to(output_dir.resolve()).as_posix()
    if ".." in Path(relative).parts or path.is_symlink():
        raise ValueError(f"producer output path escaped or is symlinked: {path}")
    return {"role": role, "case_id": case_id, "repeat": repeat, "version": version, "judge_index": judge_index, "path": relative, "sha256": _bytes_fp(path.read_bytes())}


def _build_output_manifest(output_dir: Path, plan: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    writers = _read_json(output_dir / "writers.json") if (output_dir / "writers.json").is_file() else []
    judges = _read_json(output_dir / "judges.json") if (output_dir / "judges.json").is_file() else []
    files: list[dict[str, Any]] = []
    for row in writers if isinstance(writers, list) else []:
        case_id, repeat, version = str(row.get("case_id")), int(row.get("repeat", 0)), str(row.get("version"))
        base = output_dir / "artifacts" / "writers" / case_id / str(repeat) / version
        for name in ("writer.json", "artifact.md", "artifact-map.json"):
            path = base / name
            if path.is_file():
                files.append(_file_entry(output_dir, path, role="writer", case_id=case_id, repeat=repeat, version=version))
    for row in judges if isinstance(judges, list) else []:
        case_id, repeat, judge_index = str(row.get("case_id")), int(row.get("repeat", 0)), int(row.get("judge_index", 0))
        base = output_dir / "artifacts" / "judges" / case_id / str(repeat) / str(judge_index)
        for name in ("judge.json",):
            path = base / name
            if path.is_file():
                files.append(_file_entry(output_dir, path, role="judge", case_id=case_id, repeat=repeat, judge_index=judge_index))
    for path in (output_dir / "benchmark_plan.json", output_dir / "writers.json", output_dir / "judges.json", output_dir / "summary.json", output_dir / "run_result.json"):
        if path.is_file():
            files.append(_file_entry(output_dir, path, role="metadata"))
    summary_path = output_dir / "summary.json"
    summary_fp = _bytes_fp(summary_path.read_bytes()) if summary_path.is_file() else None
    all_records_completed = (
        isinstance(writers, list) and len(writers) == CASE_COUNT * REPEATS * len(VERSIONS)
        and isinstance(judges, list) and len(judges) == CASE_COUNT * REPEATS * 2
        and all(row.get("status") == "completed" for row in (*writers, *judges))
    )
    manifest: dict[str, Any] = {
        "schema_version": "logic-writing.execution-quality-output.v1",
        "producer_check_id": PRODUCER_ID,
        "unit_id": "unit:logic-writing",
        "source_manifest_fingerprint": plan.get("source_manifest_fingerprint"),
        "frozen_plan_fingerprint": fingerprint(plan),
        "toolchain_fingerprint": fingerprint({"backend_id": plan.get("backend_id"), "model_id": plan.get("model_id"), "reasoning_effort": plan.get("reasoning_effort"), "cli_version": plan.get("cli_version"), "cli_sha256": plan.get("cli_sha256")}),
        "evidence_mode": "real_execution",
        "writer_count": sum(row.get("status") == "completed" for row in writers) if isinstance(writers, list) else 0,
        "judge_count": sum(row.get("status") == "completed" for row in judges) if isinstance(judges, list) else 0,
        "terminal_status": "completed" if all_records_completed else "incomplete",
        "files": files,
        "summary_path": "summary.json" if summary_path.is_file() else None,
        "summary_fingerprint": summary_fp,
    }
    manifest["manifest_fingerprint"] = fingerprint(manifest)
    _write_json(output_dir / "output-manifest.json", manifest)
    return manifest


def run_owner(root: Path, *, output_dir: Path, backend_plan: Path | None = None, run_writers: bool = True, run_judges: bool = True) -> dict[str, Any]:
    result = run_benchmark(root, output_dir=output_dir, backend_plan=backend_plan, run_writers=run_writers, run_judges=run_judges)
    plan = _read_json(output_dir / "benchmark_plan.json")
    manifest = _build_output_manifest(output_dir, plan, result)
    owner_result = {
        "schema_version": "logic-writing.reader-acceptance-owner-result.v1",
        "producer_check_id": PRODUCER_ID,
        "status": "passed" if manifest["terminal_status"] == "completed" else "incomplete",
        "benchmark_status": result.get("status"),
        "quality_claim_status": result.get("quality_claim_status"),
        "writer_count": manifest["writer_count"],
        "judge_count": manifest["judge_count"],
        "output_manifest_path": "output-manifest.json",
        "output_manifest_fingerprint": manifest["manifest_fingerprint"],
        "claim_boundary": "Producer pass proves complete local captures and output binding; quality preference remains a separate consumer decision.",
    }
    _write_json(output_dir / "producer-result.json", owner_result)
    _write_json(output_dir / "dependency-index.json", {
        "schema_version": "logic-writing.validation-dependency-index.v1",
        "consumer_check_id": PRODUCER_ID,
        "current_source_fingerprint": plan.get("source_manifest_fingerprint"),
        "current_toolchain_fingerprint": manifest["toolchain_fingerprint"],
        "dependencies": [],
        "producer_output_manifest_path": "output-manifest.json",
        "producer_output_manifest_fingerprint": manifest["manifest_fingerprint"],
        "index_fingerprint": fingerprint({"schema_version": "logic-writing.validation-dependency-index.v1", "consumer_check_id": PRODUCER_ID, "current_source_fingerprint": plan.get("source_manifest_fingerprint"), "current_toolchain_fingerprint": manifest["toolchain_fingerprint"], "dependencies": [], "producer_output_manifest_path": "output-manifest.json", "producer_output_manifest_fingerprint": manifest["manifest_fingerprint"]}),
    })
    return owner_result


def resolve_stage_selection(*, run_writers: bool, run_judges: bool, aggregate_only: bool) -> tuple[bool, bool]:
    """Resolve the CLI execution stage without silently starting a full run.

    The historical default remains a complete producer run when no stage is
    specified.  ``--aggregate-only`` is an explicit escape hatch for a
    pre-existing capture set and cannot be combined with either execution
    stage.  Keeping this decision in a small pure function makes the safety
    boundary directly testable without invoking the local model backend.
    """
    explicit_stage = run_writers or run_judges
    if aggregate_only and explicit_stage:
        raise ValueError("--aggregate-only cannot be combined with --run-writers or --run-judges")
    if aggregate_only:
        return False, False
    return run_writers or not explicit_stage, run_judges or not explicit_stage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--backend-plan", type=Path)
    parser.add_argument("--run-writers", action="store_true")
    parser.add_argument("--run-judges", action="store_true")
    parser.add_argument("--aggregate-only", action="store_true", help="Rebuild producer metadata from existing captures without starting writers or judges")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    output_dir = (args.output_dir or Path(__import__("os").environ.get("LW_VALIDATION_ATTEMPT_ROOT", str(args.root / "run-artifacts" / "reader-execution-quality-producer")))).resolve()
    try:
        run_writers, run_judges = resolve_stage_selection(run_writers=args.run_writers, run_judges=args.run_judges, aggregate_only=args.aggregate_only)
        report = run_owner(args.root.resolve(), output_dir=output_dir, backend_plan=(args.backend_plan or args.root / "tests/fixtures/writing_quality/local-backend-plan.json").resolve(), run_writers=run_writers, run_judges=run_judges)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        report = {"schema_version": "logic-writing.reader-acceptance-owner-result.v1", "producer_check_id": PRODUCER_ID, "status": "failed", "error": str(exc)}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"reader acceptance producer: {report.get('status')}")
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
