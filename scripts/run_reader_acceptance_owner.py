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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from run_writing_quality_benchmark import (  # noqa: E402
    CASE_COUNT,
    HELD_OUT_CASE_IDS,
    REPEATS,
    VERSIONS,
    _bytes_fp,
    _build_planned_ledger,
    _execution_policy,
    _implementation_identity,
    _load_frozen_inputs,
    _load_plan,
    _load_held_out_inputs,
    _read_json,
    _write_json,
    run_benchmark,
)
from _common import fingerprint  # noqa: E402


PRODUCER_ID = "check.reader.execution-quality-producer"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _file_entry(output_dir: Path, path: Path, *, role: str, case_id: str | None = None, repeat: int | None = None, version: str | None = None, judge_index: int | None = None) -> dict[str, Any]:
    relative = path.resolve().relative_to(output_dir.resolve()).as_posix()
    if ".." in Path(relative).parts or path.is_symlink():
        raise ValueError(f"producer output path escaped or is symlinked: {path}")
    return {"role": role, "case_id": case_id, "repeat": repeat, "version": version, "judge_index": judge_index, "path": relative, "sha256": _bytes_fp(path.read_bytes())}


def _build_output_manifest(
    output_dir: Path,
    plan: dict[str, Any],
    result: dict[str, Any],
    *,
    root: Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
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
    for path in (
        output_dir / "benchmark_plan.json", output_dir / "case_requests.json",
        output_dir / "planned-ledger.json", output_dir / "writers.json",
        output_dir / "judges.json", output_dir / "summary.json", output_dir / "run_result.json",
    ):
        if path.is_file():
            files.append(_file_entry(output_dir, path, role="metadata"))
    summary_path = output_dir / "summary.json"
    summary_fp = _bytes_fp(summary_path.read_bytes()) if summary_path.is_file() else None
    mode = str(plan.get("mode") or "pair")
    expected_writer_count = int(plan.get("planned_writer_count", CASE_COUNT * REPEATS * len(VERSIONS)))
    expected_judge_count = int(plan.get("planned_judge_count", CASE_COUNT * REPEATS * 2))
    all_records_completed = (
        isinstance(writers, list) and len(writers) == expected_writer_count
        and isinstance(judges, list) and len(judges) == expected_judge_count
        and all(row.get("status") == "completed" for row in (*writers, *judges))
    )
    capture_validation_error: str | None = None
    if all_records_completed:
        # Status flags are producer output, not proof that the files contain
        # the captures they claim.  Re-run the same canonical row validators
        # used by the quality consumer before advertising a completed
        # producer manifest.  This also prevents aggregate-only reuse of a
        # duplicated, stale, or protocol-shaped row set.
        try:
            from check_writing_quality_run import (
                _validate_held_out_judge_rows,
                _validate_held_out_writer_rows,
                _validate_judge_rows,
                _validate_writer_rows,
            )

            if mode == "held_out":
                repository_root = (root or ROOT).resolve()
                held_out_cases, _, _, _, _ = _load_held_out_inputs(repository_root / "tests" / "fixtures" / "writing_quality")
                writer_index = _validate_held_out_writer_rows(output_dir, writers, plan=plan, cases=held_out_cases)
                _validate_held_out_judge_rows(output_dir, judges, writers=writer_index, plan=plan, cases=held_out_cases)
            elif expected_writer_count == CASE_COUNT * REPEATS * len(VERSIONS) and expected_judge_count == CASE_COUNT * REPEATS * 2:
                writer_index = _validate_writer_rows(output_dir, writers, plan=plan)
                _validate_judge_rows(output_dir, judges, writers=writer_index, plan=plan)
            # A one-case preflight is still a real captured run, but it does
            # not pretend to exhaust the 48-row comparison validator.
        except (OSError, UnicodeError, ValueError, TypeError, ImportError) as exc:
            all_records_completed = False
            capture_validation_error = str(exc)
    manifest: dict[str, Any] = {
        "schema_version": "logic-writing.execution-quality-output.v1",
        "producer_check_id": PRODUCER_ID,
        "unit_id": "unit:logic-writing",
        "source_manifest_fingerprint": plan.get("source_manifest_fingerprint"),
        "implementation_fingerprint": plan.get("implementation_fingerprint"),
        "execution_policy_fingerprint": plan.get("execution_policy_fingerprint"),
        "product_implementation_identity": plan.get("product_implementation_identity"),
        "execution_policy_identity": plan.get("execution_policy_identity"),
        "frozen_plan_fingerprint": fingerprint(plan),
        "toolchain_fingerprint": fingerprint({"backend_id": plan.get("backend_id"), "model_id": plan.get("model_id"), "reasoning_effort": plan.get("reasoning_effort"), "cli_version": plan.get("cli_version"), "cli_sha256": plan.get("cli_sha256")}),
        "evidence_mode": "real_execution",
        "mode": mode,
        "writer_count": sum(row.get("status") == "completed" for row in writers) if isinstance(writers, list) else 0,
        "judge_count": sum(row.get("status") == "completed" for row in judges) if isinstance(judges, list) else 0,
        "planner_count": int(result.get("actual_planner_count", 0)),
        "planned_writer_count": int(plan.get("planned_writer_count", expected_writer_count)),
        "planned_judge_count": int(plan.get("planned_judge_count", expected_judge_count)),
        "planned_planner_count": int(plan.get("planned_planner_count", 0)),
        "planned_execution_count": int(plan.get("planned_execution_count", expected_writer_count + expected_judge_count)),
        "actual_execution_count": int(result.get("actual_execution_count", 0)),
        "held_out_passed": bool(result.get("held_out_passed", False)) if mode == "held_out" else None,
        "terminal_status": "completed" if all_records_completed else "incomplete",
        "files": files,
        "summary_path": "summary.json" if summary_path.is_file() else None,
        "summary_fingerprint": summary_fp,
    }
    if capture_validation_error is not None:
        manifest["capture_validation_error"] = capture_validation_error
    manifest["manifest_fingerprint"] = fingerprint(manifest)
    if write:
        _write_json(output_dir / "output-manifest.json", manifest)
    return manifest


def _write_if_missing(path: Path, value: Any) -> None:
    """Publish a failure receipt without overwriting earlier immutable output."""

    if not path.exists():
        _write_json(path, value)


def _record_initialization_failure(
    output_dir: Path,
    *,
    root: Path,
    error: Exception,
    mode: str = "pair",
    terminal_reason: str | None = None,
) -> dict[str, Any]:
    """Leave a complete, non-passing producer receipt when setup cannot run.

    Input loading and backend-plan validation happen before the benchmark can
    materialize its normal plan.  Downstream checks must still receive an
    explicit real-execution/incomplete boundary instead of a missing-output
    ambiguity.  The helper writes only absent files so a partially produced
    capture set remains immutable and cannot be silently replaced.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    reason = terminal_reason or f"producer_initialization_failed:{type(error).__name__}"
    message = str(error)
    held_out = mode == "held_out"
    planned_writer_count = 4 if held_out else CASE_COUNT * REPEATS * len(VERSIONS)
    planned_judge_count = 8 if held_out else CASE_COUNT * REPEATS * 2
    planned_planner_count = 8 if held_out else CASE_COUNT * REPEATS * 2
    plan = {
        "schema_version": "logic-writing.writing-quality-run.v2",
        "benchmark_id": "logic-writing-held-out-4x1x2" if held_out else "logic-writing-real-quality-12x2x2",
        "mode": mode,
        "evidence_mode": "real_execution",
        "source_manifest_fingerprint": None,
        "backend_id": None,
        "model_id": None,
        "reasoning_effort": None,
        "cli_version": None,
        "cli_sha256": None,
        "terminal_reason": reason,
        "error": message,
    }
    plan.update({
        "case_count": 4 if held_out else CASE_COUNT,
        "repeats_per_version": 1 if held_out else REPEATS,
        "versions": ["current"] if held_out else list(VERSIONS),
        "planned_writer_count": planned_writer_count,
        "planned_judge_count": planned_judge_count,
        "planned_planner_count": planned_planner_count,
        "planned_execution_count": planned_writer_count + planned_judge_count + planned_planner_count,
    })
    planned = planned_writer_count + planned_judge_count + planned_planner_count
    progress = {
        "planned": planned,
        "terminal": 0,
        "completed": 0,
        "failed": 0,
        "not_started": planned,
        "scheduled": {
            "planned": planned_writer_count + planned_judge_count,
            "terminal": 0,
            "completed": 0,
            "failed": 0,
            "not_started": planned_writer_count + planned_judge_count,
        },
        "nested_planner": {
            "planned": planned_planner_count,
            "terminal": 0,
            "completed": 0,
            "failed": 0,
            "not_started": planned_planner_count,
        },
    }
    result = {
        "schema_version": "logic-writing.writing-quality-run-result.v2",
        "benchmark_id": plan["benchmark_id"],
        "status": "not_run",
        "terminal_reason": reason,
        "quality_claim_status": "incomplete",
        "planned_writer_count": planned_writer_count,
        "planned_judge_count": planned_judge_count,
        "planned_planner_count": planned_planner_count,
        "planned_execution_count": planned,
        "actual_writer_count": 0,
        "actual_judge_count": 0,
        "actual_execution_count": 0,
        "successful_artifact_count": 0,
        "backend_id": None,
        "source_manifest_fingerprint": None,
        "created_at": _now(),
        "planned_status_counts": progress,
        "progress": progress,
        "claim_boundary": "Producer initialization failed; no local writer or independent judge ran.",
        "error": message,
    }
    summary = {
        "schema_version": "logic-writing.held-out-quality-summary.v1" if held_out else "logic-writing.writing-quality-summary.v2",
        "status": "incomplete",
        "mode": mode,
        "held_out_passed": False if held_out else None,
        "case_count": 4 if held_out else CASE_COUNT,
        "improved_case_count": 0,
        "required_improved_case_count": 0 if held_out else 9,
        "cases": [],
        "writer_count": 0,
        "judge_count": 0,
        "claim_boundary": "Producer initialization failed; no quality score exists.",
    }
    _write_if_missing(output_dir / "benchmark_plan.json", plan)
    _write_if_missing(output_dir / "writers.json", [])
    _write_if_missing(output_dir / "judges.json", [])
    _write_if_missing(output_dir / "summary.json", summary)
    _write_if_missing(output_dir / "run_result.json", result)
    placeholder_cases = (
        [{"case_id": case_id} for case_id in HELD_OUT_CASE_IDS]
        if held_out
        else [{"case_id": case_id} for case_id in ("I01", "A01", "F01", "T01", "I02", "A02", "F02", "T02", "I03", "A03", "F03", "T03")]
    )
    placeholder_ledger = _build_planned_ledger(
        placeholder_cases,
        plan,
        repeats_count=1 if held_out else REPEATS,
        versions=("current",) if held_out else VERSIONS,
        mode="held_out" if held_out else "pair",
    )
    placeholder_ledger["terminal_reason"] = reason
    placeholder_ledger["error"] = message
    _write_if_missing(output_dir / "planned-ledger.json", placeholder_ledger)
    try:
        existing_manifest_path = output_dir / "output-manifest.json"
        if existing_manifest_path.is_file():
            existing_manifest = _read_json(existing_manifest_path)
            if not isinstance(existing_manifest, dict):
                raise ValueError("existing output manifest is not an object")
            manifest = existing_manifest
        else:
            materialized_plan = _read_json(output_dir / "benchmark_plan.json")
            if not isinstance(materialized_plan, dict):
                materialized_plan = plan
            materialized_result = _read_json(output_dir / "run_result.json")
            if not isinstance(materialized_result, dict):
                materialized_result = result
            manifest = _build_output_manifest(output_dir, materialized_plan, materialized_result, root=root)
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as manifest_error:
        manifest = {
            "schema_version": "logic-writing.execution-quality-output.v1",
            "producer_check_id": PRODUCER_ID,
            "unit_id": "unit:logic-writing",
            "mode": mode,
            "source_manifest_fingerprint": None,
            "frozen_plan_fingerprint": fingerprint(plan),
            "toolchain_fingerprint": fingerprint({"backend_id": None, "model_id": None, "reasoning_effort": None, "cli_version": None, "cli_sha256": None}),
            "evidence_mode": "real_execution",
            "writer_count": 0,
            "judge_count": 0,
            "planner_count": 0,
            "held_out_passed": False if mode == "held_out" else None,
            "terminal_status": "incomplete",
            "files": [],
            "summary_path": None,
            "summary_fingerprint": None,
            "error": f"{message}; manifest_error={manifest_error}",
        }
        manifest["manifest_fingerprint"] = fingerprint(manifest)
        _write_if_missing(output_dir / "output-manifest.json", manifest)
    owner_result = {
        "schema_version": "logic-writing.reader-acceptance-owner-result.v1",
        "producer_check_id": PRODUCER_ID,
        "status": "incomplete",
        "benchmark_status": "not_run",
        "quality_claim_status": "incomplete",
        "mode": mode,
        "held_out_passed": False if mode == "held_out" else None,
        "writer_count": 0,
        "judge_count": 0,
        "planner_count": 0,
        "output_manifest_path": "output-manifest.json",
        "output_manifest_fingerprint": manifest.get("manifest_fingerprint"),
        "terminal_reason": reason,
        "error": message,
        "claim_boundary": "Producer initialization failed; no local writer or independent judge ran.",
    }
    _write_if_missing(output_dir / "producer-result.json", owner_result)
    dependency = {
        "schema_version": "logic-writing.validation-dependency-index.v1",
        "consumer_check_id": PRODUCER_ID,
        "current_source_fingerprint": None,
        "current_toolchain_fingerprint": manifest.get("toolchain_fingerprint"),
        "dependencies": [],
        "producer_output_manifest_path": "output-manifest.json",
        "producer_output_manifest_fingerprint": manifest.get("manifest_fingerprint"),
        "terminal_reason": reason,
        "index_fingerprint": None,
    }
    dependency["index_fingerprint"] = fingerprint({key: value for key, value in dependency.items() if key != "index_fingerprint"})
    _write_if_missing(output_dir / "dependency-index.json", dependency)
    return owner_result


def _toolchain_fingerprint(plan: dict[str, Any]) -> str:
    """Return the execution identity used by the producer output manifest."""

    return fingerprint({
        "backend_id": plan.get("backend_id"),
        "model_id": plan.get("model_id"),
        "reasoning_effort": plan.get("reasoning_effort"),
        "cli_version": plan.get("cli_version"),
        "cli_sha256": plan.get("cli_sha256"),
    })


def _current_preflight_identity(root: Path, backend_plan: Path | None) -> dict[str, Any]:
    """Derive the identities a completed I01 smoke must have today.

    The preflight is always the canonical I01 pair corpus. A later held-out
    run intentionally has a different input corpus, so its dependency gate
    compares the canonical I01 source identity while requiring the same
    product implementation and execution toolchain identities.
    """

    cases_dir = (root / "tests" / "fixtures" / "writing_quality").resolve()
    _, _, _, source_manifest_fp, _ = _load_frozen_inputs(cases_dir)
    plan = _load_plan(backend_plan, source_manifest_fp=source_manifest_fp)
    implementation_identity = _implementation_identity(root)
    policy_identity = _execution_policy(plan)
    return {
        "source_manifest_fingerprint": source_manifest_fp,
        "implementation_fingerprint": fingerprint(implementation_identity),
        "implementation_identity": implementation_identity,
        "execution_policy_fingerprint": fingerprint(policy_identity),
        "toolchain_fingerprint": _toolchain_fingerprint(plan),
        "plan": dict(plan),
    }


def _validate_preflight_dependency(
    root: Path,
    preflight_run_root: Path | None,
    backend_plan: Path | None,
) -> dict[str, Any]:
    """Validate a completed real I01 smoke before a larger quality lane.

    This check is read-only. It never starts a subprocess and returns a
    structured ``preflight_required`` result for missing, incomplete, stale,
    or mismatched evidence. The preflight lane itself skips this gate so the
    dependency does not become circular.
    """

    if preflight_run_root is None:
        return {"status": "preflight_required", "error": "preflight run root was not provided"}
    run_root = Path(preflight_run_root).resolve()
    if not run_root.is_dir():
        return {"status": "preflight_required", "error": f"preflight run root is missing: {run_root}"}
    try:
        expected = _current_preflight_identity(root.resolve(), backend_plan)
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {"status": "preflight_required", "error": f"current preflight identity unavailable: {exc}"}

    required = ("benchmark_plan.json", "output-manifest.json", "run_result.json", "producer-result.json")
    missing = [name for name in required if not (run_root / name).is_file()]
    if missing:
        return {"status": "preflight_required", "error": f"preflight evidence is incomplete; missing {', '.join(missing)}"}
    try:
        plan = _read_json(run_root / "benchmark_plan.json")
        manifest = _read_json(run_root / "output-manifest.json")
        result = _read_json(run_root / "run_result.json")
        producer = _read_json(run_root / "producer-result.json")
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {"status": "preflight_required", "error": f"preflight evidence is unreadable: {exc}"}
    if not all(isinstance(value, dict) for value in (plan, manifest, result, producer)):
        return {"status": "preflight_required", "error": "preflight evidence must contain four JSON objects"}

    checks: list[str] = []
    if plan.get("mode") != "preflight" or plan.get("benchmark_id") != "logic-writing-preflight-1x1x2":
        checks.append("mode/benchmark_id")
    if plan.get("claim") != "smoke_only" or plan.get("case_order") != ["I01"]:
        checks.append("I01 smoke declaration")
    if plan.get("source_manifest_fingerprint") != expected["source_manifest_fingerprint"]:
        checks.append("source_manifest_fingerprint")
    if plan.get("implementation_fingerprint") != expected["implementation_fingerprint"]:
        checks.append("implementation_fingerprint")
    expected_plan = expected["plan"]
    for key in ("backend_id", "model_id", "reasoning_effort", "cli_version", "cli_sha256"):
        if plan.get(key) != expected_plan.get(key):
            checks.append(f"toolchain.{key}")
    if plan.get("execution_policy_fingerprint") != expected["execution_policy_fingerprint"]:
        checks.append("execution_policy_fingerprint")
    if manifest.get("source_manifest_fingerprint") != expected["source_manifest_fingerprint"]:
        checks.append("manifest.source_manifest_fingerprint")
    if manifest.get("toolchain_fingerprint") != expected["toolchain_fingerprint"]:
        checks.append("toolchain_fingerprint")
    if manifest.get("mode") != "preflight" or manifest.get("evidence_mode") != "real_execution":
        checks.append("manifest execution mode")
    if manifest.get("terminal_status") != "completed":
        checks.append("manifest terminal_status")
    if result.get("status") != "completed":
        checks.append("run_result terminal status")
    if result.get("source_manifest_fingerprint") != expected["source_manifest_fingerprint"]:
        checks.append("run_result.source_manifest_fingerprint")
    if result.get("implementation_fingerprint") != expected["implementation_fingerprint"]:
        checks.append("run_result.implementation_fingerprint")
    if result.get("execution_policy_fingerprint") != expected["execution_policy_fingerprint"]:
        checks.append("run_result.execution_policy_fingerprint")
    try:
        actual_writer_count = int(result.get("actual_writer_count", 0) or 0)
        actual_judge_count = int(result.get("actual_judge_count", 0) or 0)
    except (TypeError, ValueError):
        actual_writer_count = actual_judge_count = 0
        checks.append("writer/judge smoke counts")
    if actual_writer_count < 2 or actual_judge_count < 2:
        checks.append("writer/judge smoke counts")
    if producer.get("status") != "passed":
        checks.append("producer status")
    if checks:
        return {
            "status": "preflight_required",
            "error": "preflight evidence is incomplete or stale: " + ", ".join(checks),
            "observed": {
                "source_manifest_fingerprint": plan.get("source_manifest_fingerprint"),
                "implementation_fingerprint": plan.get("implementation_fingerprint"),
                "toolchain_fingerprint": manifest.get("toolchain_fingerprint"),
            },
            "expected": {
                "source_manifest_fingerprint": expected["source_manifest_fingerprint"],
                "implementation_fingerprint": expected["implementation_fingerprint"],
                "toolchain_fingerprint": expected["toolchain_fingerprint"],
            },
        }
    return {
        "status": "passed",
        "run_root": str(run_root),
        "source_manifest_fingerprint": expected["source_manifest_fingerprint"],
        "implementation_fingerprint": expected["implementation_fingerprint"],
        "toolchain_fingerprint": expected["toolchain_fingerprint"],
    }


def _aggregate_existing(
    root: Path,
    *,
    output_dir: Path,
    backend_plan: Path | None,
    mode: str,
) -> dict[str, Any]:
    """Read and revalidate an existing producer run without starting or writing.

    Aggregate-only is a review of already captured evidence.  It must not
    create a run root, rematerialize a plan, refresh timestamps, or publish a
    replacement receipt.  The manifest is rebuilt in memory so capture
    validation still runs, while the frozen plan and all on-disk metadata stay
    byte-for-byte unchanged.
    """

    output_dir = output_dir.resolve()
    base = {
        "schema_version": "logic-writing.reader-acceptance-owner-result.v1",
        "producer_check_id": PRODUCER_ID,
        "mode": mode,
        "aggregate_only": True,
        "read_only": True,
        "output_manifest_path": "output-manifest.json",
        "claim_boundary": "Aggregate-only reopens existing local captures and performs no subprocess or filesystem write.",
    }
    if not output_dir.is_dir():
        return {
            **base,
            "status": "incomplete",
            "quality_claim_status": "incomplete",
            "terminal_reason": "aggregate_only_output_missing",
            "error": f"aggregate-only run root is missing: {output_dir}",
        }
    required = ("benchmark_plan.json", "output-manifest.json", "run_result.json", "summary.json")
    missing = [name for name in required if not (output_dir / name).is_file()]
    if missing:
        return {
            **base,
            "status": "incomplete",
            "quality_claim_status": "incomplete",
            "terminal_reason": "aggregate_only_evidence_incomplete",
            "error": "aggregate-only evidence is incomplete; missing " + ", ".join(missing),
        }
    try:
        plan = _read_json(output_dir / "benchmark_plan.json")
        manifest = _read_json(output_dir / "output-manifest.json")
        result = _read_json(output_dir / "run_result.json")
        summary = _read_json(output_dir / "summary.json")
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {
            **base,
            "status": "incomplete",
            "quality_claim_status": "incomplete",
            "terminal_reason": "aggregate_only_evidence_unreadable",
            "error": f"aggregate-only evidence is unreadable: {exc}",
        }
    if not all(isinstance(value, dict) for value in (plan, manifest, result, summary)):
        return {
            **base,
            "status": "incomplete",
            "quality_claim_status": "incomplete",
            "terminal_reason": "aggregate_only_evidence_invalid",
            "error": "aggregate-only plan, manifest, result, and summary must be JSON objects",
        }

    try:
        cases_dir = (root.resolve() / "tests" / "fixtures" / "writing_quality").resolve()
        if mode == "held_out":
            _, _, _, current_source_fp, _ = _load_held_out_inputs(cases_dir)
        else:
            _, _, _, current_source_fp, _ = _load_frozen_inputs(cases_dir)
        current_implementation_fp = fingerprint(_implementation_identity(root.resolve()))
        expected_plan = _load_plan(backend_plan, source_manifest_fp=current_source_fp)
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {
            **base,
            "status": "incomplete",
            "quality_claim_status": "incomplete",
            "terminal_reason": "aggregate_only_identity_unavailable",
            "error": f"aggregate-only current identity is unavailable: {exc}",
        }

    stale: list[str] = []
    if plan.get("mode") != mode:
        stale.append("mode")
    if plan.get("source_manifest_fingerprint") != current_source_fp:
        stale.append("source_manifest_fingerprint")
    if plan.get("implementation_fingerprint") != current_implementation_fp:
        stale.append("implementation_fingerprint")
    expected_policy_fp = fingerprint(_execution_policy(plan))
    if plan.get("execution_policy_fingerprint") != expected_policy_fp:
        stale.append("execution_policy_fingerprint")
    for key in ("backend_id", "model_id", "reasoning_effort", "cli_version", "cli_sha256"):
        if key in expected_plan and plan.get(key) != expected_plan.get(key):
            stale.append(f"toolchain.{key}")
    for payload_name, payload in (("manifest", manifest), ("run_result", result)):
        if payload.get("source_manifest_fingerprint") != current_source_fp:
            stale.append(f"{payload_name}.source_manifest_fingerprint")
        if payload.get("implementation_fingerprint") != current_implementation_fp:
            stale.append(f"{payload_name}.implementation_fingerprint")
        if payload.get("execution_policy_fingerprint") != expected_policy_fp:
            stale.append(f"{payload_name}.execution_policy_fingerprint")
    if stale:
        return {
            **base,
            "status": "stale",
            "quality_claim_status": "incomplete",
            "terminal_reason": "aggregate_only_identity_stale",
            "stale_fields": sorted(set(stale)),
            "error": "aggregate-only evidence is stale: " + ", ".join(sorted(set(stale))),
            "source_manifest_fingerprint": current_source_fp,
            "implementation_fingerprint": current_implementation_fp,
        }

    try:
        rebuilt_manifest = _build_output_manifest(
            output_dir,
            plan,
            result,
            root=root.resolve(),
            write=False,
        )
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError, ImportError) as exc:
        return {
            **base,
            "status": "incomplete",
            "quality_claim_status": "incomplete",
            "terminal_reason": "aggregate_only_capture_validation_failed",
            "error": f"aggregate-only capture validation failed: {exc}",
        }
    terminal_status = str(rebuilt_manifest.get("terminal_status") or "incomplete")
    report = {
        **base,
        "status": "passed" if terminal_status == "completed" else "incomplete",
        "benchmark_status": result.get("status"),
        "quality_claim_status": result.get("quality_claim_status", "incomplete"),
        "held_out_passed": bool(result.get("held_out_passed", False)) if mode == "held_out" else None,
        "writer_count": rebuilt_manifest.get("writer_count", 0),
        "judge_count": rebuilt_manifest.get("judge_count", 0),
        "planner_count": rebuilt_manifest.get("planner_count", 0),
        "terminal_status": terminal_status,
        "output_manifest_fingerprint": rebuilt_manifest.get("manifest_fingerprint"),
        "source_manifest_fingerprint": current_source_fp,
        "implementation_fingerprint": current_implementation_fp,
    }
    if rebuilt_manifest.get("capture_validation_error"):
        report["capture_validation_error"] = rebuilt_manifest["capture_validation_error"]
    if terminal_status != "completed":
        report["terminal_reason"] = "aggregate_only_capture_incomplete"
    return report


def run_owner(
    root: Path,
    *,
    output_dir: Path,
    backend_plan: Path | None = None,
    run_writers: bool = True,
    run_judges: bool = True,
    held_out_only: bool = False,
    preflight_case: str | None = None,
    repeats: int | None = None,
    preflight_run_root: Path | None = None,
    aggregate_only: bool = False,
) -> dict[str, Any]:
    if held_out_only and preflight_case is not None:
        raise ValueError("--held-out-only cannot be combined with --preflight-case")
    mode = "held_out" if held_out_only else ("preflight" if preflight_case is not None else "pair")
    if aggregate_only:
        return _aggregate_existing(
            root.resolve(),
            output_dir=output_dir,
            backend_plan=backend_plan,
            mode=mode,
        )
    # The I01 lane is the dependency producer and must remain runnable without
    # a preflight root. Aggregate-only is read-only and also keeps the old
    # behaviour. A normal quality lane with a usable backend plan is blocked
    # before any writer/judge subprocess can start when its smoke evidence is
    # absent or stale.
    if preflight_case is None and (run_writers or run_judges):
        # Keep the existing initialization-failure result for callers that
        # explicitly point at a missing backend plan. The normal CLI supplies
        # an existing plan, which is always subject to the dependency gate.
        if backend_plan is None or backend_plan.is_file():
            dependency = _validate_preflight_dependency(root.resolve(), preflight_run_root, backend_plan)
            if dependency.get("status") != "passed":
                detail = str(dependency.get("error") or "preflight evidence is required")
                return _record_initialization_failure(
                    output_dir.resolve(),
                    root=root.resolve(),
                    error=ValueError(detail),
                    mode=mode,
                    terminal_reason="preflight_required",
                )
    try:
        result = run_benchmark(
            root,
            output_dir=output_dir,
            backend_plan=backend_plan,
            run_writers=run_writers,
            run_judges=run_judges,
            mode=mode,
            preflight_case=preflight_case,
            repeats_override=repeats,
        )
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return _record_initialization_failure(
            output_dir.resolve(),
            root=root.resolve(),
            error=exc,
            mode="held_out" if held_out_only else ("preflight" if preflight_case else "pair"),
        )
    plan = _read_json(output_dir / "benchmark_plan.json")
    manifest = _build_output_manifest(output_dir, plan, result, root=root)
    owner_result = {
        "schema_version": "logic-writing.reader-acceptance-owner-result.v1",
        "producer_check_id": PRODUCER_ID,
        "status": "passed" if manifest["terminal_status"] == "completed" else "incomplete",
        "benchmark_status": result.get("status"),
        "quality_claim_status": result.get("quality_claim_status"),
        "mode": result.get("mode", plan.get("mode", "pair")),
        "held_out_passed": bool(result.get("held_out_passed", False)),
        "writer_count": manifest["writer_count"],
        "judge_count": manifest["judge_count"],
        "planner_count": manifest.get("planner_count", 0),
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


def resolve_quality_selection(
    *,
    held_out_only: bool,
    preflight_case: str | None,
    repeats: int | None,
) -> tuple[str, str | None, int | None]:
    """Keep holdout, smoke, and full pair evidence mutually identifiable."""

    if held_out_only and preflight_case is not None:
        raise ValueError("--held-out-only cannot be combined with --preflight-case")
    if repeats is not None and int(repeats) < 1:
        raise ValueError("--repeats must be positive")
    if held_out_only:
        if repeats is not None:
            raise ValueError("--held-out-only cannot be combined with --repeats")
        return "held_out", None, None
    if preflight_case is not None:
        return "preflight", str(preflight_case), int(repeats if repeats is not None else 1)
    if repeats is not None:
        raise ValueError("--repeats requires --preflight-case")
    return "pair", None, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--backend-plan", type=Path)
    parser.add_argument("--run-writers", action="store_true")
    parser.add_argument("--run-judges", action="store_true")
    parser.add_argument("--aggregate-only", action="store_true", help="Rebuild producer metadata from existing captures without starting writers or judges")
    parser.add_argument("--held-out-only", action="store_true", help="Run the four-case single-article holdout lane")
    parser.add_argument("--preflight-case", help="Run one canonical case as smoke-only preflight evidence")
    parser.add_argument("--repeats", type=int, help="Preflight repeat count; requires --preflight-case")
    parser.add_argument("--preflight-run-root", type=Path, help="Completed I01 preflight evidence required by held-out/full pair runs")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    output_dir = (args.output_dir or Path(__import__("os").environ.get("LW_VALIDATION_ATTEMPT_ROOT", str(args.root / "run-artifacts" / "reader-execution-quality-producer")))).resolve()
    try:
        mode, preflight_case, repeats = resolve_quality_selection(
            held_out_only=args.held_out_only,
            preflight_case=args.preflight_case,
            repeats=args.repeats,
        )
        run_writers, run_judges = resolve_stage_selection(run_writers=args.run_writers, run_judges=args.run_judges, aggregate_only=args.aggregate_only)
        report = run_owner(
            args.root.resolve(),
            output_dir=output_dir,
            backend_plan=(args.backend_plan or args.root / "tests/fixtures/writing_quality/local-backend-plan.json").resolve(),
            run_writers=run_writers,
            run_judges=run_judges,
            held_out_only=mode == "held_out",
            preflight_case=preflight_case,
            repeats=repeats,
            preflight_run_root=args.preflight_run_root.resolve() if args.preflight_run_root else None,
            aggregate_only=args.aggregate_only,
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        report = {"schema_version": "logic-writing.reader-acceptance-owner-result.v1", "producer_check_id": PRODUCER_ID, "status": "failed", "error": str(exc)}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"reader acceptance producer: {report.get('status')}")
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
