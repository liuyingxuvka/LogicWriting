"""Bounded reader-projection conformance adapter candidate.

This file is intended for the canonical LogicWriting skill source.  The
adapter exercises the current production
``build_reader_spine``/``validate_reader_spine`` boundary through the shared
FlowGuard ``replay_trace`` entrypoint.

Two result categories are kept separate:

* ``structural_alignment`` describes model/code/test binding evidence.  It
  cannot be promoted to a production behavior result.
* ``production_reader_conformance`` is emitted only from a current
  FlowGuard ``replay_trace`` against the installed production reader-spine
  implementation.

The only runtime claim in this adapter is ``reader-projection.v1``.  It does
not claim writer quality, ResearchGuard qualification, source factual truth,
full pipeline conformance, installation, or publication readiness.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import flowguard.conformance as _flowguard_conformance
from flowguard import ConformanceReport, ReplayObservation, Trace, TraceStep, replay_trace
from flowguard.replay import ReplayInput


READER_PROJECTION_CLAIM = "reader-projection.v1"
STRUCTURAL_ALIGNMENT = "structural_alignment"
PRODUCTION_READER_CONFORMANCE = "production_reader_conformance"


def _load_production_pipeline():
    """Import the current production reader module without copying it."""

    import production_reader_pipeline  # type: ignore[import-not-found]

    return production_reader_pipeline


@dataclass(frozen=True)
class ReaderProjectionRequest:
    """The sole input accepted by the prototype production adapter."""

    reader_brief: Mapping[str, Any]
    composition_plan: Mapping[str, Any]


@dataclass(frozen=True)
class ReaderProjectionExpectation:
    """Abstract expected observation, kept independent of production output."""

    output: Mapping[str, Any]
    state: Mapping[str, Any]
    label: str = "reader_projection_ready"


def _unit_order(plan: Mapping[str, Any]) -> list[str]:
    rows = plan.get("planned_units", [])
    if not isinstance(rows, list):
        raise ValueError("composition plan planned_units must be a list")
    ordered = sorted(
        (row for row in rows if isinstance(row, Mapping)),
        key=lambda row: (int(row.get("order", 0)), str(row.get("planned_unit_id", ""))),
    )
    return [str(row["planned_unit_id"]) for row in ordered]


def _abstract_projection_from_plan(
    plan: Mapping[str, Any],
    *,
    root_question: str,
    root_conclusion: str,
    owner: str,
    artifact_form: str,
) -> ReaderProjectionExpectation:
    """Build the small abstract oracle from declared plan fields only.

    This function intentionally does not call or inspect the production
    reader-spine compiler.  It represents the model-side expectation that the
    adapter must satisfy.
    """

    order = _unit_order(plan)
    rows_by_id = {
        str(row["planned_unit_id"]): row
        for row in plan.get("planned_units", [])
        if isinstance(row, Mapping) and row.get("planned_unit_id")
    }
    disposition_rows = plan.get("content_dispositions", [])
    visible: list[str] = []
    if isinstance(disposition_rows, list):
        for row in disposition_rows:
            if not isinstance(row, Mapping):
                continue
            if str(row.get("disposition", "")) in {"consumed", "body", "merged"}:
                content_id = str(row.get("content_unit_id", ""))
                if content_id and content_id not in visible:
                    visible.append(content_id)

    downstream = [
        {
            "planned_unit_id": unit_id,
            "downstream_unit_ids": [
                str(child)
                for child in rows_by_id[unit_id].get("downstream_unit_ids", [])
            ],
        }
        for unit_id in order
    ]
    limitation_ids: list[str] = []
    limitations = plan.get("limitation_dispositions", [])
    if isinstance(limitations, list):
        for row in limitations:
            if not isinstance(row, Mapping):
                continue
            if str(row.get("materiality", "")) in {
                "changes_answer", "changes_action", "changes_scope", "changes_strength"
            }:
                value = str(row.get("limitation_id", ""))
                if value and value not in limitation_ids:
                    limitation_ids.append(value)

    output = {
        "claim": READER_PROJECTION_CLAIM,
        "source_schema": "logic-writing.reader-spine.v1",
        "root_question": root_question,
        "root_conclusion": root_conclusion,
        "artifact_form": artifact_form,
        "route_mode": owner,
    }
    state = {
        "claim": READER_PROJECTION_CLAIM,
        "status": "ready",
        "major_unit_order": order,
        "downstream": downstream,
        "visible_content_ids": visible,
        "limitation_ids": limitation_ids,
    }
    return ReaderProjectionExpectation(output=output, state=state)


class ReaderProjectionReplayAdapter:
    """Adapt abstract reader-spine steps to the current production compiler.

    ``apply_step`` receives only ``ReplayInput``.  It never receives the
    expected output or expected state from a ``TraceStep``.  The raw spine is
    retained only inside the adapter for the next validation step and is never
    used as the abstract oracle.
    """

    def __init__(self) -> None:
        self._production = _load_production_pipeline()
        self._raw_spine: dict[str, Any] | None = None
        self._last_output: Any = None
        self._last_state: Any = None
        self._last_label = ""
        self._last_reason = ""

    def reset(self, initial_state: Any) -> None:
        if not isinstance(initial_state, Mapping):
            raise TypeError("reader projection initial state must be a mapping")
        if initial_state.get("claim") != READER_PROJECTION_CLAIM:
            raise ValueError("reader projection claim boundary mismatch")
        self._raw_spine = None
        self._last_output = None
        self._last_state = copy.deepcopy(dict(initial_state))
        self._last_label = "reset"
        self._last_reason = "reader-projection.v1 adapter reset"

    def apply_step(self, step: ReplayInput) -> ReplayObservation:
        if step.function_name == "BuildReaderSpine":
            if not isinstance(step.function_input, ReaderProjectionRequest):
                raise TypeError("BuildReaderSpine expects ReaderProjectionRequest")
            request = step.function_input
            raw = self._production.build_reader_spine(
                request.reader_brief,
                composition_plan=request.composition_plan,
            )
            # The production compiler currently validates before returning;
            # repeat the public boundary check so this adapter never reports a
            # projection that bypassed the production validator.
            self._production.validate_reader_spine(raw)
            self._raw_spine = copy.deepcopy(raw)
            self._last_output = self._project_output(raw)
            self._last_state = self._project_state(raw)
            self._last_label = "reader_projection_ready"
            self._last_reason = "current production reader-spine compiler and validator"
            return self._observation(step.function_name)

        if step.function_name == "ValidateReaderSpine":
            if step.function_input is not None:
                raise TypeError("ValidateReaderSpine takes no external input")
            if self._raw_spine is None:
                raise RuntimeError("ValidateReaderSpine requires a preceding BuildReaderSpine")
            self._production.validate_reader_spine(self._raw_spine)
            self._last_output = {"claim": READER_PROJECTION_CLAIM, "status": "validated"}
            self._last_state = self._project_state(self._raw_spine)
            self._last_label = "reader_projection_validated"
            self._last_reason = "public reader-spine validator accepted the exact produced object"
            return self._observation(step.function_name)

        raise ValueError(f"unsupported reader projection step: {step.function_name}")

    def observe_state(self) -> Any:
        return copy.deepcopy(self._last_state)

    def observe_output(self) -> Any:
        return copy.deepcopy(self._last_output)

    def observe_label(self) -> str:
        return self._last_label

    def observe_reason(self) -> str:
        return self._last_reason

    @staticmethod
    def _project_output(spine: Mapping[str, Any]) -> dict[str, Any]:
        route = spine.get("route_guidance")
        route_mode = route.get("mode") if isinstance(route, Mapping) else None
        return {
            "claim": READER_PROJECTION_CLAIM,
            "source_schema": str(spine.get("schema_version", "")),
            "root_question": spine.get("root_question"),
            "root_conclusion": spine.get("root_conclusion"),
            "artifact_form": spine.get("artifact_form"),
            "route_mode": route_mode,
        }

    @staticmethod
    def _project_state(spine: Mapping[str, Any]) -> dict[str, Any]:
        units = spine.get("major_units", [])
        unit_rows = [row for row in units if isinstance(row, Mapping)] if isinstance(units, list) else []
        return {
            "claim": READER_PROJECTION_CLAIM,
            "status": "ready",
            "major_unit_order": [str(row.get("planned_unit_id")) for row in unit_rows],
            "downstream": [
                {
                    "planned_unit_id": str(row.get("planned_unit_id")),
                    "downstream_unit_ids": [
                        str(child)
                        for child in row.get("forward_link", {}).get("downstream_unit_ids", [])
                    ],
                }
                for row in unit_rows
                if isinstance(row.get("forward_link"), Mapping)
            ],
            "visible_content_ids": [
                str(item.get("content_unit_id"))
                for row in unit_rows
                for item in (row.get("content", []) if isinstance(row.get("content"), list) else [])
                if isinstance(item, Mapping)
            ],
            "limitation_ids": [
                str(item.get("limitation_id"))
                for row in unit_rows
                for item in (row.get("limitation_ids", []) if isinstance(row.get("limitation_ids"), list) else [])
            ],
        }

    def _observation(self, function_name: str) -> ReplayObservation:
        return ReplayObservation(
            function_name=function_name,
            observed_output=self.observe_output(),
            observed_state=self.observe_state(),
            label=self._last_label,
            reason=self._last_reason,
        )


def build_reader_projection_trace(
    request: ReaderProjectionRequest,
    expectation: ReaderProjectionExpectation,
) -> Trace:
    """Create a two-step abstract trace without consulting production output."""

    initial = {"claim": READER_PROJECTION_CLAIM, "status": "not_run"}
    build_state = dict(expectation.state)
    build_state["status"] = "ready"
    validate_output = {"claim": READER_PROJECTION_CLAIM, "status": "validated"}
    return Trace(
        initial_state=initial,
        external_inputs=(request, None),
        metadata=(
            ("claim_boundary", READER_PROJECTION_CLAIM),
            ("evidence_kind", PRODUCTION_READER_CONFORMANCE),
        ),
        steps=(
            TraceStep(
                external_input=request,
                function_name="BuildReaderSpine",
                function_input=request,
                function_output=dict(expectation.output),
                old_state=initial,
                new_state=build_state,
                label=expectation.label,
                reason="Abstract reader projection must preserve the root and ordered reader spine.",
            ),
            TraceStep(
                external_input=None,
                function_name="ValidateReaderSpine",
                function_input=None,
                function_output=validate_output,
                old_state=build_state,
                new_state=build_state,
                label="reader_projection_validated",
                reason="The exact produced projection must pass the public reader-spine contract.",
            ),
        ),
    )


def _current_source_identity() -> dict[str, str]:
    production = _load_production_pipeline()
    files = {
        "reader_projection_adapter": Path(__file__).resolve(),
        "production_reader_pipeline": Path(production.__file__).resolve(),
        "flowguard_conformance": Path(_flowguard_conformance.__file__).resolve(),
    }
    identity: dict[str, str] = {}
    for label, path in files.items():
        if not path.is_file():
            raise RuntimeError(f"conformance source identity is unavailable: {path}")
        identity[label] = sha256_file(path)
    return identity


def _identity_fingerprint(identity: Mapping[str, str]) -> str:
    payload = json.dumps(dict(identity), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _trace_fingerprint(trace: Trace) -> str:
    return "sha256:" + hashlib.sha256(trace.to_json_text(indent=0).encode("utf-8")).hexdigest()


def replay_reader_projection(
    trace: Trace,
    *,
    adapter: ReaderProjectionReplayAdapter | None = None,
) -> ConformanceReport:
    """Run the sole production conformance path through shared FlowGuard."""

    report = replay_trace(
        trace=trace,
        adapter=adapter or ReaderProjectionReplayAdapter(),
    )
    # Keep the shared report semantics, while binding it to the exact current
    # source files and abstract trace that were replayed.  This does not turn
    # structural alignment into production evidence and does not broaden the
    # reader-projection claim.
    identity = _current_source_identity()
    return replace(
        report,
        prediction_id=f"logic-writing:{READER_PROJECTION_CLAIM}:current",
        prediction_fingerprint=_trace_fingerprint(trace),
        model_fingerprint=_identity_fingerprint(identity),
        observation_boundary_id=READER_PROJECTION_CLAIM,
    )


def structural_alignment_result(
    *,
    aligned_ok: bool,
    known_bad_rejected: bool,
    binding_row_count: int,
) -> dict[str, Any]:
    """Return a separate structural result; it never becomes a replay pass."""

    ok = bool(aligned_ok and known_bad_rejected)
    return {
        "claim": STRUCTURAL_ALIGNMENT,
        "status": "pass" if ok else "failed",
        "binding_row_count": int(binding_row_count),
        "known_bad_rejected": bool(known_bad_rejected),
        "claim_boundary": "model-code-test binding only; no production runtime behavior claim",
    }


def conformance_result(
    report: ConformanceReport,
    *,
    include_expected_trace: bool = False,
) -> dict[str, Any]:
    """Serialize a bounded production conformance result.

    FlowGuard keeps the full expected trace on its in-memory report for
    debugging.  The default serialized result deliberately redacts that trace
    because it contains the private ReaderBrief and WriterInput.  A private
    evidence store may request the exact trace explicitly.
    """

    payload = report.to_dict()
    if not include_expected_trace:
        payload["expected_trace"] = None
        # A failed FlowGuard violation repeats the expected step and trace;
        # redact both from the public result for the same private-input reason.
        for violation in payload.get("violations", []):
            if isinstance(violation, dict):
                violation["expected_step"] = None
                violation["trace"] = None
    payload.update(
        {
            "claim": PRODUCTION_READER_CONFORMANCE,
            "claim_boundary": READER_PROJECTION_CLAIM,
            "production_conformance": bool(report.ok),
            "source_identity": _current_source_identity(),
            "structural_alignment": "separate_evidence_required",
        }
    )
    return payload


def write_json(path: str | Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = [
    "PRODUCTION_READER_CONFORMANCE",
    "READER_PROJECTION_CLAIM",
    "ReaderProjectionExpectation",
    "ReaderProjectionReplayAdapter",
    "ReaderProjectionRequest",
    "STRUCTURAL_ALIGNMENT",
    "_abstract_projection_from_plan",
    "build_reader_projection_trace",
    "conformance_result",
    "replay_reader_projection",
    "structural_alignment_result",
    "write_json",
]
