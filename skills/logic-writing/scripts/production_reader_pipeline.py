"""Prepare the real reader projection through the installed ResearchGuard console.

The planner is a model-execution adapter, called twice with keyword arguments
``stage``, ``inputs`` and ``evidence_root``. ``research`` materializes a native
target inputs and returns guard_declaration, candidate_model, support_files
(relative JSON paths to known-good/bad payloads), selection_request, and budget.
The native console freezes the declaration before candidate creation and binds
the candidate itself. ``compose``
receives the actual native result and returns composition_plan,
route_composition, and native_handoff_mapping. Both calls return
``{payload, execution_record}``; the record binds input_fingerprint and an
actual JSON raw_output_locator/raw_output_fingerprint to that exact payload.

This module does not invent a research model, a depth receipt, or prose. The
native owner verifies target-purpose and recursive depth; a planner that has
not prepared that target cannot produce a writer packet. Test doubles belong
at the process boundary in tests, never on a second runtime provider path.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping

from _common import ValidationError, fingerprint, fingerprint_without, require_mapping
from build_source_unit_manifest import fingerprint_bytes
import provider_preflight
from reader_pipeline import (
    _canonical_plan_order,
    build_reader_brief,
    utc_now,
    validate_writing_request,
    validate_writer_input,
)
from researchguard_handoff import build_researchguard_handoff, bind_handoff_consumption, validate_handoff_consumption
from select_route import select_route


SCHEMA = "logic-writing.production-reader-input.v1"
READER_SPINE_SCHEMA = "logic-writing.reader-spine.v1"
READER_DIAGNOSTIC_SCHEMA = "logic-writing.reader-quality-diagnostics.v1"
PROVIDER_VERSION = provider_preflight.SUPPORTED_RESEARCHGUARD_VERSION
_RESEARCH_KEYS = {"guard_declaration", "candidate_model", "support_files", "selection_request", "budget"}
_COMPOSE_KEYS = {"composition_plan", "route_composition", "native_handoff_mapping"}
_PLANNER_RECORD_SCHEMA = "logic-writing.planner-execution-record.v1"
_PLANNER_MODE = "offline_input_only"
_BOUNDARY_KEYS = {
    "content_units",
    "evidence_anchors",
    "alternatives",
    "limitations",
    "citation_duties",
    "must_preserve_tokens",
    "verbatim_obligations",
    "prohibited_overclaims",
}
# These fields describe a benchmark, judge, or expected answer.  They are
# useful to a quality harness, but are facts from outside the writing request
# and therefore cannot cross the planner input boundary.
_FORBIDDEN_PLANNER_FACT_KEYS = {
    "case_id",
    "rubric",
    "oracle",
    "expected",
    "expected_answer",
    "reference_answer",
    "gold",
    "gold_answer",
    "judge",
    "judge_preferences",
    "score",
    "benchmark",
    "comparison_label",
    "quality_label",
    "preferred_answer",
    "fixture_label",
}
_SAFE_PLANNER_EVENT_TYPES = {
    "thread.started",
    "turn.started",
    "turn.completed",
    "agent_message",
    "reasoning",
}
_PLANNER_EVENT_RISK_TOKENS = {
    "tool",
    "command",
    "shell",
    "browser",
    "web",
    "mcp",
    "function_call",
    "function.call",
}

# The production writer receives this projection.  The immutable full
# WriterInput remains in the private ReaderBrief/evidence record and is
# validated by reader_pipeline.validate_writer_input before this projection is
# compiled.  Keep the public projection allow-listed so a newly-added private
# field cannot cross the writer boundary by accident.
_READER_SPINE_KEYS = {
    "schema_version",
    "root_question",
    "root_conclusion",
    "artifact_form",
    "opening_job",
    "conclusion_job",
    "reader_context",
    "major_units",
    "evidence_anchors",
    "editorial_dispositions",
    "conclusion_sensitive_limitations",
}
_READER_CONTEXT_KEYS = {
    "language", "audience", "purpose", "artifact_mode", "artifact_format",
    "heading_policy", "list_policy", "table_policy", "citation_policy",
    "style", "extent", "required_content", "forbidden_content",
}
_READER_CONTENT_DISPOSITIONS = {"support", "merge", "omit"}
_READER_MATERIALITIES = {
    "changes_answer", "changes_action", "changes_scope", "changes_strength",
}
_READER_SPINE_PRIVATE_KEYS = {
    "writer_input", "selected_content", "route_semantics", "gaps",
    "native_handoff", "native_handoff_mapping", "model_row_ids", "model_id",
    "model_ids", "status", "execution_record", "execution_records", "receipt",
    "receipts", "ledger", "ledgers", "citations", "private_receipt",
    "private_receipts", "evidence_ledger", "authority_ledger",
}
_READER_SPINE_LEAK = re.compile(
    r"\b(?:SourceGuard|LogicGuard|TraceGuard|FlowGuard|current_pass|"
    r"reader_intent_fingerprint|composition_plan_fingerprint|repair_request|"
    r"native_handoff|model ledger|execution record|private receipt)\b|"
    r"(?:本段|本节|本章)(?:旨在|将会|负责)|(?:以下段落|下一节)(?:将会|负责)",
    re.IGNORECASE,
)
_DISCLAIMER = re.compile(
    r"(?:不意味着|不代表|不能据此|不可据此|需要指出|需要注意|需注意|仅在|"
    r"does not mean|cannot therefore|should not be read|it should be noted)",
    re.IGNORECASE,
)
_TRANSITION_ONLY = re.compile(
    r"^(?:(?:因此|由此|接下来|下一步|随后|此外|不过|然而|总之|这意味着|"
    r"therefore|next|however|in turn|this leads to|consequently)[，,:：;；。.!！?？\s]*){1,3}$",
    re.IGNORECASE,
)
_LIST_ITEM = re.compile(r"^\s*(?:[-*+•◦▪‣]\s+|\d+[.)、]\s*|[一二三四五六七八九十]+、\s*)")
_FICTION_REQUEST = re.compile(
    r"小说|故事|场景|受限视角|近距离第三人称|fiction|story|scene|restricted\s+viewpoint|close\s+third|pov",
    re.IGNORECASE,
)
_FICTION_AUTHOR_META = re.compile(
    r"尚无交代|不能写成(?:他|她|人物)?(?:此刻)?的所知|这一后果不能|作者(?:解释|说明)|解释主题|"
    r"the\s+author|the\s+theme|cannot\s+be\s+known|no\s+explanation\s+is\s+given|"
    r"this\s+consequence\s+cannot",
    re.IGNORECASE,
)
_TRAVEL_REQUEST = re.compile(
    r"旅行|旅客|行程|雨天|指南|方案|travel|traveler|itinerary|guide|rainy",
    re.IGNORECASE,
)
_TRAVEL_FAILURE_TRIGGER = re.compile(
    r"到馆后|入口|座位|失效|不可用|到达后|if\s+.*(?:entrance|seat|unavailable)|"
    r"once\s+.*(?:unavailable|fails)",
    re.IGNORECASE,
)
_TRAVEL_NEGATIVE = re.compile(r"不能|不可|不应|无法|不得|cannot|must\s+not|should\s+not|do\s+not|not\s+reliable", re.IGNORECASE)
_TRAVEL_ACTION = re.compile(
    r"核实|留在|停留|返回|回旅馆|折返|不出发|改为|停止|等待|verify|stay|remain|return|go\s+back|"
    r"do\s+not\s+depart|stop|wait|fallback",
    re.IGNORECASE,
)
_TRAVEL_EXECUTABLE_ACTION = re.compile(
    r"应(?:当|该)?|可以|请|先留在|留在|停留|回到|返回|不出发|核实后再|"
    r"should|can|please|stay|remain|return|go\s+back|do\s+not\s+depart|verify\s+before",
    re.IGNORECASE,
)


class ProductionPipelineBlocked(ValidationError):
    def __init__(self, code: str, detail: Any):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def _inside(value: Any, root: Path, *, directory: bool = False) -> Path:
    if not isinstance(value, (str, Path)) or not Path(value).is_absolute():
        raise ProductionPipelineBlocked("native_input_path_invalid", "absolute path required")
    path = Path(value)
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ProductionPipelineBlocked("native_input_path_invalid", str(path)) from exc
    if any(item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()) for item in [path, *path.parents]):
        raise ProductionPipelineBlocked("native_input_path_invalid", "links are not native input authority")
    if (directory and not path.is_dir()) or (not directory and not path.is_file()):
        raise ProductionPipelineBlocked("native_input_path_invalid", str(path))
    return path.resolve()


def _read(path: Path) -> dict[str, Any]:
    try:
        return dict(require_mapping(json.loads(path.read_text(encoding="utf-8")), str(path)))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ProductionPipelineBlocked("native_payload_unreadable", str(path)) from exc


def _ref(path: Path) -> dict[str, str]:
    return {"locator": str(path.resolve()), "fingerprint": fingerprint_bytes(path.read_bytes())}


def _check_ref(ref: Mapping[str, str], root: Path) -> None:
    path = _inside(ref["locator"], root)
    if _ref(path) != ref:
        raise ProductionPipelineBlocked("production_input_stale", ref["locator"])


def _destination(relative: Any, root: Path) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or any(part in {"..", "."} for part in Path(relative).parts):
        raise ProductionPipelineBlocked("native_input_path_invalid", "a bounded relative target path is required")
    path = root / relative
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ProductionPipelineBlocked("native_input_path_invalid", relative) from exc
    if path.exists():
        raise ProductionPipelineBlocked("native_input_path_invalid", "target paths cannot overwrite existing files")
    return path


def _source_identity() -> dict[str, str]:
    skill = Path(__file__).parents[1]
    paths = (
        [skill / "SKILL.md"]
        + sorted((skill / "scripts").glob("*.py"))
        + sorted((skill / "assets" / "schemas").glob("*.json"))
        + sorted((skill / "references").rglob("*.md"))
        + sorted((skill / "references").rglob("*.json"))
        + sorted((skill / "routes").rglob("*.md"))
        + sorted((skill / "routes").rglob("*.json"))
    )
    unique_paths = dict.fromkeys(path.resolve() for path in paths if path.is_file())
    return {
        path.relative_to(skill).as_posix(): fingerprint_bytes(path.read_bytes())
        for path in unique_paths
    }


def _validate_planner_facts(value: Any) -> dict[str, Any]:
    """Validate the facts that may enter either planner invocation.

    The production planner is allowed to transform the request and frozen
    content boundaries only.  Benchmark labels and judge material are a
    separate authority surface and must be rejected before the first planner
    call, including when they are nested inside an otherwise valid boundary.
    """

    boundaries = dict(require_mapping(value, "frozen content boundaries"))
    missing = sorted(_BOUNDARY_KEYS - set(boundaries))
    extra = sorted(set(boundaries) - _BOUNDARY_KEYS)
    if missing or extra:
        raise ProductionPipelineBlocked(
            "planner_input_boundary_invalid",
            {"missing": missing, "unsupported": extra},
        )

    def walk(item: Any, path: str) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ProductionPipelineBlocked("planner_input_boundary_invalid", f"{path} has a non-string key")
                if key.casefold() in _FORBIDDEN_PLANNER_FACT_KEYS:
                    raise ProductionPipelineBlocked("planner_input_forbidden_field", f"{path}.{key}")
                walk(child, f"{path}.{key}")
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f"{path}[{index}]")

    walk(boundaries, "content_boundaries")
    units = boundaries.get("content_units")
    if not isinstance(units, list) or not units:
        raise ProductionPipelineBlocked("planner_input_boundary_invalid", "content_units must be a non-empty array")
    for index, unit in enumerate(units):
        if not isinstance(unit, Mapping) or not str(unit.get("safe_meaning", "")).strip():
            raise ProductionPipelineBlocked(
                "planner_input_boundary_invalid",
                f"content_units[{index}] must contain a non-empty safe_meaning",
            )
    return boundaries


def _merge_native_limitations(boundaries: Mapping[str, Any], native_plan: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Promote native material limitations into the reader boundary.

    LogicGuard can identify a limitation while selecting a valid argument
    unit.  Keeping that row only in the private native plan leaves the writer
    with an apparently complete conclusion job and invites author-facing
    explanation.  This adapter copies only selected ``Limitation`` rows into
    the current content boundary; it does not invent a remedy or change the
    native result.
    """

    result = copy.deepcopy(dict(boundaries))
    existing_rows = [
        dict(row) for row in result.get("limitations", [])
        if isinstance(row, Mapping) and row.get("limitation_id")
    ]
    existing_ids = {str(row["limitation_id"]) for row in existing_rows}
    content_ids = [
        str(row["content_unit_id"])
        for row in result.get("content_units", [])
        if isinstance(row, Mapping) and row.get("content_unit_id")
    ]
    promoted: list[dict[str, Any]] = []
    selected_items = native_plan.get("selected_items", []) if isinstance(native_plan, Mapping) else []
    if not isinstance(selected_items, list):
        selected_items = []
    for raw in selected_items:
        if not isinstance(raw, Mapping) or str(raw.get("node_type") or "") != "Limitation":
            continue
        node_id = str(raw.get("node_id") or "").strip()
        text = str(raw.get("text") or raw.get("limitation") or "").strip()
        if not node_id or not text:
            continue
        limitation_id = f"limitation:native:{node_id}"
        if limitation_id in existing_ids:
            continue
        row = {
            "limitation_id": limitation_id,
            "safe_meaning": text,
            "affected_content_unit_ids": list(content_ids),
            "required_placement": "conclusion",
        }
        existing_rows.append(row)
        existing_ids.add(limitation_id)
        promoted.append(row)
    result["limitations"] = existing_rows
    return result, promoted


def _external_file(value: Any, label: str) -> Path:
    """Resolve an absolute execution artifact without accepting links."""

    if not isinstance(value, (str, Path)) or not Path(value).is_absolute():
        raise ProductionPipelineBlocked("planner_lineage_incomplete", f"{label} must be an absolute path")
    path = Path(value)
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ProductionPipelineBlocked("planner_lineage_incomplete", f"{label}: {path}") from exc
    if any(
        item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction())
        for item in [path, *path.parents]
    ):
        raise ProductionPipelineBlocked("planner_lineage_incomplete", f"{label} cannot use links")
    if not resolved.is_file():
        raise ProductionPipelineBlocked("planner_lineage_incomplete", f"{label}: {resolved}")
    return resolved


def _read_planner_events(record: Mapping[str, Any], stage: str) -> tuple[Path, bytes]:
    """Check the terminal planner event stream and prove it used no tools."""

    capture = _external_file(record.get("backend_capture_locator"), "backend_capture_locator")
    capture_bytes = capture.read_bytes()
    if record.get("backend_capture_fingerprint") != fingerprint_bytes(capture_bytes):
        raise ProductionPipelineBlocked("planner_lineage_stale", {"stage": stage, "artifact": str(capture)})

    # LocalCodexBackend emits output.txt and events.jsonl in one run directory.
    # Deriving the event path from the immutable capture locator prevents a
    # planner from selecting a clean, unrelated event stream.
    events_path = _external_file(capture.with_name("events.jsonl"), "backend events")
    events_bytes = events_path.read_bytes()
    events: list[Mapping[str, Any]] = []
    for index, line in enumerate(events_bytes.splitlines()):
        if not line.strip():
            continue
        try:
            event = json.loads(line.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise ProductionPipelineBlocked("planner_lineage_invalid", {"stage": stage, "line": index + 1}) from exc
        if not isinstance(event, Mapping):
            raise ProductionPipelineBlocked("planner_lineage_invalid", {"stage": stage, "line": index + 1})
        events.append(event)
        event_type = str(event.get("type", "")).casefold()
        item = event.get("item")
        item_type = str(item.get("type", "")).casefold() if isinstance(item, Mapping) else ""
        if event_type in {"turn.failed", "turn.error", "turn.aborted", "error"}:
            raise ProductionPipelineBlocked("planner_execution_failed", {"stage": stage, "event": event_type})
        if event_type in {"item.started", "item.completed"} and not item_type:
            raise ProductionPipelineBlocked("planner_lineage_invalid", {"stage": stage, "reason": "typed item required"})
        # The local execution backend may retain a diagnostic item with
        # ``item.type == error`` while the surrounding turn completes.  It is
        # not a tool invocation; top-level error/failed events above remain
        # terminal failures.
        if item_type == "error":
            continue
        if any(token in event_type for token in _PLANNER_EVENT_RISK_TOKENS) or any(
            token in item_type for token in _PLANNER_EVENT_RISK_TOKENS
        ):
            raise ProductionPipelineBlocked("planner_tools_forbidden", {"stage": stage, "event": event_type or item_type})
        if item_type and item_type not in _SAFE_PLANNER_EVENT_TYPES:
            raise ProductionPipelineBlocked("planner_tools_forbidden", {"stage": stage, "item": item_type})

    threads = [event for event in events if event.get("type") == "thread.started"]
    if len(threads) != 1 or not str(threads[0].get("thread_id", "")).strip():
        raise ProductionPipelineBlocked("planner_lineage_invalid", {"stage": stage, "reason": "one thread.started required"})
    if str(threads[0]["thread_id"]) != str(record.get("context_id")):
        raise ProductionPipelineBlocked("planner_lineage_invalid", {"stage": stage, "reason": "thread/context mismatch"})
    if not any(event.get("type") == "turn.completed" for event in events):
        raise ProductionPipelineBlocked("planner_lineage_invalid", {"stage": stage, "reason": "turn.completed required"})
    if not any(
        isinstance(event.get("item"), Mapping) and event["item"].get("type") == "agent_message"
        for event in events
    ):
        raise ProductionPipelineBlocked("planner_lineage_invalid", {"stage": stage, "reason": "agent message required"})
    return events_path, events_bytes


def _validate_planner_record(record_value: Mapping[str, Any], *, stage: str, context_fp: str) -> dict[str, Any]:
    record = dict(record_value)
    if record.get("schema_version") != _PLANNER_RECORD_SCHEMA:
        raise ProductionPipelineBlocked("planner_record_invalid", "current execution record schema required")
    if record.get("terminal_status") != "completed":
        raise ProductionPipelineBlocked("planner_execution_failed", {"stage": stage, "status": record.get("terminal_status")})
    run_id = record.get("run_id")
    context_id = record.get("context_id")
    if (
        not isinstance(run_id, str)
        or not run_id.startswith(f"planner:{stage}:")
        or not isinstance(context_id, str)
        or not context_id.strip()
        or record.get("input_fingerprint") != context_fp
        or not isinstance(record.get("backend_id"), str)
        or not record["backend_id"].strip()
        or not isinstance(record.get("claim_scope"), str)
        or not record["claim_scope"].strip()
    ):
        raise ProductionPipelineBlocked("planner_record_invalid", "current input, run, context, backend and claim scope required")
    events_path, events_bytes = _read_planner_events(record, stage)
    record["planner_mode"] = _PLANNER_MODE
    record["tool_event_count"] = 0
    record["events_locator"] = str(events_path)
    record["events_fingerprint"] = fingerprint_bytes(events_bytes)
    return record


class InstalledResearchGuardProvider:
    """The sole runtime provider. Resolves distribution-owned console metadata.

    No executable, provider-root, module-import, or fallback override is accepted.
    Run the application in the intended environment to select its installation.
    """

    def __init__(self, *, timeout_seconds: float = 120, cleanup_timeout_seconds: float = 10):
        if not 0 < timeout_seconds <= 900:
            raise ValueError("native timeout must be in (0, 900]")
        if not 0 < cleanup_timeout_seconds <= 120:
            raise ValueError("native cleanup timeout must be in (0, 120]")
        self.timeout_seconds = timeout_seconds
        self.cleanup_timeout_seconds = cleanup_timeout_seconds

    def _console(self) -> tuple[str, dict[str, Any]]:
        report = provider_preflight.preflight("logicguard")
        if report.get("status") != "current_pass":
            raise ProductionPipelineBlocked("native_provider_unavailable", report)
        distribution = provider_preflight._researchguard_distribution()
        console = provider_preflight._researchguard_console(distribution)
        if distribution is None or str(distribution.version) != PROVIDER_VERSION or not console:
            raise ProductionPipelineBlocked("native_provider_identity_mismatch", report)
        return console, {"provider_id": "researchguard", "version": PROVIDER_VERSION,
                         "primary_path_id": "primary:researchguard:logic",
                         "console": _ref(Path(console)), "preflight": report}

    @staticmethod
    def _capture_bytes(value: Any) -> bytes:
        """Normalize a communicate result or TimeoutExpired partial capture.

        ``Popen(..., text=True)`` normally returns strings, while
        ``TimeoutExpired.output`` is allowed to be bytes on some Python
        versions.  The receipt must hash the bytes that were actually
        observed, regardless of which representation the subprocess layer
        returned.
        """

        if value is None:
            return b""
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            return value.encode("utf-8", errors="replace")
        return str(value).encode("utf-8", errors="replace")

    @staticmethod
    def _poll(process: Any) -> int | None:
        try:
            return process.poll()
        except (AttributeError, OSError, ValueError):
            return None

    def _write_execution_receipt(
        self,
        receipt_path: Path,
        *,
        command: list[str],
        cwd: Path,
        pid: int | None,
        started_at: str,
        finished_at: str,
        exit_code: int | None,
        terminal_status: str,
        timed_out: bool,
        timeout_stage: str | None,
        cleanup_method: str,
        cleanup_confirmed: bool,
        stdout: bytes,
        stderr: bytes,
        output: Path,
        failure_detail: str | None = None,
        cleanup_detail: str | None = None,
        process_started: bool = False,
        communicate_completed: bool = False,
    ) -> dict[str, Any]:
        """Persist one exclusive process receipt before reporting its result.

        The receipt is intentionally independent from the native JSON payload.
        A native command can exit non-zero, time out, or produce no payload;
        each case still gets one immutable sidecar with enough identity and
        byte fingerprints to audit what actually happened.
        """

        output_bytes: bytes | None = None
        output_error: str | None = None
        try:
            if output.is_file():
                output_bytes = output.read_bytes()
        except OSError as exc:
            output_error = f"{type(exc).__name__}: {exc}"
        receipt: dict[str, Any] = {
            "schema_version": "logic-writing.native-execution-receipt.v1",
            "receipt_locator": str(receipt_path.resolve()),
            "command": command,
            "command_fingerprint": fingerprint(command),
            "cwd": str(cwd.resolve()),
            "pid": pid,
            "process_started": process_started,
            "started_at": started_at,
            "finished_at": finished_at,
            "exit_code": exit_code,
            "terminal_status": terminal_status,
            "timeout": bool(timed_out),
            "timeout_seconds": self.timeout_seconds,
            "timeout_stage": timeout_stage,
            "cleanup_method": cleanup_method,
            "cleanup_confirmed": bool(cleanup_confirmed),
            "communicate_completed": communicate_completed,
            "stdout_fingerprint": fingerprint_bytes(stdout),
            "stdout_bytes": len(stdout),
            "stderr_fingerprint": fingerprint_bytes(stderr),
            "stderr_bytes": len(stderr),
            "output_fingerprint": fingerprint_bytes(output_bytes) if output_bytes is not None else None,
            "output_bytes": len(output_bytes) if output_bytes is not None else None,
            "output_locator": str(output.resolve()),
            "output_error": output_error,
            "failure_detail": failure_detail,
            "cleanup_detail": cleanup_detail,
        }
        # ``_write`` opens with ``x``.  A second write to the same execution
        # path is therefore rejected rather than silently replacing evidence.
        _write(receipt_path, receipt)
        return receipt

    def _terminate_for_timeout(self, process: Any) -> tuple[str, bool, str | None]:
        """Request bounded process-tree cleanup and return its evidence.

        The caller performs exactly one bounded final ``communicate`` after
        this request.  If that drain itself times out, the caller keeps the
        cleanup result false and fails closed; it never retries an unbounded
        pipe read.
        """

        pid = getattr(process, "pid", None)
        if pid is None:
            return "no_process_identity", False, "process pid unavailable"
        if os.name == "nt":
            try:
                result = subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    timeout=self.cleanup_timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                return "taskkill_timeout", False, f"{type(exc).__name__}: taskkill exceeded cleanup timeout"
            except (OSError, ValueError) as exc:
                return "taskkill_error", False, f"{type(exc).__name__}: {exc}"
            code = getattr(result, "returncode", None)
            if code == 0:
                return "taskkill_tree", True, None
            # A process can finish between the timeout and taskkill.  It is
            # safe to accept that only after the bounded drain confirms the
            # root is gone; the caller still checks ``poll`` before accepting.
            if self._poll(process) is not None:
                return "taskkill_process_already_exited", True, f"taskkill returncode={code}"
            return "taskkill_failed", False, f"taskkill returncode={code}"
        try:
            import signal
            os.killpg(pid, signal.SIGKILL)
            return "killpg", True, None
        except ProcessLookupError:
            return "killpg_process_already_exited", True, None
        except (OSError, ValueError) as exc:
            return "killpg_error", False, f"{type(exc).__name__}: {exc}"

    def _run(self, console: str, args: list[str], output: Path, *, cwd: Path) -> dict[str, Any]:
        if output.exists():
            raise ProductionPipelineBlocked("native_output_already_exists", str(output))
        receipt_path = output.with_suffix(".execution.json")
        if receipt_path.exists():
            raise ProductionPipelineBlocked("native_output_already_exists", str(receipt_path))
        command = [console, "logic", *args, "--output", str(output)]
        options: dict[str, Any] = {"cwd": cwd, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE,
                                   "text": True, "encoding": "utf-8", "errors": "strict"}
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            options["start_new_session"] = True

        started_at = utc_now()
        process: Any = None
        pid: int | None = None
        stdout = b""
        stderr = b""
        exit_code: int | None = None
        timed_out = False
        timeout_stage: str | None = None
        cleanup_method = "not_started"
        cleanup_confirmed = False
        cleanup_detail: str | None = None
        failure_detail: str | None = None
        communicate_completed = False
        process_started = False
        start_failed = False
        communicate_failed = False

        try:
            try:
                process = subprocess.Popen(command, **options)
                pid = getattr(process, "pid", None)
                process_started = pid is not None
                cleanup_method = "natural_exit"
            except (OSError, ValueError) as exc:
                failure_detail = f"{type(exc).__name__}: {exc}"
                start_failed = True
                raise

            try:
                raw_stdout, raw_stderr = process.communicate(timeout=self.timeout_seconds)
                stdout = self._capture_bytes(raw_stdout)
                stderr = self._capture_bytes(raw_stderr)
                communicate_completed = True
            except subprocess.TimeoutExpired as first_timeout:
                timed_out = True
                timeout_stage = "execution"
                failure_detail = f"{type(first_timeout).__name__}: native command exceeded execution timeout"
                stdout = self._capture_bytes(getattr(first_timeout, "stdout", None) or getattr(first_timeout, "output", None))
                stderr = self._capture_bytes(getattr(first_timeout, "stderr", None))
                cleanup_method, cleanup_confirmed, cleanup_detail = self._terminate_for_timeout(process)
                # The post-kill drain is always bounded.  A second timeout is
                # terminal evidence of uncertain cleanup, never an invitation
                # to call communicate again or to report a pass.
                try:
                    raw_stdout, raw_stderr = process.communicate(timeout=self.cleanup_timeout_seconds)
                    stdout = self._capture_bytes(raw_stdout) or stdout
                    stderr = self._capture_bytes(raw_stderr) or stderr
                    communicate_completed = True
                except subprocess.TimeoutExpired as second_timeout:
                    timeout_stage = "cleanup_drain"
                    cleanup_confirmed = False
                    cleanup_method = f"{cleanup_method}+communicate_timeout"
                    detail = f"{type(second_timeout).__name__}: cleanup drain exceeded cleanup timeout"
                    cleanup_detail = f"{cleanup_detail}; {detail}" if cleanup_detail else detail
                    stdout = self._capture_bytes(getattr(second_timeout, "stdout", None) or getattr(second_timeout, "output", None)) or stdout
                    stderr = self._capture_bytes(getattr(second_timeout, "stderr", None)) or stderr
            except (OSError, ValueError) as exc:
                failure_detail = f"{type(exc).__name__}: {exc}"
                cleanup_method = "communicate_error"
                cleanup_confirmed = False
                communicate_failed = True
                try:
                    if self._poll(process) is None:
                        cleanup_method, cleanup_confirmed, cleanup_detail = self._terminate_for_timeout(process)
                except (OSError, ValueError) as cleanup_exc:
                    cleanup_detail = f"{type(cleanup_exc).__name__}: {cleanup_exc}"
        finally:
            if process is not None:
                current_code = self._poll(process)
                exit_code = current_code if current_code is not None else getattr(process, "returncode", None)
                if not timed_out and communicate_completed:
                    cleanup_confirmed = exit_code is not None
                    cleanup_method = "natural_exit"
            finished_at = utc_now()
            terminal_status = "start_failed" if start_failed else "timed_out" if timed_out else "completed" if exit_code == 0 else "failed"
            self._write_execution_receipt(
                receipt_path,
                command=command,
                cwd=cwd,
                pid=pid,
                started_at=started_at,
                finished_at=finished_at,
                exit_code=exit_code,
                terminal_status=terminal_status,
                timed_out=timed_out,
                timeout_stage=timeout_stage,
                cleanup_method=cleanup_method,
                cleanup_confirmed=cleanup_confirmed,
                stdout=stdout,
                stderr=stderr,
                output=output,
                failure_detail=failure_detail,
                cleanup_detail=cleanup_detail,
                process_started=process_started,
                communicate_completed=communicate_completed,
            )

        if timed_out:
            if not cleanup_confirmed or self._poll(process) is None:
                raise ProductionPipelineBlocked("native_cleanup_unconfirmed", pid)
            raise ProductionPipelineBlocked("native_provider_timeout", args[0])
        if communicate_failed:
            raise ProductionPipelineBlocked("native_execution_capture_failed", failure_detail or args[0])
        payload = _read(output) if output.is_file() else {}
        if exit_code != 0:
            raise ProductionPipelineBlocked("native_check_blocked", payload or {"stderr": stderr.decode("utf-8", errors="replace")})
        if not payload:
            raise ProductionPipelineBlocked("native_payload_missing", str(output))
        return payload

    def research(self, prepared: Mapping[str, Any], *, evidence_root: Path) -> dict[str, Any]:
        if set(prepared) != _RESEARCH_KEYS:
            raise ProductionPipelineBlocked("native_request_invalid", sorted(set(prepared) ^ _RESEARCH_KEYS))
        if type(prepared["budget"]) is not int or prepared["budget"] < 1:
            raise ProductionPipelineBlocked("native_request_invalid", "positive native budget required")
        selection = copy.deepcopy(dict(require_mapping(prepared["selection_request"], "native selection request")))
        if selection.get("schema") != "researchguard.logic.synthesis-request.v1":
            raise ProductionPipelineBlocked("native_request_invalid", "current selection schema required")
        if selection.get("native_depth_receipt_ref"):
            raise ProductionPipelineBlocked("native_request_invalid", "caller-supplied depth receipt is forbidden")
        console, identity = self._console()
        declaration = dict(require_mapping(prepared["guard_declaration"], "native guard declaration"))
        candidate = dict(require_mapping(prepared["candidate_model"], "native candidate model"))
        supporting = require_mapping(prepared["support_files"], "native good/bad support files")
        target = evidence_root / "target"
        target.mkdir()
        declaration_path, contract = target / "declaration.json", target / "guard-contract.json"
        model = _destination(declaration.get("candidate_relative_path"), target)
        reserved = {model, declaration_path, contract, target / "freeze-result.json", target / "bind-result.json"}
        support_refs = {}
        for relative, value in supporting.items():
            path = _destination(relative, target)
            if path in reserved:
                raise ProductionPipelineBlocked("native_input_path_invalid", "support file aliases a native control/candidate path")
            _write(path, dict(require_mapping(value, "native support document")))
            support_refs["support:" + relative] = _ref(path)
        _write(declaration_path, declaration)
        self._run(console, ["guard-contract", "freeze", "--target-root", str(target), "--declaration", str(declaration_path),
                           "--contract", str(contract)], target / "freeze-result.json", cwd=target)
        if model.exists():
            raise ProductionPipelineBlocked("native_candidate_created_before_freeze", str(model))
        _write(model, candidate)
        self._run(console, ["guard-contract", "bind", "--target-root", str(target), "--contract", str(contract)], target / "bind-result.json", cwd=target)
        _inside(contract, target)
        model_ref, contract_ref = _ref(model), _ref(contract)
        receipt_path = evidence_root / "native-depth-receipt.json"
        receipt = self._run(console, ["depth", str(model), "--target-root", str(target),
                           "--guard-contract", str(contract), "--budget", str(prepared["budget"])], receipt_path, cwd=target)
        if receipt.get("receipt_version") != "researchguard.logic.depth.v3" or receipt.get("status") != "pass":
            raise ProductionPipelineBlocked("native_depth_blocked", receipt)
        if receipt.get("unresolved_gaps") or receipt.get("untested_high_impact_node_ids"):
            raise ProductionPipelineBlocked("native_depth_blocked", receipt)
        _check_ref(model_ref, target)
        _check_ref(contract_ref, target)
        selection["model_id"] = receipt["model_id"]
        selection["model_fingerprint"] = receipt["model_fingerprint"]
        selection["native_depth_receipt_ref"] = str(receipt_path)
        selection_path = evidence_root / "native-selection-request.json"
        _write(selection_path, selection)
        plan_path = evidence_root / "native-synthesis-plan.json"
        plan = self._run(console, ["synthesize", str(model), "--selection-request", str(selection_path), "--json"], plan_path, cwd=target)
        _check_ref(model_ref, target)
        _check_ref(contract_ref, target)
        if plan.get("status") != "research_handoff_ready" or plan.get("open_gaps"):
            raise ProductionPipelineBlocked("native_synthesis_blocked", plan)
        if plan.get("model_id") != receipt.get("model_id") or str(plan.get("model_fingerprint")).removeprefix("sha256:") != str(receipt.get("model_fingerprint")).removeprefix("sha256:"):
            raise ProductionPipelineBlocked("native_plan_receipt_mismatch", "model identity")
        return {"plan": plan, "receipt": receipt, "identity": identity,
                "refs": {"native_plan": _ref(plan_path), "native_receipt": _ref(receipt_path),
                         "native_selection_request": _ref(selection_path), "native_model": model_ref,
                         "native_guard_contract": contract_ref, "native_declaration": _ref(declaration_path), **support_refs}}


def _plan(backend: Any, stage: str, inputs: dict[str, Any], root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot = copy.deepcopy(inputs)
    context = copy.deepcopy(snapshot)
    context_fp = fingerprint(context)
    response = require_mapping(backend(stage=stage, inputs=context, evidence_root=root), "planner response")
    if context != snapshot:
        raise ProductionPipelineBlocked("planner_input_mutated", stage)
    if set(response) != {"payload", "execution_record"}:
        raise ProductionPipelineBlocked("planner_record_invalid", "payload and execution_record required")
    payload = dict(require_mapping(response["payload"], "planner payload"))
    record = _validate_planner_record(
        require_mapping(response["execution_record"], "planner execution record"),
        stage=stage,
        context_fp=context_fp,
    )
    raw = _inside(record.get("raw_output_locator"), root)
    if record.get("raw_output_fingerprint") != fingerprint_bytes(raw.read_bytes()) or _read(raw) != payload:
        raise ProductionPipelineBlocked("planner_payload_mismatch", stage)
    _write(root / f"planner-{stage}.json", {"stage": stage, "inputs": snapshot, "payload": payload, "execution_record": record})
    return copy.deepcopy(payload), copy.deepcopy(record)


def _spine_disposition(value: str) -> str:
    """Collapse planner dispositions into the three reader actions."""
    if value == "merged":
        return "merge"
    if value in {"consumed", "body", "note", "appendix"}:
        return "support"
    # ``implied_by_scope`` has no independent prose obligation.  It is
    # intentionally represented as omit in the writer projection even though
    # the full WriterInput retains it as a visible disposition.
    return "omit"


def _spine_leak_keys(value: Any, *, path: str = "reader_spine") -> list[str]:
    """Return private/card-level keys found anywhere in a proposed spine."""
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if key_text in _READER_SPINE_PRIVATE_KEYS:
                found.append(f"{path}.{key_text}")
            found.extend(_spine_leak_keys(item, path=f"{path}.{key_text}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_spine_leak_keys(item, path=f"{path}[{index}]"))
    return found


def _spine_context(intent: Mapping[str, Any]) -> dict[str, Any]:
    """Copy only reader constraints that are useful during prose generation."""
    return {
        key: copy.deepcopy(intent[key])
        for key in (
            "language", "audience", "purpose", "artifact_mode", "artifact_format",
            "heading_policy", "list_policy", "table_policy", "citation_policy",
            "style", "extent", "required_content", "forbidden_content",
        )
    }


def validate_reader_spine(value: Any) -> dict[str, Any]:
    """Validate the minimal writer-facing reader-spine contract.

    This validator is deliberately separate from ``validate_writer_input``.
    The latter recognizes the immutable, full card-level WriterInput by its
    required ``selected_content``/``composition``/``limitations``/``citations``/
    ``route_semantics``/``gaps`` fields.  A full card-level object therefore
    cannot silently pass as a spine or be used as a prompt fallback.
    """
    spine = require_mapping(value, "reader_spine")
    extra = sorted(set(spine) - _READER_SPINE_KEYS)
    missing = sorted(_READER_SPINE_KEYS - set(spine))
    if extra or missing or spine.get("schema_version") != READER_SPINE_SCHEMA:
        detail = {"extra": extra, "missing": missing, "schema_version": spine.get("schema_version")}
        raise ProductionPipelineBlocked("reader_spine_non_minimal", detail)
    leaked = _spine_leak_keys(spine)
    if leaked:
        raise ProductionPipelineBlocked("reader_spine_private_field", leaked)

    for field in ("root_question", "root_conclusion", "artifact_form", "opening_job", "conclusion_job"):
        if not isinstance(spine[field], str) or not spine[field].strip():
            raise ProductionPipelineBlocked("reader_spine_field_invalid", field)
        if _READER_SPINE_LEAK.search(spine[field]):
            raise ProductionPipelineBlocked("reader_spine_internal_leakage", field)

    context = require_mapping(spine["reader_context"], "reader_spine reader_context")
    context_extra = sorted(set(context) - _READER_CONTEXT_KEYS)
    context_missing = sorted(_READER_CONTEXT_KEYS - set(context))
    if context_extra or context_missing:
        raise ProductionPipelineBlocked(
            "reader_spine_context_invalid", {"extra": context_extra, "missing": context_missing}
        )
    for key in ("language", "audience", "purpose", "artifact_mode", "artifact_format",
                "heading_policy", "list_policy", "table_policy", "citation_policy"):
        if not isinstance(context[key], str) or not context[key].strip():
            raise ProductionPipelineBlocked("reader_spine_context_invalid", key)
    if not isinstance(context["style"], Mapping) or not isinstance(context["extent"], Mapping):
        raise ProductionPipelineBlocked("reader_spine_context_invalid", "style/extent")
    for key in ("required_content", "forbidden_content"):
        if not isinstance(context[key], list) or not all(isinstance(item, str) and item.strip() for item in context[key]):
            raise ProductionPipelineBlocked("reader_spine_context_invalid", key)

    units = spine["major_units"]
    if not isinstance(units, list) or not units:
        raise ProductionPipelineBlocked("reader_spine_units_invalid", "major_units must be non-empty")
    unit_ids: list[str] = []
    unit_by_id: dict[str, dict[str, Any]] = {}
    unit_keys = {
        "planned_unit_id", "parent_unit_id", "order", "title", "reader_job",
        "relation_to_previous", "incoming_reader_state", "forward_link",
        "content", "evidence_anchor_ids", "limitation_ids", "presentation_mode",
        "target_extent",
    }
    for index, raw_unit in enumerate(units):
        unit = require_mapping(raw_unit, f"reader_spine major_units[{index}]")
        if set(unit) != unit_keys:
            raise ProductionPipelineBlocked(
                "reader_spine_unit_invalid",
                {"index": index, "extra": sorted(set(unit) - unit_keys), "missing": sorted(unit_keys - set(unit))},
            )
        unit_id = str(unit.get("planned_unit_id", ""))
        if not unit_id or unit_id in unit_by_id:
            raise ProductionPipelineBlocked("reader_spine_unit_invalid", f"duplicate or empty id: {unit_id}")
        unit_ids.append(unit_id)
        unit_by_id[unit_id] = unit
        for field in ("title", "reader_job", "relation_to_previous", "incoming_reader_state", "presentation_mode"):
            if not isinstance(unit[field], str) or not unit[field].strip():
                raise ProductionPipelineBlocked("reader_spine_unit_invalid", f"{unit_id}.{field}")
            if _READER_SPINE_LEAK.search(unit[field]):
                raise ProductionPipelineBlocked("reader_spine_internal_leakage", f"{unit_id}.{field}")
        parent = unit["parent_unit_id"]
        if parent is not None and not isinstance(parent, str):
            raise ProductionPipelineBlocked("reader_spine_unit_invalid", f"{unit_id}.parent_unit_id")
        link = require_mapping(unit["forward_link"], f"reader_spine {unit_id}.forward_link")
        if set(link) != {"outgoing_reader_state", "downstream_unit_ids"}:
            raise ProductionPipelineBlocked("reader_spine_forward_link_invalid", unit_id)
        if not isinstance(link["outgoing_reader_state"], str) or not link["outgoing_reader_state"].strip():
            raise ProductionPipelineBlocked("reader_spine_forward_link_invalid", unit_id)
        if _READER_SPINE_LEAK.search(link["outgoing_reader_state"]):
            raise ProductionPipelineBlocked("reader_spine_internal_leakage", f"{unit_id}.forward_link")
        if not isinstance(link["downstream_unit_ids"], list) or len(set(map(str, link["downstream_unit_ids"]))) != len(link["downstream_unit_ids"]):
            raise ProductionPipelineBlocked("reader_spine_forward_link_invalid", unit_id)
        if not isinstance(unit["content"], list) or not isinstance(unit["evidence_anchor_ids"], list) or not isinstance(unit["limitation_ids"], list):
            raise ProductionPipelineBlocked("reader_spine_unit_invalid", unit_id)
        content_ids: set[str] = set()
        for item in unit["content"]:
            row = require_mapping(item, f"reader_spine {unit_id}.content")
            if set(row) != {"content_unit_id", "meaning", "disposition"}:
                raise ProductionPipelineBlocked("reader_spine_content_invalid", unit_id)
            content_id = str(row["content_unit_id"])
            if not content_id or content_id in content_ids:
                raise ProductionPipelineBlocked("reader_spine_content_invalid", unit_id)
            content_ids.add(content_id)
            if not isinstance(row["meaning"], str) or not row["meaning"].strip():
                raise ProductionPipelineBlocked("reader_spine_content_invalid", content_id)
            if _READER_SPINE_LEAK.search(row["meaning"]):
                raise ProductionPipelineBlocked("reader_spine_internal_leakage", content_id)
            if row["disposition"] not in {"support", "merge"}:
                raise ProductionPipelineBlocked("reader_spine_content_invalid", content_id)

    for unit in units:
        unit_id = str(unit["planned_unit_id"])
        parent = unit["parent_unit_id"]
        if parent is not None and parent not in unit_by_id:
            raise ProductionPipelineBlocked("reader_spine_unit_invalid", f"{unit_id}.parent_unit_id")
        links = unit["forward_link"]["downstream_unit_ids"]
        if any(str(item) not in unit_by_id for item in links):
            raise ProductionPipelineBlocked("reader_spine_forward_link_invalid", unit_id)

    anchors = spine["evidence_anchors"]
    if not isinstance(anchors, list):
        raise ProductionPipelineBlocked("reader_spine_evidence_invalid", "evidence_anchors must be a list")
    anchor_ids: set[str] = set()
    for index, raw_anchor in enumerate(anchors):
        anchor = require_mapping(raw_anchor, f"reader_spine evidence_anchors[{index}]")
        anchor_keys = {"anchor_id", "source_id", "locator", "relation", "observed_summary", "boundary", "content_unit_ids"}
        if set(anchor) != anchor_keys:
            raise ProductionPipelineBlocked("reader_spine_evidence_invalid", index)
        anchor_id = str(anchor["anchor_id"])
        if not anchor_id or anchor_id in anchor_ids:
            raise ProductionPipelineBlocked("reader_spine_evidence_invalid", anchor_id)
        anchor_ids.add(anchor_id)
        for key in ("source_id", "locator", "relation", "observed_summary", "boundary"):
            if not isinstance(anchor[key], str) or not anchor[key].strip():
                raise ProductionPipelineBlocked("reader_spine_evidence_invalid", f"{anchor_id}.{key}")
            if _READER_SPINE_LEAK.search(anchor[key]):
                raise ProductionPipelineBlocked("reader_spine_internal_leakage", f"{anchor_id}.{key}")
        if not isinstance(anchor["content_unit_ids"], list) or not anchor["content_unit_ids"]:
            raise ProductionPipelineBlocked("reader_spine_evidence_invalid", anchor_id)

    dispositions = spine["editorial_dispositions"]
    if not isinstance(dispositions, list) or not dispositions:
        raise ProductionPipelineBlocked("reader_spine_dispositions_invalid", "editorial_dispositions")
    disposition_ids: set[str] = set()
    disposition_by_content: dict[str, dict[str, Any]] = {}
    for index, raw_row in enumerate(dispositions):
        row = require_mapping(raw_row, f"reader_spine editorial_dispositions[{index}]")
        if set(row) != {"content_unit_id", "planned_unit_ids", "disposition"}:
            raise ProductionPipelineBlocked("reader_spine_disposition_invalid", index)
        content_id = str(row["content_unit_id"])
        if not content_id or content_id in disposition_ids:
            raise ProductionPipelineBlocked("reader_spine_disposition_invalid", content_id)
        disposition_ids.add(content_id)
        disposition_by_content[content_id] = row
        if row["disposition"] not in _READER_CONTENT_DISPOSITIONS:
            raise ProductionPipelineBlocked("reader_spine_disposition_invalid", content_id)
        if not isinstance(row["planned_unit_ids"], list) or len(set(map(str, row["planned_unit_ids"]))) != len(row["planned_unit_ids"]):
            raise ProductionPipelineBlocked("reader_spine_disposition_invalid", content_id)
        if row["disposition"] == "omit" and row["planned_unit_ids"]:
            raise ProductionPipelineBlocked("reader_spine_disposition_invalid", f"omitted content has destinations: {content_id}")
        if row["disposition"] != "omit" and not row["planned_unit_ids"]:
            raise ProductionPipelineBlocked("reader_spine_disposition_invalid", content_id)
        if any(str(unit_id) not in unit_by_id for unit_id in row["planned_unit_ids"]):
            raise ProductionPipelineBlocked("reader_spine_disposition_invalid", content_id)

    for anchor in anchors:
        if any(str(content_id) not in disposition_ids for content_id in anchor["content_unit_ids"]):
            raise ProductionPipelineBlocked("reader_spine_evidence_invalid", f"{anchor['anchor_id']}.content_unit_ids")

    for unit in units:
        unit_id = str(unit["planned_unit_id"])
        for row in unit["content"]:
            content_id = str(row["content_unit_id"])
            disposition = disposition_by_content.get(content_id)
            if disposition is None or unit_id not in {str(item) for item in disposition["planned_unit_ids"]}:
                raise ProductionPipelineBlocked("reader_spine_content_unattached", content_id)
            if row["disposition"] != disposition["disposition"]:
                raise ProductionPipelineBlocked("reader_spine_content_disposition_mismatch", content_id)

    limitations = spine["conclusion_sensitive_limitations"]
    if not isinstance(limitations, list):
        raise ProductionPipelineBlocked("reader_spine_limitations_invalid", "must be a list")
    limitation_ids: set[str] = set()
    for index, raw_row in enumerate(limitations):
        row = require_mapping(raw_row, f"reader_spine conclusion_sensitive_limitations[{index}]")
        limitation_keys = {
            "limitation_id", "meaning", "affected_content_unit_ids", "required_placement",
            "materiality", "materiality_reason", "disposition", "destination_unit_ids",
            "realization_requirement",
        }
        if set(row) != limitation_keys:
            raise ProductionPipelineBlocked("reader_spine_limitation_invalid", index)
        limitation_id = str(row["limitation_id"])
        if not limitation_id or limitation_id in limitation_ids:
            raise ProductionPipelineBlocked("reader_spine_limitation_invalid", limitation_id)
        limitation_ids.add(limitation_id)
        if row["materiality"] not in _READER_MATERIALITIES:
            raise ProductionPipelineBlocked("reader_spine_limitation_invalid", f"{limitation_id}.materiality")
        if row["disposition"] not in _READER_CONTENT_DISPOSITIONS:
            raise ProductionPipelineBlocked("reader_spine_limitation_invalid", f"{limitation_id}.disposition")
        for key in ("meaning", "required_placement", "materiality_reason", "realization_requirement"):
            if not isinstance(row[key], str) or not row[key].strip():
                raise ProductionPipelineBlocked("reader_spine_limitation_invalid", f"{limitation_id}.{key}")
            if _READER_SPINE_LEAK.search(row[key]):
                raise ProductionPipelineBlocked("reader_spine_internal_leakage", f"{limitation_id}.{key}")
        for key in ("affected_content_unit_ids", "destination_unit_ids"):
            if not isinstance(row[key], list) or len(set(map(str, row[key]))) != len(row[key]):
                raise ProductionPipelineBlocked("reader_spine_limitation_invalid", f"{limitation_id}.{key}")
        if not row["destination_unit_ids"]:
            raise ProductionPipelineBlocked("reader_spine_limitation_invalid", limitation_id)
        if any(str(unit_id) not in unit_by_id for unit_id in row["destination_unit_ids"]):
            raise ProductionPipelineBlocked("reader_spine_limitation_invalid", limitation_id)
        if any(str(content_id) not in disposition_ids for content_id in row["affected_content_unit_ids"]):
            raise ProductionPipelineBlocked("reader_spine_limitation_invalid", f"{limitation_id}.affected_content_unit_ids")
        for unit_id in row["destination_unit_ids"]:
            unit = unit_by_id[str(unit_id)]
            if limitation_id not in unit["limitation_ids"]:
                raise ProductionPipelineBlocked("reader_spine_limitation_unattached", limitation_id)

    if any(str(anchor_id) not in anchor_ids for unit in units for anchor_id in unit["evidence_anchor_ids"]):
        raise ProductionPipelineBlocked("reader_spine_evidence_unattached", "unit references unknown anchor")
    if any(str(limitation_id) not in limitation_ids for unit in units for limitation_id in unit["limitation_ids"]):
        raise ProductionPipelineBlocked("reader_spine_limitation_unattached", "unit references unknown limitation")
    return spine


def build_reader_spine(
    reader_brief: Mapping[str, Any],
    *,
    composition_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile the current ReaderBrief/CompositionPlan into ``reader_spine``.

    ``reader_brief`` is intentionally the only accepted source shape.  Passing
    the full WriterInput directly raises instead of triggering a permissive
    fallback.  The full WriterInput is validated first and remains available
    only in the private receipt written by ``prepare_production_reader_input``.
    """
    brief = require_mapping(reader_brief, "ReaderBrief")
    if "writer_input" not in brief:
        raise ProductionPipelineBlocked(
            "reader_spine_source_invalid",
            "ReaderBrief with private writer_input is required; full WriterInput cannot be used as reader_spine",
        )
    writer_input = require_mapping(brief["writer_input"], "ReaderBrief.writer_input")
    brief_plan = brief.get("composition_plan")
    plan = require_mapping(composition_plan if composition_plan is not None else brief_plan, "CompositionPlan")
    if brief_plan is not None and dict(brief_plan) != dict(plan):
        raise ProductionPipelineBlocked("reader_spine_source_stale", "CompositionPlan does not match ReaderBrief")
    if brief.get("writer_input_fingerprint") != fingerprint(writer_input):
        raise ProductionPipelineBlocked("reader_spine_source_stale", "ReaderBrief writer_input fingerprint")
    if plan.get("plan_fingerprint") != fingerprint_without(dict(plan), "plan_fingerprint"):
        raise ProductionPipelineBlocked("reader_spine_source_stale", "CompositionPlan fingerprint")
    if "brief_fingerprint" in brief and brief.get("brief_fingerprint") != fingerprint_without(dict(brief), "brief_fingerprint"):
        raise ProductionPipelineBlocked("reader_spine_source_stale", "ReaderBrief fingerprint")
    try:
        validate_writer_input(writer_input, reader_brief=brief, composition_plan=plan)
    except ValidationError as exc:
        raise ProductionPipelineBlocked("reader_spine_source_invalid", str(exc)) from exc

    intent = require_mapping(brief.get("reader_intent"), "ReaderBrief.reader_intent")
    boundaries = require_mapping(brief.get("content_boundaries"), "ReaderBrief.content_boundaries")
    boundary_content = {
        str(row["content_unit_id"]): row
        for row in boundaries.get("content_units", [])
        if isinstance(row, Mapping) and row.get("content_unit_id")
    }
    selected = {
        str(row["content_unit_id"]): row
        for row in writer_input.get("selected_content", [])
        if isinstance(row, Mapping) and row.get("content_unit_id")
    }
    plan_dispositions = {
        str(row["content_unit_id"]): row
        for row in plan.get("content_dispositions", [])
        if isinstance(row, Mapping) and row.get("content_unit_id")
    }
    unit_rows = {
        str(row["planned_unit_id"]): row
        for row in plan.get("planned_units", [])
        if isinstance(row, Mapping) and row.get("planned_unit_id")
    }
    if not unit_rows or set(plan_dispositions) != set(boundary_content):
        raise ProductionPipelineBlocked("reader_spine_source_invalid", "plan/boundary content coverage")

    ordered_unit_ids = _canonical_plan_order(plan["planned_units"])
    unit_rank = {unit_id: index for index, unit_id in enumerate(ordered_unit_ids)}
    editorial: list[dict[str, Any]] = []
    for content_id in sorted(plan_dispositions):
        disposition_row = plan_dispositions[content_id]
        disposition = _spine_disposition(str(disposition_row["disposition"]))
        planned_ids = list(disposition_row.get("planned_unit_ids", []))
        if disposition != "omit" and content_id not in selected:
            raise ProductionPipelineBlocked("reader_spine_content_missing", content_id)
        if disposition == "omit":
            # Hidden/deferred/conflicted material has no writer destination;
            # do not preserve a planner's internal placement hint in the
            # minimal projection.
            planned_ids = []
        elif any(str(unit_id) not in unit_rows for unit_id in planned_ids):
            raise ProductionPipelineBlocked("reader_spine_disposition_invalid", content_id)
        editorial.append({
            "content_unit_id": content_id,
            "planned_unit_ids": sorted(map(str, planned_ids), key=lambda unit_id: unit_rank.get(unit_id, len(unit_rank))),
            "disposition": disposition,
        })

    evidence_by_anchor: dict[str, dict[str, Any]] = {}
    evidence_content_ids: dict[str, set[str]] = {}
    evidence_rows = [row for row in writer_input.get("evidence", []) if isinstance(row, Mapping)]
    for row in evidence_rows:
        anchor_id = str(row.get("anchor_id", ""))
        if not anchor_id:
            raise ProductionPipelineBlocked("reader_spine_evidence_invalid", "evidence row has no anchor_id")
        comparable = {
            key: row.get(key)
            for key in ("anchor_id", "source_id", "locator", "relation", "observed_summary", "boundary")
        }
        previous = evidence_by_anchor.get(anchor_id)
        if previous is not None and previous != comparable:
            raise ProductionPipelineBlocked("reader_spine_duplicate_evidence_conflict", anchor_id)
        evidence_by_anchor[anchor_id] = comparable
        evidence_content_ids.setdefault(anchor_id, set()).add(str(row.get("content_unit_id", "")))

    selected_content_ids = set(selected)
    for content_id, row in selected.items():
        if content_id not in boundary_content:
            raise ProductionPipelineBlocked("reader_spine_source_invalid", f"unknown selected content: {content_id}")
        for anchor_id in row.get("evidence_anchor_ids", []):
            if str(anchor_id) not in evidence_by_anchor:
                raise ProductionPipelineBlocked("reader_spine_evidence_missing", str(anchor_id))
            evidence_content_ids.setdefault(str(anchor_id), set()).add(content_id)
    evidence_anchors = []
    for anchor_id in sorted(evidence_by_anchor):
        row = evidence_by_anchor[anchor_id]
        content_ids = sorted(item for item in evidence_content_ids.get(anchor_id, set()) if item in selected_content_ids)
        if not content_ids:
            continue
        evidence_anchors.append({**row, "content_unit_ids": content_ids})

    limitation_by_id = {
        str(row["limitation_id"]): row
        for row in writer_input.get("limitations", [])
        if isinstance(row, Mapping) and row.get("limitation_id")
    }
    boundary_limitation_by_id = {
        str(row["limitation_id"]): row
        for row in boundaries.get("limitations", [])
        if isinstance(row, Mapping) and row.get("limitation_id")
    }
    material_limitations: list[dict[str, Any]] = []
    material_ids: set[str] = set()
    for raw in plan.get("limitation_dispositions", []):
        plan_limitation = require_mapping(raw, "CompositionPlan limitation disposition")
        limitation_id = str(plan_limitation["limitation_id"])
        materiality = str(plan_limitation["materiality"])
        if materiality not in _READER_MATERIALITIES:
            continue
        if limitation_id not in boundary_limitation_by_id or limitation_id not in limitation_by_id:
            raise ProductionPipelineBlocked("reader_spine_material_limitation_missing", limitation_id)
        destinations = [str(item) for item in plan_limitation.get("destination_unit_ids", [])]
        if not destinations or any(item not in unit_rows for item in destinations):
            raise ProductionPipelineBlocked("reader_spine_limitation_invalid", limitation_id)
        limitation = limitation_by_id[limitation_id]
        disposition = _spine_disposition(str(plan_limitation["disposition"]))
        material_ids.add(limitation_id)
        material_limitations.append({
            "limitation_id": limitation_id,
            "meaning": limitation["meaning"],
            "affected_content_unit_ids": sorted(map(str, limitation.get("affected_content_unit_ids", []))),
            "required_placement": limitation["required_placement"],
            "materiality": materiality,
            "materiality_reason": plan_limitation["materiality_reason"],
            "disposition": disposition,
            "destination_unit_ids": sorted(destinations, key=lambda unit_id: unit_rank.get(unit_id, len(unit_rank))),
            "realization_requirement": plan_limitation["realization_requirement"],
        })
    material_limitations.sort(key=lambda row: row["limitation_id"])

    limitation_destinations = {
        str(row["limitation_id"]): {str(item) for item in row.get("destination_unit_ids", [])}
        for row in material_limitations
    }
    units: list[dict[str, Any]] = []
    for unit_id in ordered_unit_ids:
        plan_unit = unit_rows[unit_id]
        unit_content: list[dict[str, Any]] = []
        anchor_ids: set[str] = set()
        for content_id in plan_unit.get("content_unit_ids", []):
            content_id = str(content_id)
            row = selected.get(content_id)
            disposition = plan_dispositions.get(content_id)
            if row is None or disposition is None:
                continue
            mapped = _spine_disposition(str(disposition["disposition"]))
            if mapped == "omit":
                continue
            unit_content.append({
                "content_unit_id": content_id,
                "meaning": row["meaning"],
                "disposition": mapped,
            })
            anchor_ids.update(str(item) for item in row.get("evidence_anchor_ids", []))
        limitation_ids = [
            limitation_id
            for limitation_id in sorted(material_ids)
            if unit_id in limitation_destinations.get(limitation_id, set())
        ]
        units.append({
            "planned_unit_id": unit_id,
            "parent_unit_id": plan_unit["parent_unit_id"],
            "order": plan_unit["order"],
            "title": plan_unit["title"],
            "reader_job": plan_unit["reader_job"],
            "relation_to_previous": plan_unit["relation_to_previous"],
            "incoming_reader_state": plan_unit["incoming_reader_state"],
            "forward_link": {
                "outgoing_reader_state": plan_unit["outgoing_reader_state"],
                "downstream_unit_ids": list(plan_unit.get("downstream_unit_ids", [])),
            },
            "content": unit_content,
            "evidence_anchor_ids": sorted(anchor_ids),
            "limitation_ids": limitation_ids,
            "presentation_mode": plan_unit["presentation_mode"],
            "target_extent": plan_unit["target_extent"],
        })

    spine = {
        "schema_version": READER_SPINE_SCHEMA,
        "root_question": plan["central_question"],
        "root_conclusion": plan["central_throughline"],
        "artifact_form": plan["artifact_form"],
        "opening_job": plan["opening_job"],
        "conclusion_job": plan["conclusion_job"],
        "reader_context": _spine_context(intent),
        "major_units": units,
        "evidence_anchors": evidence_anchors,
        "editorial_dispositions": editorial,
        "conclusion_sensitive_limitations": material_limitations,
    }
    return validate_reader_spine(spine)


def render_reader_spine_prompt(reader_spine: Mapping[str, Any]) -> str:
    """Render only the validated spine into the production writer prompt."""
    spine = validate_reader_spine(reader_spine)
    return (
        "请只输出面向读者的最终成稿。按照以下 reader_spine 组织整篇文本：先回答根问题，"
        "再按主要单元的阅读职责推进；同一单元中的多个材料只在确有独立阅读职责时分开，"
        "否则按 support/merge/omit 处置。保留必要证据锚点，并把结论敏感限制附在受影响单元；"
        "不要输出内部记录、模型标识、执行状态、缺口清单或流程说明。\n\n"
        + json.dumps(spine, ensure_ascii=False, sort_keys=True, indent=2)
    )


def _paragraphs_for_diagnostic(text: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n+", text.replace("\r\n", "\n").replace("\r", "\n")) if block.strip()]


def diagnose_reader_output(
    text: str,
    reader_spine: Mapping[str, Any],
    *,
    thresholds: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Measure the focused reader-spine quality risks used by R04 checks."""
    if not isinstance(text, str):
        raise ProductionPipelineBlocked("reader_diagnostic_input_invalid", "text must be a string")
    spine = validate_reader_spine(reader_spine)
    limits = {
        "one_finding_paragraph_ratio": 0.65,
        "repeated_no_information_disclaimers": 0,
        "list_item_ratio": 0.50,
        "workflow_leak_count": 0,
        "transition_only_count": 0,
        "fiction_author_meta_count": 0,
        "travel_negative_only_failure_count": 0,
    }
    if thresholds is not None:
        for key, value in thresholds.items():
            if key not in limits or not isinstance(value, (int, float)) or value < 0:
                raise ProductionPipelineBlocked("reader_diagnostic_threshold_invalid", key)
            limits[key] = value
    blocks = _paragraphs_for_diagnostic(text)
    content_markers = {
        str(item["content_unit_id"]): str(item["meaning"]) for unit in spine["major_units"] for item in unit["content"]
    }
    marker_to_content: dict[str, str] = {}
    for content_id, meaning in content_markers.items():
        compact = re.sub(r"\s+", "", meaning)
        marker = meaning[:32].strip() if len(meaning) <= 48 else meaning[:28].strip()
        if marker:
            marker_to_content[marker] = content_id
        if compact and len(compact) >= 8:
            marker_to_content[compact[:24]] = content_id
    prose_blocks = [block for block in blocks if not all(_LIST_ITEM.match(line) for line in block.splitlines())]
    list_items = [line.strip() for block in blocks for line in block.splitlines() if _LIST_ITEM.match(line)]
    finding_blocks = 0
    single_finding_blocks = 0
    for block in prose_blocks:
        found = {content_id for marker, content_id in marker_to_content.items() if marker in block}
        if found:
            finding_blocks += 1
            if len(found) == 1:
                single_finding_blocks += 1
    one_finding_ratio = single_finding_blocks / finding_blocks if finding_blocks else 0.0
    sentences = [part.strip() for part in re.split(r"(?<=[.!?。！？])\s*", text) if part.strip()]
    disclaimer_sentences = [re.sub(r"\s+", " ", item) for item in sentences if _DISCLAIMER.search(item)]
    # A second no-new-information disclaimer is already repetition even when
    # the writer changes its wording.  Exact duplicates remain visible via
    # the same count.
    repeated_disclaimers = max(0, len(disclaimer_sentences) - 1)
    total_units = len(prose_blocks) + len(list_items)
    list_ratio = len(list_items) / total_units if total_units else 0.0
    workflow_leaks = len(_READER_SPINE_LEAK.findall(text))
    transition_only = sum(
        1 for block in prose_blocks
        if len(re.sub(r"\s+", "", block)) <= 40
        and _TRANSITION_ONLY.search(re.sub(r"\s+", "", block))
        and not any(marker in block for marker in marker_to_content)
    )
    purpose = str(spine["reader_context"].get("purpose") or "")
    fiction_author_meta = len(_FICTION_AUTHOR_META.findall(text)) if _FICTION_REQUEST.search(purpose) else 0
    travel_negative_only = 0
    if _TRAVEL_REQUEST.search(purpose):
        for block in prose_blocks:
            if _TRAVEL_FAILURE_TRIGGER.search(block) and _TRAVEL_NEGATIVE.search(block) and not _TRAVEL_EXECUTABLE_ACTION.search(block):
                travel_negative_only += 1
    findings: list[dict[str, Any]] = []
    if finding_blocks >= 2 and one_finding_ratio > limits["one_finding_paragraph_ratio"]:
        findings.append({"code": "one_finding_one_paragraph", "count": single_finding_blocks, "ratio": one_finding_ratio, "threshold": limits["one_finding_paragraph_ratio"]})
    if repeated_disclaimers > limits["repeated_no_information_disclaimers"]:
        findings.append({"code": "repeated_no_information_disclaimer", "count": repeated_disclaimers, "threshold": limits["repeated_no_information_disclaimers"]})
    if len(list_items) >= 3 and list_ratio > limits["list_item_ratio"] and spine["reader_context"]["list_policy"] != "lists_required":
        findings.append({"code": "list_inflation", "count": len(list_items), "ratio": list_ratio, "threshold": limits["list_item_ratio"]})
    if workflow_leaks > limits["workflow_leak_count"]:
        findings.append({"code": "guard_process_leakage", "count": workflow_leaks, "threshold": limits["workflow_leak_count"]})
    if transition_only > limits["transition_only_count"]:
        findings.append({"code": "transition_only_coherence", "count": transition_only, "threshold": limits["transition_only_count"]})
    if fiction_author_meta > limits["fiction_author_meta_count"]:
        findings.append({"code": "fiction_author_meta", "count": fiction_author_meta, "threshold": limits["fiction_author_meta_count"]})
    if travel_negative_only > limits["travel_negative_only_failure_count"]:
        findings.append({"code": "travel_negative_only_failure", "count": travel_negative_only, "threshold": limits["travel_negative_only_failure_count"]})
    return {
        "schema_version": READER_DIAGNOSTIC_SCHEMA,
        "status": "repair" if findings else "passed",
        "thresholds": limits,
        "metrics": {
            "paragraph_count": len(prose_blocks),
            "finding_paragraph_count": finding_blocks,
            "single_finding_paragraph_count": single_finding_blocks,
            "single_finding_paragraph_ratio": one_finding_ratio,
            "disclaimer_sentence_count": len(disclaimer_sentences),
            "repeated_no_information_disclaimer_count": repeated_disclaimers,
            "list_item_count": len(list_items),
            "list_item_ratio": list_ratio,
            "workflow_leak_count": workflow_leaks,
            "transition_only_count": transition_only,
            "fiction_author_meta_count": fiction_author_meta,
            "travel_negative_only_failure_count": travel_negative_only,
        },
        "findings": findings,
        "reader_spine_fingerprint": fingerprint(spine),
    }


# Names used by callers that describe this as a quality rather than output
# diagnostic.  They are aliases to one implementation and do not create a
# second provider or a second receipt path.
compile_reader_spine = build_reader_spine
diagnose_reader_quality = diagnose_reader_output


def prepare_production_reader_input(request, *, native_provider, planner_backend, frozen_content_boundaries, evidence_root):
    """Return the exact current WriterInput plus auditable native/reader refs.

    Raises ProductionPipelineBlocked (or a current contract ValidationError).
    Never returns ready on provider failure and never invokes a writer/judge.
    """
    request = copy.deepcopy(validate_writing_request(request))
    boundaries = _validate_planner_facts(frozen_content_boundaries)
    if type(native_provider) is not InstalledResearchGuardProvider:
        raise ProductionPipelineBlocked("native_provider_invalid", "installed console provider required")
    if not callable(planner_backend):
        raise ProductionPipelineBlocked("planner_unavailable", "a real execution adapter is required")
    source_identity = _source_identity()
    root = Path(evidence_root).absolute()
    if root.exists() and any(root.iterdir()):
        raise ProductionPipelineBlocked("evidence_root_not_empty", str(root))
    root.mkdir(parents=True, exist_ok=True)
    _inside(root, root, directory=True)
    decision = select_route({"writing_request": request, "decision_id": "decision:" + request["request_fingerprint"][7:31],
                             "decided_at": utc_now(), "material_assumptions": []})
    if decision["status"] != "current":
        raise ProductionPipelineBlocked("route_not_current", decision)
    context = {"writing_request": request, "content_boundaries": boundaries, "route_decision": decision}
    _write(root / "request.json", context)
    prepared, research_execution = _plan(planner_backend, "research", context, root)
    native = native_provider.research(prepared, evidence_root=root)
    # Preserve native material limits in the current reader boundary before
    # the composition planner runs.  A limitation that changes a conclusion,
    # scope, or viewpoint must become a formal placement or blocker; leaving
    # it only in the private native plan allows unsupported prose to leak out.
    boundaries, promoted_limitations = _merge_native_limitations(boundaries, native["plan"])
    context["content_boundaries"] = boundaries
    if promoted_limitations:
        _write(root / "native-limitations.json", {
            "schema_version": "logic-writing.native-limitations.v1",
            "rows": promoted_limitations,
            "claim_boundary": "Rows copied from the current native Limitation selections; no remedy or factual addition is asserted.",
        })
    handoff = build_researchguard_handoff(native["plan"], reader_intent_fingerprint=request["reader_intent"]["intent_fingerprint"],
               native_result_locator=native["refs"]["native_plan"]["locator"],
               native_receipt_fingerprint=fingerprint(native["receipt"]), native_receipt_locator=native["refs"]["native_receipt"]["locator"])
    composed, compose_execution = _plan(planner_backend, "compose", {**context, "native_plan": native["plan"], "native_handoff": handoff}, root)
    if set(composed) != _COMPOSE_KEYS:
        raise ProductionPipelineBlocked("composition_payload_invalid", sorted(set(composed) ^ _COMPOSE_KEYS))
    for ref in native["refs"].values():
        _check_ref(ref, root)
    mapping = composed["native_handoff_mapping"]
    brief = build_reader_brief(route_decision=decision, content_boundaries=boundaries,
            composition_plan=composed["composition_plan"], route_composition=composed["route_composition"],
            native_dependency_receipt_fingerprints=[fingerprint(native["receipt"])],
            content_authority_fingerprints={str(row["content_unit_id"]): fingerprint(row) for row in boundaries.get("content_units", [])},
            brief_id="brief:" + request["request_fingerprint"][7:31], native_handoff=handoff,
            native_plan=native["plan"], native_handoff_mapping=mapping)
    binding = bind_handoff_consumption(handoff, brief, mapping)
    validate_handoff_consumption(binding, handoff, brief, mapping)
    validate_writer_input(brief["writer_input"], reader_brief=brief, composition_plan=composed["composition_plan"])
    reader_spine = build_reader_spine(brief, composition_plan=composed["composition_plan"])
    mapped_planned = {value for row in binding["unit_mapping"] for value in row["planned_unit_ids"]}
    if mapped_planned != set(binding["planned_unit_ids"]):
        raise ProductionPipelineBlocked("composition_mapping_incomplete", "every planned unit must consume native research")
    refs = dict(native["refs"])
    for name, value in {"reader_brief": brief, "composition_plan": composed["composition_plan"],
                        "semantic_handoff": handoff, "consumption_binding": binding,
                        "reader_spine": reader_spine}.items():
        path = root / f"{name}.json"
        _write(path, value)
        refs[name] = _ref(path)
    if promoted_limitations:
        refs["native_limitations"] = _ref(root / "native-limitations.json")
    if _source_identity() != source_identity:
        raise ProductionPipelineBlocked("production_source_changed_during_run", "repeat on a frozen product snapshot")
    result = {"schema_version": SCHEMA, "status": "ready_for_writer", "writer_input": brief["writer_input"],
              "writer_input_fingerprint": brief["writer_input_fingerprint"], "reader_spine": reader_spine,
              "reader_spine_fingerprint": fingerprint(reader_spine), "reader_spine_schema": READER_SPINE_SCHEMA,
              "refs": refs,
              "request_fingerprint": request["request_fingerprint"], "content_fingerprint": fingerprint(boundaries),
              "source_fingerprint": fingerprint(source_identity), "source_identity": source_identity,
              "provider_identity": native["identity"], "planner_execution_records": [research_execution, compose_execution],
              "claim_boundary": "Current native-to-reader input preparation only; no prose quality or final closure is asserted."}
    _write(root / "production-reader-input.json", result)
    return result


__all__ = [
    "InstalledResearchGuardProvider", "ProductionPipelineBlocked", "READER_SPINE_SCHEMA",
    "READER_DIAGNOSTIC_SCHEMA", "build_reader_spine", "compile_reader_spine",
    "validate_reader_spine", "render_reader_spine_prompt", "diagnose_reader_output",
    "diagnose_reader_quality", "prepare_production_reader_input",
]
