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
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = ROOT / "skills" / "logic-writing" / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

from _common import fingerprint  # noqa: E402
from execution_record_resolver import LocalExecutionRecordResolver  # noqa: E402
from reader_execution import validate_execution_record  # noqa: E402
from reader_pipeline import validate_artifact_map  # noqa: E402
from run_writing_quality_benchmark import (  # noqa: E402
    CASE_COUNT,
    CASE_ORDER,
    REPEATS,
    VERSIONS,
    _bytes_fp,
    _extract_json,
    _pair_writer_input_fingerprint,
    _read_json,
    _validate_judgment_payload,
    _write_json,
)


def _path(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise ValueError("producer manifest path is not a safe relative path")
    resolved = (root / Path(value)).resolve()
    resolved.relative_to(root.resolve())
    if resolved.is_symlink() or not resolved.is_file():
        raise ValueError(f"producer manifest file is missing or symlinked: {value}")
    return resolved


def _manifest_fingerprint(manifest: Mapping[str, Any]) -> str:
    """Return the fingerprint the producer had to commit for its manifest."""

    return fingerprint(
        {key: value for key, value in manifest.items() if key != "manifest_fingerprint"}
    )


def _record_request_matches(record: Mapping[str, Any], request: Mapping[str, Any], *, role: str) -> None:
    """Keep the persisted execution record tied to the exact producer request."""

    if record.get("role") != role:
        raise ValueError(f"{role} row contains a record for another role")
    # dispatch_* adds the role to the sanitized request before invoking the
    # backend.  The benchmark row intentionally persists the caller request
    # without that derived field, so compare against the exact dispatched
    # shape rather than the pre-dispatch row shape.
    dispatched_request = dict(request)
    dispatched_request["role"] = role
    if record.get("request_fingerprint") != fingerprint(dispatched_request):
        raise ValueError(f"{role} execution record is not bound to its persisted request")
    if record.get("input_reader_intent_fingerprint") != request.get("reader_intent_fingerprint"):
        raise ValueError(f"{role} execution record has a stale ReaderIntent input")
    if record.get("input_writer_input_fingerprint") != request.get("writer_input_fingerprint"):
        raise ValueError(f"{role} execution record has a stale writer input")


def _writer_key(row: Mapping[str, Any]) -> tuple[str, int, str]:
    try:
        return str(row["case_id"]), int(row["repeat"]), str(row["version"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("writer row has an invalid case/repeat/version key") from exc


def _judge_key(row: Mapping[str, Any]) -> tuple[str, int, int]:
    try:
        return str(row["case_id"]), int(row["repeat"]), int(row["judge_index"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("judge row has an invalid case/repeat/judge key") from exc


def _validate_writer_rows(
    run_root: Path,
    writers: list[Any],
    *,
    plan: Mapping[str, Any],
) -> dict[tuple[str, int, str], Mapping[str, Any]]:
    expected = {
        (case_id, repeat, version)
        for repeat in range(1, REPEATS + 1)
        for case_id in CASE_ORDER
        for version in VERSIONS
    }
    if len(writers) != len(expected):
        raise ValueError("producer does not contain exactly 48 writer rows")
    resolver = LocalExecutionRecordResolver(
        run_root / "attempts",
        expected_cli_version=str(plan.get("cli_version") or "") or None,
        expected_cli_sha256=str(plan.get("cli_sha256") or "") or None,
        expected_backend_id=str(plan.get("backend_id") or "") or None,
    )
    index: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    contexts: set[str] = set()
    run_ids: set[str] = set()
    for row in writers:
        if not isinstance(row, Mapping):
            raise ValueError("producer writers contain a non-object row")
        key = _writer_key(row)
        if key in index:
            raise ValueError(f"producer contains duplicate writer row: {key}")
        if key not in expected:
            raise ValueError(f"producer contains an unexpected writer row: {key}")
        if row.get("status") != "completed" or not isinstance(row.get("record"), Mapping):
            raise ValueError(f"writer row is not a completed captured execution: {key}")
        request = row.get("request")
        if not isinstance(request, Mapping):
            raise ValueError(f"writer row has no persisted request: {key}")
        expected_run_id = f"writer:{key[0]}:{key[1]}:{key[2]}"
        if row.get("request_fingerprint") != fingerprint(dict(request)):
            raise ValueError(f"writer request fingerprint is stale: {key}")
        if request.get("request_id") != expected_run_id or request.get("run_id") != expected_run_id:
            raise ValueError(f"writer request identity is not bound to its row key: {key}")
        record = row["record"]
        _record_request_matches(record, request, role="writer")
        if record.get("run_id") != expected_run_id:
            raise ValueError(f"writer execution run id is not bound to its row key: {key}")
        validate_execution_record(record, resolver)
        context = str(record.get("context_id") or "")
        run_id = str(record.get("run_id") or "")
        if not context or context in contexts:
            raise ValueError(f"writer contexts are missing or reused: {key}")
        if not run_id or run_id in run_ids:
            raise ValueError(f"writer run ids are missing or reused: {key}")
        contexts.add(context)
        run_ids.add(run_id)
        if row.get("artifact_fingerprint") != record.get("output_fingerprint"):
            raise ValueError(f"writer artifact is not bound to its execution output: {key}")
        artifact_path = _path(run_root, row.get("artifact_path"))
        try:
            artifact_text = artifact_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ValueError(f"writer artifact is unreadable: {key}") from exc
        if row.get("artifact_text") != artifact_text:
            raise ValueError(f"writer row text differs from its captured artifact: {key}")
        map_path = artifact_path.with_name("artifact-map.json")
        artifact_map = _read_json(map_path)
        validate_artifact_map(artifact_map)
        if Path(str(artifact_map.get("artifact_path"))).resolve() != artifact_path:
            raise ValueError(f"writer ArtifactMap points at a different file: {key}")
        if artifact_map.get("artifact_fingerprint") != row.get("artifact_fingerprint"):
            raise ValueError(f"writer ArtifactMap fingerprint is not bound to its row: {key}")
        if row.get("artifact_map_fingerprint") != artifact_map.get("map_fingerprint"):
            raise ValueError(f"writer row has a stale ArtifactMap fingerprint: {key}")
        index[key] = row
    if set(index) != expected:
        raise ValueError("producer writer rows do not exhaust the canonical 48-key universe")
    return index


def _validate_judge_rows(
    run_root: Path,
    judges: list[Any],
    *,
    writers: Mapping[tuple[str, int, str], Mapping[str, Any]],
    plan: Mapping[str, Any],
) -> None:
    expected = {
        (case_id, repeat, judge_index)
        for repeat in range(1, REPEATS + 1)
        for case_id in CASE_ORDER
        for judge_index in (1, 2)
    }
    if len(judges) != len(expected):
        raise ValueError("producer does not contain exactly 48 judge rows")
    resolver = LocalExecutionRecordResolver(
        run_root / "attempts",
        expected_cli_version=str(plan.get("cli_version") or "") or None,
        expected_cli_sha256=str(plan.get("cli_sha256") or "") or None,
        expected_backend_id=str(plan.get("backend_id") or "") or None,
    )
    seen: set[tuple[str, int, int]] = set()
    for row in judges:
        if not isinstance(row, Mapping):
            raise ValueError("producer judges contain a non-object row")
        key = _judge_key(row)
        if key in seen:
            raise ValueError(f"producer contains duplicate judge row: {key}")
        if key not in expected:
            raise ValueError(f"producer contains an unexpected judge row: {key}")
        seen.add(key)
        if row.get("status") != "completed" or not isinstance(row.get("record"), Mapping):
            raise ValueError(f"judge row is not a completed captured execution: {key}")
        request = row.get("request")
        record = row["record"]
        if not isinstance(request, Mapping):
            raise ValueError(f"judge row has no persisted request: {key}")
        expected_run_id = f"judge:{key[0]}:{key[1]}:{key[2]}"
        if row.get("request_fingerprint") != fingerprint(dict(request)):
            raise ValueError(f"judge request fingerprint is stale: {key}")
        if request.get("request_id") != expected_run_id or request.get("run_id") != expected_run_id:
            raise ValueError(f"judge request identity is not bound to its row key: {key}")
        _record_request_matches(record, request, role="judge")
        if record.get("run_id") != expected_run_id:
            raise ValueError(f"judge execution run id is not bound to its row key: {key}")
        validate_execution_record(record, resolver)
        if record.get("independence_status") != "verified":
            raise ValueError(f"judge row is not independently verified: {key}")
        if request.get("evaluation_mode") != "pair" or record.get("evaluation_mode") != "pair":
            raise ValueError(f"judge row is not a pair evaluation: {key}")
        pair_inputs = request.get("pair_inputs")
        if not isinstance(pair_inputs, list) or len(pair_inputs) != 2:
            raise ValueError(f"judge row does not persist both writer inputs: {key}")
        record_pair = record.get("pair_inputs")
        if record_pair != pair_inputs:
            raise ValueError(f"judge record pair binding differs from its request: {key}")
        version_by_run_id: dict[str, str] = {}
        for version in VERSIONS:
            writer = writers.get((key[0], key[1], version))
            if isinstance(writer, Mapping) and isinstance(writer.get("record"), Mapping):
                version_by_run_id[str(writer["record"].get("run_id"))] = version
        try:
            order = [version_by_run_id[str(item["writer_run_id"])] for item in pair_inputs]
        except (KeyError, TypeError) as exc:
            raise ValueError(f"judge pair references an unknown writer run: {key}") from exc
        if order != (["baseline", "repaired"] if key[2] == 1 else ["repaired", "baseline"]):
            raise ValueError(f"judge row has an invalid blind order: {key}")
        if row.get("pair_order") != order:
            raise ValueError(f"judge row pair_order is stale: {key}")
        expected_contexts: list[str] = []
        for label, version in zip(("X", "Y"), order, strict=True):
            candidate = next((item for item in pair_inputs if isinstance(item, Mapping) and item.get("anonymous_label") == label), None)
            if candidate is None:
                raise ValueError(f"judge row pair is missing {label}: {key}")
            writer = writers.get((key[0], key[1], version))
            if writer is None:
                raise ValueError(f"judge row references a missing writer: {key}")
            writer_record = writer.get("record")
            if not isinstance(writer_record, Mapping):
                raise ValueError(f"judge row references an invalid writer: {key}")
            for field, expected_value in (
                ("artifact_fingerprint", writer.get("artifact_fingerprint")),
                ("writer_run_id", writer_record.get("run_id")),
                ("writer_context_id", writer_record.get("context_id")),
                ("writer_input_fingerprint", writer_record.get("input_writer_input_fingerprint")),
            ):
                if candidate.get(field) != expected_value:
                    raise ValueError(f"judge row has stale {field} binding: {key}")
            expected_contexts.append(str(writer_record.get("context_id")))
        if request.get("writer_context_ids") != expected_contexts:
            raise ValueError(f"judge request has stale writer context ordering: {key}")
        if request.get("writer_input_fingerprint") != _pair_writer_input_fingerprint(pair_inputs):
            raise ValueError(f"judge request has a stale pair input fingerprint: {key}")
        if record.get("writer_context_ids") != expected_contexts:
            raise ValueError(f"judge record has stale writer context ordering: {key}")
        raw_output_locator = record.get("raw_output_locator")
        raw_path = (run_root / "attempts" / Path(str(raw_output_locator))).resolve()
        raw_path.relative_to((run_root / "attempts").resolve())
        raw_text = raw_path.read_text(encoding="utf-8")
        if row.get("raw_output") != raw_text:
            raise ValueError(f"judge row text differs from its captured output: {key}")
        parsed = _validate_judgment_payload(_extract_json(raw_text))
        if row.get("judgment") != parsed or row.get("judgment_fingerprint") != fingerprint(parsed):
            raise ValueError(f"judge row judgment is not the captured JSON payload: {key}")
    if seen != expected:
        raise ValueError("producer judge rows do not exhaust the canonical 48-key universe")


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
    if manifest.get("manifest_fingerprint") != _manifest_fingerprint(manifest):
        errors.append("producer output manifest fingerprint is stale")
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
    try:
        writers = _read_json(run_root / "writers.json") if (run_root / "writers.json").is_file() else []
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        writers = []
        errors.append(f"producer writers.json is unreadable: {exc}")
    try:
        judges = _read_json(run_root / "judges.json") if (run_root / "judges.json").is_file() else []
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        judges = []
        errors.append(f"producer judges.json is unreadable: {exc}")
    writer_index: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    if not isinstance(writers, list):
        errors.append("producer writers.json is not an array")
    else:
        try:
            writer_index = _validate_writer_rows(run_root, writers, plan=effective_plan)
        except (OSError, UnicodeError, ValueError, TypeError):
            errors.append("producer writer rows do not contain a complete, locally verified capture set")
    if not isinstance(judges, list):
        errors.append("producer judges.json is not an array")
    elif writer_index:
        try:
            _validate_judge_rows(run_root, judges, writers=writer_index, plan=effective_plan)
        except (OSError, UnicodeError, ValueError, TypeError):
            errors.append("producer judge rows do not contain complete, independent, locally verified pair captures")
    elif isinstance(judges, list):
        errors.append("producer judge rows cannot be verified without the complete writer capture set")
    if manifest.get("terminal_status") != "completed":
        errors.append("producer terminal status is not completed")
    if isinstance(result, dict):
        if result.get("summary_fingerprint") != fingerprint(summary):
            errors.append("producer run result summary fingerprint is stale")
        if result.get("source_manifest_fingerprint") != manifest.get("source_manifest_fingerprint"):
            errors.append("producer run result source manifest is stale")
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
