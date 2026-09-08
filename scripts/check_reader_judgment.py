"""Validate one current reader judgment supplied by the execution owner.

This is a consumer wrapper, not a fixture producer.  A judgment can enter the
current-pass path only when the caller supplies a current envelope and one
judge ``ReaderExecutionRecord`` (or an explicitly injected backend produces
one).  With no input, backend, or execution record the wrapper emits a typed
unavailable/repair result.  It never calls the synthetic protocol-chain
helper and it never turns a caller-authored status into an execution receipt.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


UNAVAILABLE = "execution_provider_unavailable"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _unwrap_execution(value: Any) -> Any:
    """Unwrap the result shape emitted by ``dispatch_judge``.

    The provider boundary returns ``{"status": "completed", "record": ...}``
    and an execution owner may persist either that envelope or the record
    itself.  Unavailable envelopes deliberately remain record-less.
    """

    if isinstance(value, Mapping) and "record" in value:
        if value.get("status") != "completed" or value.get("record") is None:
            return None
        return value["record"]
    return value


def _select_execution_record(
    envelope: Mapping[str, Any],
    explicit: Any = None,
) -> dict[str, Any] | None:
    """Resolve exactly one judge record without silently choosing a sibling."""

    candidates: list[tuple[str, Any]] = []
    if explicit is not None:
        candidates.append(("explicit execution record", _unwrap_execution(explicit)))
    for key in ("execution_record", "reader_execution_record"):
        if key in envelope:
            candidates.append((key, _unwrap_execution(envelope[key])))
    rows = envelope.get("reader_execution_records")
    if rows is not None:
        if not isinstance(rows, list):
            raise ValueError("reader_execution_records must be an array")
        candidates.extend(
            (f"reader_execution_records[{index}]", _unwrap_execution(row))
            for index, row in enumerate(rows)
        )

    records: list[tuple[str, Mapping[str, Any]]] = []
    for source, row in candidates:
        if row is None:
            continue
        if not isinstance(row, Mapping):
            raise ValueError(f"{source} must contain an execution-record object")
        if not source.startswith("reader_execution_records["):
            if row.get("role") != "judge":
                raise ValueError(f"{source} must contain a judge ReaderExecutionRecord")
        records.append((source, row))
    judges = [row for _source, row in records if row.get("role") == "judge"]
    if len(judges) > 1:
        fingerprints = {row.get("record_fingerprint") for row in judges}
        if len(fingerprints) != 1:
            raise ValueError("multiple different judge ReaderExecutionRecords were supplied")
    if not judges:
        return None
    record = judges[0]
    if not isinstance(record, dict):
        raise ValueError("judge ReaderExecutionRecord must be an object")
    return record


def _is_protocol_record(record: Mapping[str, Any]) -> bool:
    """Keep synthetic protocol fixtures out of the real quality evidence path."""

    markers = (
        str(record.get("backend_id", "")),
        str(record.get("model_id", "")),
        str(record.get("provider_completion_ref", "")),
    )
    return any(
        marker == "synthetic-protocol-only"
        or marker.startswith("synthetic://")
        or marker.startswith("synthetic-")
        for marker in markers
    )


def _load_backend(spec: str | None) -> Callable[..., Any] | Any | None:
    if not spec:
        return None
    if ":" not in spec:
        raise ValueError("backend must use module:function syntax")
    module_name, function_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    backend = getattr(module, function_name, None)
    if not callable(backend) and not hasattr(backend, "run"):
        raise ValueError(f"backend is not callable or runnable: {spec}")
    return backend


def _judge_request(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Build only the execution request needed by ``dispatch_judge``.

    A backend may be injected for a real run, but it still receives an
    execution request rather than a caller-authored completion record.  The
    rubric fingerprint must be explicit so an evaluation profile cannot be
    silently substituted for a scoring rubric.
    """

    judgment = envelope.get("judgment", envelope)
    brief = envelope.get("reader_brief")
    artifact_map = envelope.get("artifact_map")
    if not isinstance(judgment, Mapping) or not isinstance(brief, Mapping):
        raise ValueError("a current judgment envelope requires judgment and reader_brief")
    rubric = envelope.get("rubric_fingerprint")
    if not isinstance(rubric, str) or not rubric:
        raise ValueError("backend execution requires an explicit rubric_fingerprint")
    if not isinstance(brief.get("reader_intent_fingerprint"), str):
        raise ValueError("reader_brief lacks reader_intent_fingerprint")
    writer_input = brief.get("writer_input_fingerprint")
    if not isinstance(writer_input, str):
        raise ValueError("reader_brief lacks writer_input_fingerprint")
    request: dict[str, Any] = {
        "reader_intent_fingerprint": brief["reader_intent_fingerprint"],
        "writer_input_fingerprint": writer_input,
        "rubric_fingerprint": rubric,
        "evaluation_mode": envelope.get("evaluation_mode", "single"),
        "pair_inputs": envelope.get("pair_inputs", []),
        "settings": envelope.get("settings", {}),
    }
    if isinstance(artifact_map, Mapping):
        request["artifact_fingerprint"] = artifact_map.get("artifact_fingerprint")
    return request


def _unavailable_report(
    *,
    reason: str,
    runtime: Path,
    result_path: Path,
    preparation_status: str = "not_run",
    input_path: Path | None = None,
) -> dict[str, Any]:
    result = {
        "status": "provider_unavailable",
        "errors": [reason],
        "warnings": [],
        "reader_judgment": None,
        "judgment_status": "repair",
        "execution_status": UNAVAILABLE,
        "execution_record_fingerprint": None,
        "required_repairs": [
            "Supply one current judgment envelope and a real judge ReaderExecutionRecord, or configure an authorized execution backend."
        ],
        "claim_boundary": "No independent judge pass is claimed because the execution provider or record is unavailable.",
    }
    _write_json(result_path, result)
    return {
        "check": "reader-judgment-owner",
        "status": "provider_unavailable",
        "preparation_status": preparation_status,
        "judgment_status": "repair",
        "execution_status": UNAVAILABLE,
        "terminal_reason": reason,
        "artifact": None,
        "input": str(input_path) if input_path is not None else None,
        "runtime_outputs": [result_path.name],
        "claim_boundary": result["claim_boundary"],
    }


def check(
    root: Path,
    runtime_root: Path | None = None,
    *,
    input_path: Path | None = None,
    execution_record_path: Path | None = None,
    execution_capture_root: Path | None = None,
    backend: Any = None,
    dependency_producer: str | None = None,
) -> dict[str, Any]:
    """Validate an owner-supplied envelope and its judge execution record.

    ``input_path`` is an envelope containing the current judgment and all
    current evidence objects.  ``execution_record_path`` may point to a raw
    record or the completed envelope returned by ``dispatch_judge``.  When a
    backend is provided and no record is embedded, it is invoked through the
    fixed ``dispatch_judge`` boundary; a missing backend returns unavailable.
    """

    root = root.resolve()
    runtime = (runtime_root or root / "run-artifacts" / "reader-judgment-owner").resolve()
    request_path = runtime / "reader-quality-judgment.json"
    result_path = runtime / "reader-quality-judgment-result.json"
    skill_scripts = root / "skills" / "logic-writing" / "scripts"
    if str(skill_scripts) not in sys.path:
        sys.path.insert(0, str(skill_scripts))
    project_scripts = root / "scripts"
    if str(project_scripts) not in sys.path:
        sys.path.insert(0, str(project_scripts))

    if dependency_producer is not None:
        return _check_dependency_producer(root, runtime, dependency_producer)

    if input_path is None:
        return _unavailable_report(
            reason="no current reader judgment envelope was supplied",
            runtime=runtime,
            result_path=result_path,
        )

    input_path = input_path.resolve()
    try:
        envelope = _load_json(input_path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return _unavailable_report(
            reason=f"current reader judgment envelope is unavailable: {exc}",
            runtime=runtime,
            result_path=result_path,
            input_path=input_path,
        )
    if not isinstance(envelope, dict):
        _write_json(result_path, {"status": "blocked", "errors": ["judgment envelope must be an object"]})
        return {
            "check": "reader-judgment-owner",
            "status": "repair",
            "preparation_status": "provided",
            "judgment_status": "repair",
            "execution_status": "record_invalid",
            "terminal_reason": "judgment envelope must be an object",
            "artifact": None,
            "input": str(input_path),
            "runtime_outputs": [result_path.name],
            "claim_boundary": "No reader-judgment pass is claimed for an invalid envelope.",
        }

    explicit_record = None
    if execution_record_path is not None:
        try:
            explicit_record = _load_json(execution_record_path.resolve())
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            return _unavailable_report(
                reason=f"judge ReaderExecutionRecord is unavailable: {exc}",
                runtime=runtime,
                result_path=result_path,
                preparation_status="provided",
                input_path=input_path,
            )

    try:
        record = _select_execution_record(envelope, explicit_record)
    except ValueError as exc:
        _write_json(result_path, {"status": "blocked", "errors": [str(exc)], "judgment_status": "repair"})
        return {
            "check": "reader-judgment-owner",
            "status": "repair",
            "preparation_status": "provided",
            "judgment_status": "repair",
            "execution_status": "record_invalid",
            "terminal_reason": str(exc),
            "artifact": None,
            "input": str(input_path),
            "runtime_outputs": [result_path.name],
            "claim_boundary": "No reader-judgment pass is claimed for an ambiguous execution record.",
        }

    if record is not None and _is_protocol_record(record):
        return _unavailable_report(
            reason="synthetic protocol-only execution records cannot supply real reader quality evidence",
            runtime=runtime,
            result_path=result_path,
            preparation_status="provided",
            input_path=input_path,
        )

    if record is None and backend is None:
        return _unavailable_report(
            reason="no judge ReaderExecutionRecord or authorized execution backend was supplied",
            runtime=runtime,
            result_path=result_path,
            preparation_status="provided",
            input_path=input_path,
        )

    if record is None:
        try:
            from reader_execution import dispatch_judge

            dispatched = dispatch_judge(_judge_request(envelope), backend)
        except (OSError, ValueError, TypeError, ImportError) as exc:
            return _unavailable_report(
                reason=f"judge backend could not produce a verifiable execution record: {exc}",
                runtime=runtime,
                result_path=result_path,
                preparation_status="provided",
                input_path=input_path,
            )
        if dispatched.get("status") != "completed" or dispatched.get("record") is None:
            return _unavailable_report(
                reason="judge backend returned execution_provider_unavailable",
                runtime=runtime,
                result_path=result_path,
                preparation_status="provided",
                input_path=input_path,
            )
        record = dispatched["record"]

    # Direct judgment validation must be able to re-open the immutable local
    # capture.  A record-shaped object with ``independence_status=verified``
    # is not enough; protocol fixtures use that shape deliberately.  The
    # quality producer passes its capture root through the dependency-owner
    # path below, while direct callers must state the root explicitly (or
    # provide a backend exposing its owner run root).
    capture_root = execution_capture_root.resolve() if execution_capture_root is not None else None
    if capture_root is None and backend is not None:
        candidate_root = getattr(backend, "run_root", None)
        if candidate_root is not None:
            capture_root = Path(candidate_root).expanduser().resolve()
    execution_resolver = None
    if capture_root is not None:
        try:
            from execution_record_resolver import LocalExecutionRecordResolver

            execution_resolver = LocalExecutionRecordResolver(capture_root)
        except (OSError, ValueError, TypeError) as exc:
            return _unavailable_report(
                reason=f"judge execution capture root is unavailable: {exc}",
                runtime=runtime,
                result_path=result_path,
                preparation_status="provided",
                input_path=input_path,
            )

    envelope = dict(envelope)
    envelope["execution_record"] = record
    _write_json(request_path, envelope)
    try:
        from validate_judgment_receipt import validate_judgment_receipt

        validation = validate_judgment_receipt(
            envelope,
            execution_record=record,
            execution_resolver=execution_resolver,
        )
    except (OSError, ValueError, TypeError, ImportError, json.JSONDecodeError) as exc:
        _write_json(
            result_path,
            {
                "status": "partial",
                "errors": [str(exc)],
                "warnings": [],
                "judgment_status": "repair",
                "execution_status": "record_invalid",
                "execution_record_fingerprint": record.get("record_fingerprint"),
                "claim_boundary": "No reader-judgment pass is claimed when current evidence or execution binding fails validation.",
            },
        )
        return {
            "check": "reader-judgment-owner",
            "status": "repair",
            "preparation_status": "provided",
            "judgment_status": "repair",
            "execution_status": "record_invalid",
            "terminal_reason": str(exc),
            "artifact": None,
            "input": str(input_path),
            "runtime_outputs": [request_path.name, result_path.name],
            "claim_boundary": "No reader-judgment pass is claimed when current evidence or execution binding fails validation.",
        }

    _write_json(result_path, validation)
    passed = validation.get("status") == "current_pass"
    return {
        "check": "reader-judgment-owner",
        "status": "passed" if passed else "repair",
        "preparation_status": "provided",
        "judgment_status": validation.get("status", "partial"),
        "execution_status": "completed",
        "execution_record_fingerprint": record.get("record_fingerprint"),
        "artifact": validation.get("artifact_fingerprint"),
        "input": str(input_path),
        "runtime_outputs": [request_path.name, result_path.name],
        "claim_boundary": (
            "This owner validates one externally produced judgment against the current artifact and execution record. "
            "It does not generalize that judgment to other artifacts or prove that the provider's qualitative assessment is infallible."
        ),
    }


def _check_dependency_producer(root: Path, runtime: Path, producer_id: str) -> dict[str, Any]:
    """Consume the current producer output without starting another model.

    The quality producer owns all 48 writer and 48 judge calls.  This consumer
    verifies the producer's immutable manifest and re-resolves every judge
    capture against its local ``attempts`` root; it does not recalculate a
    preference or silently select a recent run directory.
    """

    result_path = runtime / "reader-quality-judgment-result.json"
    output_root = runtime
    index_path = Path(__import__("os").environ.get("LW_VALIDATION_DEPENDENCY_INDEX", str(runtime / "dependency-index.json"))).expanduser().resolve()
    errors: list[str] = []
    try:
        index = _load_json(index_path)
        if not isinstance(index, dict) or index.get("consumer_check_id") != producer_id:
            raise ValueError("dependency index does not identify the requested producer")
        from _common import fingerprint

        if index.get("index_fingerprint") != fingerprint(
            {key: value for key, value in index.items() if key != "index_fingerprint"}
        ):
            raise ValueError("producer dependency index fingerprint is stale")
        manifest_locator = index.get("producer_output_manifest_path") or "output-manifest.json"
        manifest_path = (index_path.parent / Path(str(manifest_locator))).resolve()
        manifest_path.relative_to(index_path.parent.resolve())
        manifest = _load_json(manifest_path)
        if not isinstance(manifest, dict) or manifest.get("producer_check_id") != producer_id:
            raise ValueError("producer output manifest is missing or belongs to another owner")
        if manifest.get("manifest_fingerprint") != fingerprint(
            {key: value for key, value in manifest.items() if key != "manifest_fingerprint"}
        ):
            raise ValueError("producer output manifest fingerprint is stale")
        if manifest.get("terminal_status") != "completed" or manifest.get("evidence_mode") != "real_execution":
            raise ValueError("producer output is incomplete or protocol-only")
        rows_path = manifest_path.parent / "judges.json"
        writers_path = manifest_path.parent / "writers.json"
        judges = _load_json(rows_path)
        writers = _load_json(writers_path)
        if not isinstance(judges, list) or len(judges) != 48:
            raise ValueError("producer must expose exactly 48 judge rows")
        if not isinstance(writers, list) or len(writers) != 48:
            raise ValueError("producer must expose exactly 48 writer rows")
        capture_root = manifest_path.parent / "attempts"
        plan = _load_json(manifest_path.parent / "benchmark_plan.json")
        if not isinstance(plan, dict):
            raise ValueError("producer benchmark plan is missing or invalid")
        if plan.get("source_manifest_fingerprint") != manifest.get("source_manifest_fingerprint"):
            raise ValueError("producer benchmark plan is stale for its source manifest")
        # Reuse the quality consumer's canonical row validators here.  The
        # reader owner must establish the same all-capture boundary as the
        # quality consumer: exact case/repeat keys, unique writer contexts,
        # artifact maps, blind pair bindings, raw judge JSON, and local
        # execution captures.  Checking only 48 status flags would allow a
        # duplicated or protocol-shaped row to masquerade as independent
        # evidence.
        from check_writing_quality_run import _validate_judge_rows, _validate_writer_rows

        writer_index = _validate_writer_rows(manifest_path.parent, writers, plan=plan)
        _validate_judge_rows(manifest_path.parent, judges, writers=writer_index, plan=plan)
        report = {
            "check": "reader-judgment-owner",
            "status": "passed",
            "preparation_status": "dependency_producer",
            "judgment_status": "current_pass",
            "execution_status": "completed",
            "producer_check_id": producer_id,
            "writer_count": len(writers),
            "judge_count": len(judges),
            "output_manifest": str(manifest_path),
            "claim_boundary": "All producer writer/judge captures are locally verified; qualitative preference remains the separate quality consumer's claim.",
        }
    except (OSError, ValueError, TypeError, ImportError, json.JSONDecodeError) as exc:
        report = {
            "check": "reader-judgment-owner",
            "status": "repair",
            "preparation_status": "dependency_producer",
            "judgment_status": "repair",
            "execution_status": "record_invalid",
            "producer_check_id": producer_id,
            "errors": [str(exc)],
            "claim_boundary": "No reader-judgment pass is claimed when the producer dependency is missing or stale.",
        }
    _write_json(result_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--input", type=Path, help="current judgment envelope JSON")
    parser.add_argument("--execution-record", type=Path, help="raw or dispatch_judge execution record JSON")
    parser.add_argument("--execution-capture-root", type=Path, help="owner run root containing the immutable local execution capture")
    parser.add_argument("--backend", help="explicit authorized backend module:function")
    parser.add_argument("--dependency-producer", help="consume one current producer dependency index")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        backend = _load_backend(args.backend)
        report = check(
            args.root,
            args.runtime_root,
            input_path=args.input,
            execution_record_path=args.execution_record,
            execution_capture_root=args.execution_capture_root,
            backend=backend,
            dependency_producer=args.dependency_producer,
        )
    except (OSError, ValueError, TypeError, ImportError, json.JSONDecodeError) as exc:
        report = {
            "check": "reader-judgment-owner",
            "status": "repair",
            "preparation_status": "not_run",
            "judgment_status": "repair",
            "execution_status": "record_invalid",
            "terminal_reason": str(exc),
            "claim_boundary": "No reader-judgment pass is claimed when provider configuration cannot be resolved.",
        }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"reader judgment owner: {report['status']}")
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
