"""Read-only quality consumer for a completed local benchmark.

The consumer never starts Codex and never fills missing scores.  It validates
the producer manifest, current frozen plan, byte hashes, 48 writer/48 judge
counts, and the explicit nine-of-twelve quality gate.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = ROOT / "skills" / "logic-writing" / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

from _common import fingerprint, fingerprint_without  # noqa: E402
from execution_record_resolver import LocalExecutionRecordResolver  # noqa: E402
from reader_execution import validate_execution_record  # noqa: E402
from reader_pipeline import validate_artifact_map, validate_writer_input  # noqa: E402
from production_reader_pipeline import validate_reader_spine  # noqa: E402
from researchguard_handoff import validate_handoff_consumption  # noqa: E402
from run_writing_quality_benchmark import (  # noqa: E402
    CASE_COUNT,
    CASE_ORDER,
    HELD_OUT_CASE_IDS,
    HELD_OUT_VERSION,
    REPEATS,
    VERSIONS,
    _bytes_fp,
    _extract_json,
    _execution_policy,
    _held_out_quality_passes,
    _implementation_identity,
    _load_held_out_inputs,
    _pair_writer_input_fingerprint,
    _read_json,
    _validate_judgment_payload,
    _validate_single_judgment_payload,
    _write_json,
)


def _is_link(path: Path) -> bool:
    """Treat symlinks and Windows reparse junctions as untrusted evidence."""

    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


def _path(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise ValueError("producer manifest path is not a safe relative path")
    candidate = root / Path(value)
    if _is_link(candidate) or any(_is_link(parent) for parent in candidate.parents):
        raise ValueError(f"producer manifest file is symlinked: {value}")
    resolved = candidate.resolve()
    resolved.relative_to(root.resolve())
    if not resolved.is_file():
        raise ValueError(f"producer manifest file is missing or symlinked: {value}")
    return resolved


def _execution_capture_path(run_root: Path, locator: Any) -> Path:
    """Resolve a backend capture locator below the owner run's attempts root."""

    return _path((run_root / "attempts").resolve(), locator)


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


def _production_file(value: Any, root: Path, *, label: str) -> Path:
    """Resolve one production-reader evidence file without following links.

    Production refs are deliberately absolute so a consumer can audit the
    exact file the producer used.  The consumer still anchors every ref to
    the writer's own ``production-reader`` directory and rejects reparse/link
    indirection before reading bytes.
    """

    if not isinstance(value, (str, Path)) or not Path(value).is_absolute():
        raise ValueError(f"{label} must be an absolute production-reader path")
    path = Path(value)
    root = root.resolve()
    if _is_link(path) or any(_is_link(parent) for parent in path.parents):
        raise ValueError(f"{label} is symlinked")
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} escaped its production-reader root") from exc
    if not resolved.is_file():
        raise ValueError(f"{label} is missing")
    return resolved


def _production_json(root: Path, name: str) -> dict[str, Any]:
    path = _production_file(root / name, root, label=name)
    value = _read_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"production-reader {name} must be an object")
    return value


def _validate_production_ref(ref: Any, root: Path, *, label: str) -> Path:
    if not isinstance(ref, Mapping):
        raise ValueError(f"production-reader ref {label} is not an object")
    locator = ref.get("locator")
    recorded = ref.get("fingerprint")
    path = _production_file(locator, root, label=f"production-reader ref {label}")
    if not isinstance(recorded, str) or recorded != _bytes_fp(path.read_bytes()):
        raise ValueError(f"production-reader ref {label} has a stale byte fingerprint")
    return path


def _validate_planner_record(
    record: Mapping[str, Any],
    *,
    stage: str,
    production: Mapping[str, Any],
    production_root: Path,
    attempts_root: Path,
    writer_record: Mapping[str, Any],
    expected_writing_request: Mapping[str, Any],
    expected_boundaries: Mapping[str, Any],
    expected_composition: Mapping[str, Any] | None = None,
) -> None:
    """Validate one nested planner execution and its two raw captures."""

    if record.get("schema_version") != "logic-writing.planner-execution-record.v1":
        raise ValueError(f"planner {stage} record schema is stale")
    if record.get("terminal_status") != "completed":
        raise ValueError(f"planner {stage} execution is not completed")
    run_id = str(record.get("run_id") or "")
    context_id = str(record.get("context_id") or "")
    if not run_id or not context_id:
        raise ValueError(f"planner {stage} execution has no run/context identity")
    raw_path = _production_file(record.get("raw_output_locator"), production_root, label=f"planner {stage} raw output")
    raw_fingerprint = record.get("raw_output_fingerprint")
    if raw_fingerprint != _bytes_fp(raw_path.read_bytes()):
        raise ValueError(f"planner {stage} raw output fingerprint is stale")

    staged = _production_json(production_root, f"planner-{stage}.json")
    if staged.get("stage") != stage:
        raise ValueError(f"planner {stage} staged envelope has the wrong stage")
    staged_record = staged.get("execution_record")
    if not isinstance(staged_record, Mapping) or dict(staged_record) != dict(record):
        raise ValueError(f"planner {stage} staged record differs from the writer lineage")
    inputs = staged.get("inputs")
    payload = staged.get("payload")
    if not isinstance(inputs, Mapping) or not isinstance(payload, Mapping):
        raise ValueError(f"planner {stage} staged envelope is incomplete")
    if inputs.get("writing_request") != expected_writing_request or inputs.get("content_boundaries") != expected_boundaries:
        raise ValueError(f"planner {stage} inputs are not bound to the production writing request: {stage}")
    if stage == "compose" and (expected_composition is None or payload.get("composition_plan") != expected_composition):
        raise ValueError("planner compose payload is not the consumed CompositionPlan")
    if record.get("input_fingerprint") != fingerprint(dict(inputs)):
        raise ValueError(f"planner {stage} input fingerprint is stale")
    try:
        raw_payload = _read_json(raw_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"planner {stage} raw output is not JSON") from exc
    if raw_payload != dict(payload):
        raise ValueError(f"planner {stage} raw output differs from its staged payload")

    # The planner adapter also records the backend's original capture.  It is
    # outside the production-reader root by design, but must stay inside the
    # writer attempt root and retain its exact byte hash.
    capture_locator = record.get("backend_capture_locator")
    capture_fingerprint = record.get("backend_capture_fingerprint")
    if not isinstance(capture_locator, str) or not capture_locator:
        raise ValueError(f"planner {stage} has no backend raw capture locator")
    capture_path = Path(capture_locator)
    if not capture_path.is_absolute():
        capture_path = attempts_root / capture_path
    else:
        capture_path = capture_path
    if _is_link(capture_path) or any(_is_link(parent) for parent in capture_path.parents):
        raise ValueError(f"planner {stage} backend raw capture is symlinked")
    try:
        capture_path = capture_path.resolve()
        capture_path.relative_to(attempts_root.resolve())
    except (OSError, ValueError) as exc:
        raise ValueError(f"planner {stage} backend capture escaped attempts root") from exc
    if not capture_path.is_file():
        raise ValueError(f"planner {stage} backend raw capture is missing or symlinked")
    if not isinstance(capture_fingerprint, str) or capture_fingerprint != _bytes_fp(capture_path.read_bytes()):
        raise ValueError(f"planner {stage} backend capture fingerprint is stale")
    if record.get("backend_id") != writer_record.get("backend_id"):
        raise ValueError(f"planner {stage} backend identity differs from writer execution")


def _validate_production_reader_lineage(
    run_root: Path,
    row: Mapping[str, Any],
    *,
    require_writer_request_binding: bool = True,
) -> None:
    """Validate the native planner -> reader -> writer chain for one writer.

    This is intentionally consumer-side validation.  A producer status flag
    alone cannot establish that the writer used the exact ReaderBrief,
    CompositionPlan, semantic handoff, ConsumptionBinding, and two completed
    planner captures that were persisted beside its artifact.
    """

    key = _writer_key(row)
    production = row.get("production_reader")
    if not isinstance(production, Mapping):
        raise ValueError(f"writer row has no production_reader lineage: {key}")
    artifact_path = _path(run_root, row.get("artifact_path"))
    writer_dir = artifact_path.parent
    production_root = writer_dir / "production-reader"
    if not production_root.is_dir() or _is_link(production_root):
        raise ValueError(f"writer production-reader root is missing or symlinked: {key}")
    production_root = production_root.resolve()
    if production.get("status") != "ready_for_writer":
        raise ValueError(f"writer production reader is not ready_for_writer: {key}")
    attempts_root = (run_root / "attempts").resolve()
    request = row.get("request")
    writer_record = row.get("record")
    if not isinstance(request, Mapping) or not isinstance(writer_record, Mapping):
        raise ValueError(f"writer row lacks request/record for production lineage: {key}")

    if require_writer_request_binding:
        if production.get("writer_request_fingerprint") != row.get("request_fingerprint"):
            raise ValueError(f"writer production reader is not bound to its request fingerprint: {key}")
    writer_input_fp = request.get("writer_input_fingerprint")
    if not isinstance(writer_input_fp, str) or production.get("writer_input_fingerprint") != writer_input_fp:
        raise ValueError(f"writer production reader has a stale WriterInput fingerprint: {key}")
    if request.get("reader_intent_fingerprint") != writer_record.get("input_reader_intent_fingerprint"):
        raise ValueError(f"writer production reader has a stale ReaderIntent request binding: {key}")

    production_envelope_path = _production_file(
        production_root / "production-reader-input.json",
        production_root,
        label="production-reader-input.json",
    )
    production_doc = _read_json(production_envelope_path)
    if not isinstance(production_doc, Mapping):
        raise ValueError(f"production-reader-input.json must be an object: {key}")
    recorded_production_fp = production.get("production_reader_fingerprint")
    if not isinstance(recorded_production_fp, str) or recorded_production_fp != _bytes_fp(production_envelope_path.read_bytes()):
        raise ValueError(f"writer production-reader envelope fingerprint is stale: {key}")
    if production_doc.get("schema_version") != "logic-writing.production-reader-input.v1":
        raise ValueError(f"writer production-reader envelope schema is stale: {key}")
    if production_doc.get("status") != production.get("status"):
        raise ValueError(f"writer production-reader status differs from its row: {key}")
    for field in (
        "writer_input_fingerprint", "request_fingerprint", "content_fingerprint",
        "source_fingerprint", "reader_spine_fingerprint", "reader_spine_schema",
        "refs", "planner_execution_records", "provider_identity",
    ):
        if production_doc.get(field) != production.get(field):
            raise ValueError(f"writer production-reader {field} differs from its row: {key}")
    if production_doc.get("writer_input_fingerprint") != fingerprint(production_doc.get("writer_input")):
        raise ValueError(f"writer production-reader WriterInput bytes are stale: {key}")
    if production_doc.get("writer_input_fingerprint") != writer_input_fp:
        raise ValueError(f"writer request and production WriterInput differ: {key}")

    refs = production.get("refs")
    if not isinstance(refs, Mapping) or not refs:
        raise ValueError(f"writer production-reader refs are missing: {key}")
    required_refs = {"reader_brief", "composition_plan", "semantic_handoff", "consumption_binding", "reader_spine"}
    if not required_refs <= set(refs):
        raise ValueError(f"writer production-reader refs omit reader lineage artifacts: {key}")
    ref_paths = {name: _validate_production_ref(ref, production_root, label=str(name)) for name, ref in refs.items()}
    for name in required_refs:
        expected_path = (production_root / f"{name}.json").resolve()
        if ref_paths[name] != expected_path:
            raise ValueError(f"writer production-reader ref {name} points at a foreign file: {key}")

    request_doc = _production_json(production_root, "request.json")
    writing_request = request_doc.get("writing_request")
    boundaries = request_doc.get("content_boundaries")
    if not isinstance(writing_request, Mapping) or not isinstance(boundaries, Mapping):
        raise ValueError(f"writer production request envelope is incomplete: {key}")
    if writing_request.get("request_fingerprint") != production.get("request_fingerprint"):
        raise ValueError(f"writer production request fingerprint is stale: {key}")
    production_intent = writing_request.get("reader_intent")
    if not isinstance(production_intent, Mapping):
        raise ValueError(f"writer production request has no ReaderIntent: {key}")
    if production_intent.get("intent_fingerprint") != request.get("reader_intent_fingerprint"):
        raise ValueError(f"writer production ReaderIntent differs from writer request: {key}")
    if production.get("content_fingerprint") != fingerprint(dict(boundaries)):
        raise ValueError(f"writer production content boundary fingerprint is stale: {key}")

    # Research runs before the native provider's selected Limitation rows are
    # promoted into the reader boundary.  The request snapshot is refreshed
    # after that promotion so compose sees the final boundary.  Reconstruct
    # the research-stage view from the immutable promotion artifact instead of
    # comparing both planner stages with the post-promotion snapshot.
    research_boundaries = copy.deepcopy(dict(boundaries))
    native_limitations_ref = refs.get("native_limitations")
    if native_limitations_ref is not None:
        native_limitations_path = _validate_production_ref(
            native_limitations_ref,
            production_root,
            label="native_limitations",
        )
        native_limitations_doc = _read_json(native_limitations_path)
        promoted_rows = native_limitations_doc.get("rows")
        if not isinstance(promoted_rows, list):
            raise ValueError(f"writer native limitations artifact is incomplete: {key}")
        promoted_ids = {
            str(row.get("limitation_id"))
            for row in promoted_rows
            if isinstance(row, Mapping) and str(row.get("limitation_id") or "").strip()
        }
        if len(promoted_ids) != len(promoted_rows):
            raise ValueError(f"writer native limitations artifact has invalid ids: {key}")
        research_boundaries["limitations"] = [
            row
            for row in research_boundaries.get("limitations", [])
            if not isinstance(row, Mapping)
            or str(row.get("limitation_id") or "") not in promoted_ids
        ]

    brief = _production_json(production_root, "reader_brief.json")
    composition = _production_json(production_root, "composition_plan.json")
    handoff = _production_json(production_root, "semantic_handoff.json")
    binding = _production_json(production_root, "consumption_binding.json")
    reader_spine = _production_json(production_root, "reader_spine.json")
    try:
        validate_reader_spine(reader_spine)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(f"writer reader spine is invalid: {key}") from exc
    if production_doc.get("reader_spine") != reader_spine:
        raise ValueError(f"writer production ReaderSpine differs from its receipt: {key}")
    if production_doc.get("reader_spine_fingerprint") != fingerprint(reader_spine):
        raise ValueError(f"writer production ReaderSpine fingerprint is stale: {key}")
    if production.get("reader_spine_fingerprint") != fingerprint(reader_spine):
        raise ValueError(f"writer row ReaderSpine fingerprint is stale: {key}")
    if request.get("reader_spine_fingerprint") != production.get("reader_spine_fingerprint"):
        raise ValueError(f"writer request is not bound to its ReaderSpine: {key}")

    # The writer's captured prompt must contain the validated spine JSON and
    # no card-level or internal model projection.  This closes the consumer
    # boundary even when a caller writes a plausible production receipt.
    # Execution-capture locators are rooted at ``attempts``.  Production
    # evidence paths are rooted at the writer's ``production-reader`` folder,
    # while the backend prompt/events/output captures live beside the
    # completion receipt under ``run_root/attempts``.  Resolving this locator
    # from ``run_root`` silently points at a non-existent sibling and makes a
    # valid held-out/full capture fail consumer validation.
    prompt_path = _execution_capture_path(run_root, writer_record.get("input_prompt_locator"))
    prompt_text = prompt_path.read_text(encoding="utf-8")
    if any(token in prompt_text for token in (
        '"selected_content"', '"route_semantics"', '"gaps"', '"native_handoff"',
        '"model_row_ids"', 'WriterInput', "LogicGuard", "FlowGuard",
    )):
        raise ValueError(f"writer production prompt contains private/card-level fields: {key}")
    try:
        prompt_spine = json.loads(prompt_text.rsplit("\n\n", 1)[-1])
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"writer production prompt does not end with ReaderSpine JSON: {key}") from exc
    if prompt_spine != reader_spine:
        raise ValueError(f"writer production prompt ReaderSpine differs from receipt: {key}")
    if brief.get("composition_plan") != composition:
        raise ValueError(f"writer ReaderBrief embeds a different CompositionPlan: {key}")
    if brief.get("writer_input") != production_doc.get("writer_input"):
        raise ValueError(f"writer ReaderBrief embeds a different WriterInput: {key}")
    if brief.get("writer_input_fingerprint") != writer_input_fp or brief.get("writer_input_fingerprint") != fingerprint(brief.get("writer_input")):
        raise ValueError(f"writer ReaderBrief WriterInput fingerprint is stale: {key}")
    if brief.get("reader_intent_fingerprint") != brief.get("reader_intent", {}).get("intent_fingerprint"):
        raise ValueError(f"writer ReaderBrief ReaderIntent fingerprint is stale: {key}")
    if brief.get("reader_intent_fingerprint") != request.get("reader_intent_fingerprint"):
        raise ValueError(f"writer ReaderBrief is not bound to its request ReaderIntent: {key}")
    if brief.get("brief_fingerprint") != fingerprint_without(dict(brief), "brief_fingerprint"):
        raise ValueError(f"writer ReaderBrief fingerprint is stale: {key}")
    if composition.get("plan_fingerprint") != fingerprint_without(dict(composition), "plan_fingerprint"):
        raise ValueError(f"writer CompositionPlan fingerprint is stale: {key}")
    if brief.get("composition_plan", {}).get("plan_fingerprint") != composition.get("plan_fingerprint"):
        raise ValueError(f"writer ReaderBrief CompositionPlan binding is stale: {key}")

    if handoff.get("handoff_fingerprint") != fingerprint_without(dict(handoff), "handoff_fingerprint"):
        raise ValueError(f"writer semantic handoff fingerprint is stale: {key}")
    if handoff.get("reader_intent_fingerprint") != request.get("reader_intent_fingerprint"):
        raise ValueError(f"writer semantic handoff is not bound to its request ReaderIntent: {key}")
    if binding.get("handoff_fingerprint") != handoff.get("handoff_fingerprint"):
        raise ValueError(f"writer ConsumptionBinding handoff binding is stale: {key}")
    if binding.get("brief_fingerprint") != brief.get("brief_fingerprint"):
        raise ValueError(f"writer ConsumptionBinding ReaderBrief binding is stale: {key}")
    # ConsumptionBinding intentionally fingerprints the complete persisted
    # CompositionPlan (including its own plan_fingerprint); this differs from
    # the plan's self-fingerprint used by ReaderBrief.
    if binding.get("composition_plan_fingerprint") != fingerprint(composition):
        raise ValueError(f"writer ConsumptionBinding CompositionPlan binding is stale: {key}")
    if binding.get("writer_input_fingerprint") != writer_input_fp:
        raise ValueError(f"writer ConsumptionBinding WriterInput binding is stale: {key}")
    if binding.get("binding_fingerprint") != fingerprint_without(dict(binding), "binding_fingerprint"):
        raise ValueError(f"writer ConsumptionBinding fingerprint is stale: {key}")
    try:
        validate_writer_input(production_doc.get("writer_input"), reader_brief=brief, composition_plan=composition)
        validate_handoff_consumption(binding, handoff, brief, binding.get("unit_mapping"))
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError(f"writer production reader contract validation failed: {key}") from exc

    planner_records = production.get("planner_execution_records")
    if not isinstance(planner_records, list) or len(planner_records) != 2 or any(not isinstance(item, Mapping) for item in planner_records):
        raise ValueError(f"writer production reader must contain exactly two planner executions: {key}")
    by_stage: dict[str, Mapping[str, Any]] = {}
    for item in planner_records:
        run_id = str(item.get("run_id") or "")
        stage = run_id.split(":", 2)[1] if run_id.startswith("planner:") and len(run_id.split(":", 2)) == 3 else ""
        if stage not in {"research", "compose"} or stage in by_stage:
            raise ValueError(f"writer planner execution stages are not research/compose: {key}")
        by_stage[stage] = item
    planner_run_ids = {str(item.get("run_id")) for item in planner_records}
    planner_context_ids = {str(item.get("context_id")) for item in planner_records}
    if len(planner_run_ids) != 2 or len(planner_context_ids) != 2:
        raise ValueError(f"writer planner execution identities are reused: {key}")
    if str(writer_record.get("run_id") or "") in planner_run_ids or str(writer_record.get("context_id") or "") in planner_context_ids:
        raise ValueError(f"writer planner execution reuses the writer identity: {key}")
    for stage in ("research", "compose"):
        _validate_planner_record(
            by_stage[stage], stage=stage, production=production, production_root=production_root,
            attempts_root=attempts_root, writer_record=writer_record,
            expected_writing_request=writing_request,
            expected_boundaries=research_boundaries if stage == "research" else boundaries,
            expected_composition=composition if stage == "compose" else None,
        )


def _status_counts(items: Any) -> dict[str, int]:
    rows = list(items) if isinstance(items, list) else []
    statuses = [str(item.get("status")) for item in rows if isinstance(item, Mapping)]
    not_started_statuses = {
        "queued",
        "not_started_dependency_failed",
        "not_started_deadline",
        "not_started_cleanup_blocked",
    }
    terminal_statuses = {
        "completed",
        "failed",
        "timed_out",
        "cancelled",
        "not_started_dependency_failed",
        "not_started_deadline",
        "not_started_cleanup_blocked",
    }
    terminal = sum(status in terminal_statuses for status in statuses)
    completed = sum(status == "completed" for status in statuses)
    failed = sum(status in {"failed", "timed_out", "cancelled"} for status in statuses)
    not_started = sum(status in not_started_statuses for status in statuses)
    return {
        "planned": len(rows),
        "terminal": terminal,
        "completed": completed,
        "failed": failed,
        "not_started": not_started,
    }


def _validate_execution_accounting(
    run_root: Path,
    *,
    plan: Mapping[str, Any],
    result: Mapping[str, Any],
    manifest: Mapping[str, Any] | None = None,
) -> None:
    """Ensure totals include nested planners while jobs stay schedulable.

    ``planned-ledger.jobs`` is the set of directly scheduled writer/judge
    jobs.  ``nested_planner_executions`` is the per-writer research/compose
    work performed inside the repaired/current writer process.  The total
    progress and execution counts include both collections.
    """

    ledger = _read_json(run_root / "planned-ledger.json")
    if not isinstance(ledger, Mapping):
        raise ValueError("planned ledger is not an object")
    jobs = ledger.get("jobs")
    nested = ledger.get("nested_planner_executions")
    if not isinstance(jobs, list) or not isinstance(nested, list):
        raise ValueError("planned ledger must separate scheduled jobs and nested planner executions")
    planned_writers = int(plan.get("planned_writer_count", 0))
    planned_judges = int(plan.get("planned_judge_count", 0))
    planned_planners = int(plan.get("planned_planner_count", 0))
    if len(jobs) != planned_writers + planned_judges:
        raise ValueError("planned ledger scheduled job count is stale")
    if len(nested) != planned_planners:
        raise ValueError("planned ledger nested planner count is stale")
    expected_total = planned_writers + planned_judges + planned_planners
    planned_counts = ledger.get("planned_counts")
    if not isinstance(planned_counts, Mapping) or planned_counts.get("scheduled_jobs") != len(jobs) or planned_counts.get("nested_planner_executions") != len(nested) or planned_counts.get("planned_execution_count") != expected_total:
        raise ValueError("planned ledger count breakdown is stale")
    progress = ledger.get("progress")
    if not isinstance(progress, Mapping) or progress.get("planned") != expected_total:
        raise ValueError("planned ledger total progress is stale")
    scheduled_progress = _status_counts(jobs)
    nested_progress = _status_counts(nested)
    if progress.get("scheduled") != scheduled_progress or progress.get("nested_planner") != nested_progress:
        raise ValueError("planned ledger scheduled/nested progress is stale")
    for field, value in (
        ("terminal", scheduled_progress["terminal"] + nested_progress["terminal"]),
        ("completed", scheduled_progress["completed"] + nested_progress["completed"]),
        ("failed", scheduled_progress["failed"] + nested_progress["failed"]),
        ("not_started", scheduled_progress["not_started"] + nested_progress["not_started"]),
    ):
        if progress.get(field) != value:
            raise ValueError(f"planned ledger {field} progress is stale")
    if result.get("planned_execution_count") != expected_total:
        raise ValueError("run result planned_execution_count is stale")
    actual_writer = int(result.get("actual_writer_count", 0))
    actual_judge = int(result.get("actual_judge_count", 0))
    actual_planner = int(result.get("actual_planner_count", 0))
    if result.get("actual_execution_count") != actual_writer + actual_judge + actual_planner:
        raise ValueError("run result actual execution count is stale")
    if manifest is not None:
        if manifest.get("planned_execution_count") != expected_total:
            raise ValueError("output manifest planned_execution_count is stale")
        if manifest.get("planned_writer_count") != planned_writers or manifest.get("planned_judge_count") != planned_judges or manifest.get("planned_planner_count") != planned_planners:
            raise ValueError("output manifest planned count breakdown is stale")
        if manifest.get("actual_execution_count") != result.get("actual_execution_count"):
            raise ValueError("output manifest actual execution count is stale")


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
        if key[2] == "repaired":
            _validate_production_reader_lineage(run_root, row)
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


def _held_out_prompt_path(run_root: Path, record: Mapping[str, Any]) -> Path:
    locator = record.get("input_prompt_locator")
    root = (run_root / "attempts").resolve()
    if not isinstance(locator, str) or not locator:
        raise ValueError("held-out writer execution has no prompt locator")
    path = (root / Path(locator)).resolve()
    path.relative_to(root)
    if path.is_symlink() or not path.is_file():
        raise ValueError("held-out writer prompt capture is missing or symlinked")
    return path


def _validate_held_out_writer_rows(
    run_root: Path,
    writers: list[Any],
    *,
    plan: Mapping[str, Any],
    cases: list[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    """Validate one current artifact for each frozen holdout request."""

    expected = {(str(case["case_id"]), 1, HELD_OUT_VERSION) for case in cases}
    if len(writers) != len(expected):
        raise ValueError(f"producer does not contain exactly {len(expected)} held-out writer rows")
    resolver = LocalExecutionRecordResolver(
        run_root / "attempts",
        expected_cli_version=str(plan.get("cli_version") or "") or None,
        expected_cli_sha256=str(plan.get("cli_sha256") or "") or None,
        expected_backend_id=str(plan.get("backend_id") or "") or None,
    )
    index: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    contexts: set[str] = set()
    run_ids: set[str] = set()
    case_ids = {str(case["case_id"]) for case in cases}
    for row in writers:
        if not isinstance(row, Mapping):
            raise ValueError("held-out writers contain a non-object row")
        key = _writer_key(row)
        if key in index:
            raise ValueError(f"held-out producer contains duplicate writer row: {key}")
        if key not in expected or key[0] not in case_ids:
            raise ValueError(f"held-out producer contains an unexpected writer row: {key}")
        if row.get("status") != "completed" or not isinstance(row.get("record"), Mapping):
            raise ValueError(f"held-out writer row is not a completed captured execution: {key}")
        request = row.get("request")
        if not isinstance(request, Mapping):
            raise ValueError(f"held-out writer row has no persisted request: {key}")
        expected_run_id = f"writer:{key[0]}:{key[1]}:{key[2]}"
        if row.get("request_fingerprint") != fingerprint(dict(request)):
            raise ValueError(f"held-out writer request fingerprint is stale: {key}")
        if request.get("request_id") != expected_run_id or request.get("run_id") != expected_run_id:
            raise ValueError(f"held-out writer request identity is not bound to its row key: {key}")
        record = row["record"]
        _record_request_matches(record, request, role="writer")
        if record.get("run_id") != expected_run_id:
            raise ValueError(f"held-out writer execution run id is not bound to its row key: {key}")
        validate_execution_record(record, resolver)
        context = str(record.get("context_id") or "")
        run_id = str(record.get("run_id") or "")
        if not context or context in contexts:
            raise ValueError(f"held-out writer contexts are missing or reused: {key}")
        if not run_id or run_id in run_ids:
            raise ValueError(f"held-out writer run ids are missing or reused: {key}")
        contexts.add(context)
        run_ids.add(run_id)
        # The writer/prompt boundary is intentionally visible to the
        # consumer: holdout case id, oracle, rubric, and expected answer must
        # never be sent into the model context.
        prompt_text = _held_out_prompt_path(run_root, record).read_text(encoding="utf-8")
        lowered = prompt_text.casefold()
        forbidden = {key[0].casefold(), "oracle", "rubric", "expected answer", "expected_answer"}
        if any(token in lowered for token in forbidden):
            raise ValueError(f"held-out writer prompt contains audit-only input: {key}")
        if row.get("artifact_fingerprint") != record.get("output_fingerprint"):
            raise ValueError(f"held-out writer artifact is not bound to execution output: {key}")
        artifact_path = _path(run_root, row.get("artifact_path"))
        artifact_text = artifact_path.read_text(encoding="utf-8")
        if row.get("artifact_text") != artifact_text:
            raise ValueError(f"held-out writer row text differs from artifact: {key}")
        artifact_map = _read_json(artifact_path.with_name("artifact-map.json"))
        validate_artifact_map(artifact_map)
        if Path(str(artifact_map.get("artifact_path"))).resolve() != artifact_path:
            raise ValueError(f"held-out ArtifactMap points at a different file: {key}")
        if artifact_map.get("artifact_fingerprint") != row.get("artifact_fingerprint"):
            raise ValueError(f"held-out ArtifactMap fingerprint is stale: {key}")
        if row.get("artifact_map_fingerprint") != artifact_map.get("map_fingerprint"):
            raise ValueError(f"held-out writer map fingerprint is stale: {key}")
        _validate_production_reader_lineage(run_root, row)
        index[key] = row
    if set(index) != expected:
        raise ValueError("held-out writer rows do not exhaust the frozen four-key universe")
    return index


def _validate_held_out_judge_rows(
    run_root: Path,
    judges: list[Any],
    *,
    writers: Mapping[tuple[str, int, str], Mapping[str, Any]],
    plan: Mapping[str, Any],
    cases: list[Mapping[str, Any]],
) -> None:
    """Validate two independent single-article reviews for every artifact."""

    expected = {
        (str(case["case_id"]), 1, judge_index)
        for case in cases
        for judge_index in (1, 2)
    }
    if len(judges) != len(expected):
        raise ValueError(f"producer does not contain exactly {len(expected)} held-out judge rows")
    resolver = LocalExecutionRecordResolver(
        run_root / "attempts",
        expected_cli_version=str(plan.get("cli_version") or "") or None,
        expected_cli_sha256=str(plan.get("cli_sha256") or "") or None,
        expected_backend_id=str(plan.get("backend_id") or "") or None,
    )
    seen: set[tuple[str, int, int]] = set()
    contexts_by_case: dict[str, set[str]] = {}
    judge_thread_ids: set[str] = set()
    for row in judges:
        if not isinstance(row, Mapping):
            raise ValueError("held-out judges contain a non-object row")
        key = _judge_key(row)
        if key in seen:
            raise ValueError(f"held-out producer contains duplicate judge row: {key}")
        if key not in expected:
            raise ValueError(f"held-out producer contains an unexpected judge row: {key}")
        seen.add(key)
        if row.get("status") != "completed" or not isinstance(row.get("record"), Mapping):
            raise ValueError(f"held-out judge row is not a completed captured execution: {key}")
        writer = writers.get((key[0], 1, HELD_OUT_VERSION))
        if not isinstance(writer, Mapping) or not isinstance(writer.get("record"), Mapping):
            raise ValueError(f"held-out judge references a missing writer: {key}")
        writer_record = writer["record"]
        request = row.get("request")
        record = row["record"]
        if not isinstance(request, Mapping):
            raise ValueError(f"held-out judge row has no persisted request: {key}")
        expected_run_id = f"judge:{key[0]}:{key[1]}:{key[2]}"
        if row.get("request_fingerprint") != fingerprint(dict(request)):
            raise ValueError(f"held-out judge request fingerprint is stale: {key}")
        if request.get("request_id") != expected_run_id or request.get("run_id") != expected_run_id:
            raise ValueError(f"held-out judge request identity is not bound to its row key: {key}")
        _record_request_matches(record, request, role="judge")
        if record.get("run_id") != expected_run_id:
            raise ValueError(f"held-out judge execution run id is not bound to its row key: {key}")
        if request.get("evaluation_mode") != "single" or record.get("evaluation_mode") != "single":
            raise ValueError(f"held-out judge is not a single-article evaluation: {key}")
        if request.get("pair_inputs") or record.get("pair_inputs"):
            raise ValueError(f"held-out judge contains synthetic pair inputs: {key}")
        artifact_fp = str(writer.get("artifact_fingerprint") or "")
        if request.get("artifact_fingerprint") != artifact_fp or record.get("input_artifact_fingerprint") != artifact_fp:
            raise ValueError(f"held-out judge is bound to the wrong artifact: {key}")
        writer_context = str(writer_record.get("context_id") or "")
        expected_contexts = [writer_context]
        if request.get("writer_context_ids") != expected_contexts or record.get("writer_context_ids") != expected_contexts:
            raise ValueError(f"held-out judge has a stale writer context binding: {key}")
        validate_execution_record(record, resolver)
        if record.get("independence_status") != "verified" or record.get("context_id") == writer_context:
            raise ValueError(f"held-out judge context is not independent: {key}")
        judge_context = str(record.get("context_id") or "")
        if not judge_context or judge_context in contexts_by_case.setdefault(key[0], set()):
            raise ValueError(f"held-out judge contexts are reused: {key}")
        contexts_by_case[key[0]].add(judge_context)
        thread_id = str(record.get("thread_id") or "")
        if not thread_id or thread_id in judge_thread_ids:
            raise ValueError(f"held-out judge thread identity is missing or reused: {key}")
        judge_thread_ids.add(thread_id)
        raw_output_locator = record.get("raw_output_locator")
        root = (run_root / "attempts").resolve()
        raw_path = (root / Path(str(raw_output_locator))).resolve()
        raw_path.relative_to(root)
        if raw_path.is_symlink() or not raw_path.is_file():
            raise ValueError(f"held-out judge output capture is missing: {key}")
        raw_text = raw_path.read_text(encoding="utf-8")
        if row.get("raw_output") != raw_text:
            raise ValueError(f"held-out judge row text differs from its captured output: {key}")
        parsed = _validate_single_judgment_payload(_extract_json(raw_text))
        if parsed.get("artifact_fingerprint") != artifact_fp:
            raise ValueError(f"held-out judgment payload has a stale artifact fingerprint: {key}")
        if row.get("judgment") != parsed or row.get("judgment_fingerprint") != fingerprint(parsed):
            raise ValueError(f"held-out judge row judgment is not the captured JSON payload: {key}")
    if seen != expected:
        raise ValueError("held-out judge rows do not exhaust the frozen eight-key universe")
    if any(len(values) != 2 for values in contexts_by_case.values()):
        raise ValueError("each held-out artifact must have two distinct judge contexts")


def _check_held_out_run(
    root: Path,
    *,
    plan_path: Path,
    run_root: Path,
    pair_plan: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Read-only validation for the separate four-case holdout receipt."""

    errors: list[str] = []
    try:
        plan_input = _read_json(plan_path.resolve())
        plan = _read_json(run_root / "benchmark_plan.json")
        manifest = _read_json(run_root / "output-manifest.json")
        result = _read_json(run_root / "run_result.json")
        summary = _read_json(run_root / "summary.json")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return {
            "status": "failed",
            "held_out_passed": False,
            "errors": [f"held-out producer output unavailable: {exc}"],
        }
    if not all(isinstance(value, dict) for value in (plan_input, plan, manifest, result, summary)):
        errors.append("held-out plan, manifest, result, and summary must all be objects")
        plan_input = plan_input if isinstance(plan_input, dict) else {}
        plan = plan if isinstance(plan, dict) else {}
        manifest = manifest if isinstance(manifest, dict) else {}
        result = result if isinstance(result, dict) else {}
        summary = summary if isinstance(summary, dict) else {}
    if plan.get("mode") != "held_out" or plan.get("benchmark_id") != "logic-writing-held-out-4x1x2":
        errors.append("held-out run is not the current four-case mode")
    if manifest.get("schema_version") != "logic-writing.execution-quality-output.v1":
        errors.append("held-out output manifest schema is not current")
    if manifest.get("producer_check_id") != "check.reader.execution-quality-producer":
        errors.append("held-out output manifest belongs to a different owner")
    if manifest.get("mode") != "held_out":
        errors.append("held-out output manifest does not declare held_out mode")
    if manifest.get("manifest_fingerprint") != _manifest_fingerprint(manifest):
        errors.append("held-out output manifest fingerprint is stale")
    if manifest.get("evidence_mode") != "real_execution":
        errors.append("protocol-only held-out output cannot satisfy the consumer")
    materialized_plan = plan
    if manifest.get("frozen_plan_fingerprint") != fingerprint(plan):
        errors.append("held-out output is bound to a different frozen plan")
        try:
            materialized = _read_json(run_root / "benchmark_plan.json")
        except (OSError, UnicodeError, json.JSONDecodeError):
            materialized = None
        if isinstance(materialized, dict) and manifest.get("frozen_plan_fingerprint") == fingerprint(materialized):
            materialized_plan = materialized
    if materialized_plan.get("mode") != "held_out":
        errors.append("held-out materialized plan mode is stale")
    if plan_input.get("model_id") and any(materialized_plan.get(key) != plan_input.get(key) for key in ("model_id", "reasoning_effort", "cli_version", "cli_sha256")):
        errors.append("held-out materialized plan changed the portable backend settings")
    try:
        _validate_execution_accounting(
            run_root,
            plan=materialized_plan,
            result=result,
            manifest=manifest,
        )
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(f"held-out execution accounting is stale: {exc}")
    try:
        held_out_cases, _, input_fp, source_fp, _ = _load_held_out_inputs(root / "tests" / "fixtures" / "writing_quality")
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        held_out_cases, input_fp, source_fp = [], None, None
        errors.append(f"held-out input manifest is invalid: {exc}")
    if held_out_cases:
        if materialized_plan.get("case_order") != [case["case_id"] for case in held_out_cases]:
            errors.append("held-out plan case order is stale")
        if materialized_plan.get("input_manifest_fingerprint") != input_fp:
            errors.append("held-out input manifest fingerprint is stale")
        if materialized_plan.get("source_manifest_fingerprint") != source_fp or manifest.get("source_manifest_fingerprint") != source_fp:
            errors.append("held-out source manifest fingerprint is stale")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        errors.append("held-out output manifest has no files")
    else:
        for item in files:
            if not isinstance(item, Mapping):
                errors.append("held-out manifest contains a non-object file entry")
                continue
            try:
                path = _path(run_root, item.get("path"))
                if item.get("sha256") != _bytes_fp(path.read_bytes()):
                    errors.append(f"held-out file hash mismatch: {item.get('path')}")
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
    try:
        writers = _read_json(run_root / "writers.json")
        judges = _read_json(run_root / "judges.json")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        writers, judges = [], []
        errors.append(f"held-out rows are unreadable: {exc}")
    writer_index: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    if not isinstance(writers, list) or not isinstance(judges, list):
        errors.append("held-out writers.json and judges.json must be arrays")
    elif held_out_cases:
        try:
            writer_index = _validate_held_out_writer_rows(run_root, writers, plan=materialized_plan, cases=held_out_cases)
            _validate_held_out_judge_rows(run_root, judges, writers=writer_index, plan=materialized_plan, cases=held_out_cases)
            judges_by_case: dict[str, list[Mapping[str, Any]]] = {}
            for judge in judges:
                if isinstance(judge, Mapping) and isinstance(judge.get("judgment"), Mapping):
                    judges_by_case.setdefault(str(judge.get("case_id")), []).append(judge["judgment"])
            for case in held_out_cases:
                case_id = str(case["case_id"])
                writer = writer_index.get((case_id, 1, HELD_OUT_VERSION))
                artifact_fp = str(writer.get("artifact_fingerprint") or "") if isinstance(writer, Mapping) else ""
                if not _held_out_quality_passes(judges_by_case.get(case_id, []), artifact_fingerprint=artifact_fp):
                    errors.append(f"held-out case {case_id} fails the dual-judge absolute quality gate")
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            errors.append(f"held-out capture validation failed: {exc}")
    try:
        expected_planner_count = int(materialized_plan.get("planned_planner_count", len(held_out_cases) * 2))
        actual_planner_count = int(result.get("actual_planner_count", 0))
    except (TypeError, ValueError):
        expected_planner_count = len(held_out_cases) * 2
        actual_planner_count = -1
        errors.append("held-out production chain planner count is not an integer")
    if actual_planner_count != expected_planner_count:
        errors.append("held-out production chain planner count does not match the planned two-stage executions")
    if manifest.get("planner_count") is not None:
        try:
            manifest_planner_count = int(manifest.get("planner_count", 0))
        except (TypeError, ValueError):
            manifest_planner_count = -1
        if manifest_planner_count != actual_planner_count:
            errors.append("held-out manifest planner_count is stale")
    if manifest.get("terminal_status") != "completed":
        errors.append("held-out producer terminal status is not completed")
    if result.get("summary_fingerprint") != fingerprint(summary):
        errors.append("held-out result summary fingerprint is stale")
    if result.get("held_out_passed") is not True or summary.get("status") != "passed" or summary.get("held_out_passed") is not True:
        errors.append("all four held-out cases did not pass the dual-judge absolute gate")
    if pair_plan is not None:
        for key in ("implementation_fingerprint", "execution_policy_fingerprint", "backend_id", "model_id", "reasoning_effort", "cli_version", "cli_sha256"):
            if materialized_plan.get(key) != pair_plan.get(key):
                errors.append(f"held-out {key} does not match the main quality run")
    status = "passed" if not errors else "failed"
    return {
        "status": status,
        "held_out_passed": status == "passed",
        "errors": errors,
        "writer_count": manifest.get("writer_count"),
        "judge_count": manifest.get("judge_count"),
        "planner_count": manifest.get("planner_count"),
        "summary_fingerprint": manifest.get("summary_fingerprint"),
        "claim_boundary": "Four frozen holdout artifacts, each reviewed by two independent single-article judges; no pair-comparison or universal claim.",
    }


def check(
    root: Path,
    *,
    plan_path: Path,
    run_root: Path,
    dependency_producer: str | None = None,
    held_out_run_root: Path | None = None,
) -> dict[str, Any]:
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
        result = result if isinstance(result, dict) else {}
        summary = summary if isinstance(summary, dict) else {}
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
    # A receipt's materialized plan is historical evidence.  Recompute the
    # current implementation and policy identity from the repository before
    # reopening captures; copying the plan's own values here would let a stale
    # receipt certify a changed backend, consumer, or provider schema.
    try:
        current_implementation_fp = fingerprint(_implementation_identity(root))
        current_policy_fp = fingerprint(_execution_policy(effective_plan))
    except (OSError, UnicodeError, ValueError, TypeError):
        current_implementation_fp = None
        current_policy_fp = None
        errors.append("current implementation or execution policy identity is unavailable")
    for key, expected in (
        ("implementation_fingerprint", current_implementation_fp),
        ("execution_policy_fingerprint", current_policy_fp),
    ):
        if expected is None or effective_plan.get(key) != expected:
            errors.append(f"producer output {key} is stale")
        if manifest.get(key) != expected:
            errors.append(f"producer manifest {key} is stale")
        if result.get(key) != expected:
            errors.append(f"producer run result {key} is stale")
    if dependency_producer and dependency_producer != manifest.get("producer_check_id"):
        errors.append("dependency producer does not match the current output")
    try:
        _validate_execution_accounting(
            run_root,
            plan=effective_plan,
            result=result,
            manifest=manifest,
        )
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(f"producer execution accounting is stale: {exc}")
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
    pair_report = {
        "status": status,
        "errors": errors,
        "quality_claim_status": "passed" if status == "passed" else "incomplete",
        "writer_count": manifest.get("writer_count"), "judge_count": manifest.get("judge_count"),
        "improved_case_count": summary.get("improved_case_count"),
    }
    report: dict[str, Any] = {
        "check": "writing-quality-run", "status": status, "errors": errors,
        "quality_claim_status": "passed" if status == "passed" else "incomplete",
        "writer_count": manifest.get("writer_count"), "judge_count": manifest.get("judge_count"),
        "improved_case_count": summary.get("improved_case_count"),
        "producer_output_manifest_fingerprint": manifest.get("manifest_fingerprint"),
        "claim_boundary": "This consumer checks one bounded twelve-case local comparison; it does not generalize the result to arbitrary topics or models.",
        # Without a holdout root this is intentionally the only quality
        # conclusion exposed by the consumer.
        "pair_comparison": pair_report,
    }
    if held_out_run_root is not None:
        held_out_report = _check_held_out_run(
            root,
            plan_path=plan_path,
            run_root=held_out_run_root.resolve(),
            pair_plan=effective_plan if isinstance(effective_plan, Mapping) else None,
        )
        combined_errors = [*errors, *[str(item) for item in held_out_report.get("errors", [])]]
        product_passed = status == "passed" and held_out_report.get("status") == "passed"
        report.update({
            "errors": combined_errors,
            "status": "passed" if product_passed else "failed",
            "quality_claim_status": "passed" if product_passed else "incomplete",
            "held_out": held_out_report,
            "held_out_passed": bool(held_out_report.get("held_out_passed")),
            "product_quality_passed": product_passed,
            "product_path_verified": product_passed,
        })
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--plan", type=Path, required=False)
    parser.add_argument("--run-root", type=Path, required=False)
    parser.add_argument("--held-out-run-root", type=Path, required=False)
    parser.add_argument("--dependency-producer")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    plan = args.plan or (args.root / "tests/fixtures/writing_quality/local-backend-plan.json")
    run_root = args.run_root or Path(__import__("os").environ.get("LW_VALIDATION_ATTEMPT_ROOT", str(args.root / "run-artifacts" / "reader-execution-quality-producer")))
    report = check(
        args.root,
        plan_path=plan,
        run_root=run_root,
        dependency_producer=args.dependency_producer,
        held_out_run_root=args.held_out_run_root,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"writing quality consumer: {report['status']}")
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
