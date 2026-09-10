"""Provider execution boundary for writer and reader-judge calls.

Requests describe work to start.  Only the orchestrator's backend completion
record can populate a ``reader-execution-record``; callers cannot submit a
completed judgment as proof of execution.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from _common import ValidationError, fingerprint, require_mapping, require_schema


_TERMINAL_STATUSES = frozenset({"completed", "failed", "unavailable"})


def _request(request: Mapping[str, Any], role: str) -> dict[str, Any]:
    value = dict(require_mapping(request, f"{role} request"))
    forbidden = {"terminal_status", "finished_at", "output_fingerprint", "provider_completion_ref", "record_fingerprint", "judge_output", "completed", "status"}
    present = sorted(forbidden & set(value))
    if present:
        raise ValidationError(f"{role} request cannot prefill execution fields: {present}")
    value["role"] = role
    for key in ("reader_intent_fingerprint", "writer_input_fingerprint"):
        if key not in value or not isinstance(value[key], str):
            raise ValidationError(f"{role} request requires {key}")
    if role == "judge" and "rubric_fingerprint" not in value:
        raise ValidationError("judge request requires rubric_fingerprint")
    return value


def _backend_run(backend: Any, role: str, request: Mapping[str, Any]) -> Mapping[str, Any] | None:
    if backend is None:
        return None
    if callable(backend):
        result = backend(role, dict(request))
    elif hasattr(backend, "run"):
        result = backend.run(role, dict(request))
    else:
        raise ValidationError("execution backend must be callable or provide run")
    if not isinstance(result, Mapping):
        raise ValidationError("execution backend must return a mapping")
    return result


def _record_from_result(request: Mapping[str, Any], result: Mapping[str, Any], *, role: str, backend_id: str) -> dict[str, Any]:
    required = ("run_id", "context_id", "parent_orchestrator_run_id", "model_id", "started_at", "provider_completion_ref")
    missing = [key for key in required if not isinstance(result.get(key), str) or not result[key]]
    if missing:
        raise ValidationError(f"execution backend completion is missing {missing}")
    terminal_status = result.get("terminal_status")
    if not isinstance(terminal_status, str) or terminal_status not in _TERMINAL_STATUSES:
        if terminal_status is None:
            raise ValidationError("execution backend completion requires terminal_status")
        raise ValidationError(f"execution backend completion has unknown terminal_status: {terminal_status!r}")
    evaluation_mode = request.get("evaluation_mode", "single")
    pair_inputs = list(request.get("pair_inputs", []))
    input_artifact = request.get("artifact_fingerprint")
    if evaluation_mode == "pair":
        input_artifact = None
        if len(pair_inputs) != 2:
            raise ValidationError("pair judge execution requires exactly two pair_inputs")
    output = result.get("output")
    output_fp = result.get("output_fingerprint") or (fingerprint(output) if output is not None else None)
    # A failed or unavailable judge still needs a valid execution record so
    # the orchestrator can preserve the failure receipt and count the run as
    # incomplete.  ``not_applicable`` is reserved for writers by the schema;
    # accepting it on the judge path would turn an ordinary backend failure
    # into a schema error and discard the immutable capture metadata.
    judge_independence = result.get("independence_status", "independence_unverified")
    if role == "judge" and judge_independence == "not_applicable":
        judge_independence = "independence_unverified"
    record = {
        "schema_version": "1.0", "record_id": result.get("record_id", f"execution:{role}:{result['run_id']}"), "role": role,
        "backend_id": backend_id, "run_id": result["run_id"], "context_id": result["context_id"], "parent_orchestrator_run_id": result["parent_orchestrator_run_id"],
        "input_reader_intent_fingerprint": request["reader_intent_fingerprint"], "input_writer_input_fingerprint": request["writer_input_fingerprint"],
        "input_artifact_fingerprint": input_artifact, "rubric_fingerprint": request.get("rubric_fingerprint"), "model_id": result["model_id"],
        "settings_fingerprint": request.get("settings_fingerprint") or fingerprint(request.get("settings", {})), "started_at": result["started_at"], "finished_at": result.get("finished_at"),
        "terminal_status": terminal_status, "output_fingerprint": output_fp, "provider_completion_ref": result["provider_completion_ref"],
        "independence_status": "not_applicable" if role == "writer" else judge_independence,
        "evaluation_mode": evaluation_mode, "pair_inputs": pair_inputs,
        "pair_input_fingerprint": fingerprint({"reader_intent_fingerprint": request["reader_intent_fingerprint"], "rubric_fingerprint": request.get("rubric_fingerprint"), "pair_inputs": pair_inputs}) if evaluation_mode == "pair" else None,
    }
    # A real local execution backend may attach immutable capture metadata.
    # These fields are optional so protocol fixtures remain useful for unit
    # tests, but a production resolver must require and verify them before a
    # completed record can support a quality claim.
    capture_fields = (
        "execution_capture_ref", "raw_output_locator", "events_locator",
        "stderr_locator", "completion_locator", "request_fingerprint",
        "input_prompt_fingerprint", "input_prompt_locator", "raw_output_fingerprint",
        "events_fingerprint", "stderr_fingerprint", "argv_fingerprint",
        "cli_executable", "cli_executable_fingerprint", "cli_version",
        "process_id", "thread_id", "exit_code", "timed_out",
        "descendant_cleanup_confirmed", "terminal_event_type", "terminal_event_index",
        "tool_event_count", "writer_context_ids", "usage", "cost_actual",
    )
    for key in capture_fields:
        if key in result and result[key] is not None:
            record[key] = result[key]
    record["record_fingerprint"] = fingerprint(record)
    require_schema("reader-execution-record.schema.json", record, label="ReaderExecutionRecord")
    return record


def _unavailable(request: Mapping[str, Any], role: str) -> dict[str, Any]:
    return {"status": "execution_provider_unavailable", "role": role, "request_fingerprint": fingerprint(dict(request)), "record": None, "failure_reason": "execution_provider_unavailable"}


def dispatch_writer(request: Mapping[str, Any], backend: Any) -> dict[str, Any]:
    clean = _request(request, "writer")
    result = _backend_run(backend, "writer", clean)
    if result is None:
        return _unavailable(clean, "writer")
    record = _record_from_result(clean, result, role="writer", backend_id=str(result.get("backend_id", "provider")))
    return {"status": record["terminal_status"], "record": record}


def dispatch_judge(request: Mapping[str, Any], backend: Any) -> dict[str, Any]:
    clean = _request(request, "judge")
    result = _backend_run(backend, "judge", clean)
    if result is None:
        return _unavailable(clean, "judge")
    record = _record_from_result(clean, result, role="judge", backend_id=str(result.get("backend_id", "provider")))
    return {"status": record["terminal_status"], "record": record}


def validate_execution_record(record: Mapping[str, Any], resolver: Callable[[Mapping[str, Any]], Any] | Any) -> dict[str, Any]:
    value = require_mapping(record, "ReaderExecutionRecord")
    require_schema("reader-execution-record.schema.json", value, label="ReaderExecutionRecord")
    if value["record_fingerprint"] != fingerprint({key: item for key, item in value.items() if key != "record_fingerprint"}):
        raise ValidationError("ReaderExecutionRecord fingerprint is stale")
    if value["terminal_status"] == "completed" and (value["finished_at"] is None or value["output_fingerprint"] is None):
        raise ValidationError("completed execution requires finished_at and output_fingerprint")
    if value["role"] == "writer" and value["independence_status"] != "not_applicable":
        raise ValidationError("writer execution independence must be not_applicable")
    if value["role"] == "judge":
        if value["evaluation_mode"] == "pair" and len(value["pair_inputs"]) != 2:
            raise ValidationError("pair judge record must bind two writer inputs")
        if value["evaluation_mode"] == "pair":
            if [row["anonymous_label"] for row in value["pair_inputs"]] != ["X", "Y"]:
                raise ValidationError("pair inputs must preserve the explicit X then Y order")
            expected_pair = fingerprint({"reader_intent_fingerprint": value["input_reader_intent_fingerprint"], "rubric_fingerprint": value["rubric_fingerprint"], "pair_inputs": value["pair_inputs"]})
            if value["pair_input_fingerprint"] != expected_pair:
                raise ValidationError("pair input fingerprint does not bind the current ordered pair")
        if value["evaluation_mode"] == "single" and value["pair_inputs"]:
            raise ValidationError("single judge record cannot bind pair inputs")
        if value["terminal_status"] == "completed":
            if callable(resolver):
                verified = resolver(value)
            elif hasattr(resolver, "resolve"):
                verified = resolver.resolve(value)
            else:
                raise ValidationError("execution resolver must be callable or provide resolve")
            if value["independence_status"] == "verified" and not verified:
                raise ValidationError("resolver cannot verify this judge execution")
            if value["independence_status"] == "verified" and isinstance(verified, Mapping):
                contexts = set(verified.get("writer_context_ids", []))
                if value["context_id"] in contexts:
                    raise ValidationError("judge context must differ from every writer context")
            if value["evaluation_mode"] == "single" and value["independence_status"] == "verified":
                contexts = list(value.get("writer_context_ids", []))
                if len(contexts) != 1 or not isinstance(contexts[0], str):
                    raise ValidationError("single judge must bind one writer context")
                if value["context_id"] == contexts[0]:
                    raise ValidationError("single judge context must differ from its writer context")
    return value


__all__ = ["dispatch_writer", "dispatch_judge", "validate_execution_record"]
