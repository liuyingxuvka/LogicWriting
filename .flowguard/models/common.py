"""Shared executable state machines for Logic Writing.

Every block implements the FlowGuard contract::

    Input x State -> Set(Output x State)

The agent-operation plane models user work.  The development-process plane
models validation, installation, publication, and predecessor retirement.
There is no implicit edge between the two planes.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


FINAL_OWNERS = ("investigation", "academic-writing")
NATIVE_OWNERS = (
    "sourceguard",
    "logicguard",
    "traceguard",
    "flowguard",
    "documents",
    "pdf",
)
NATIVE_EVIDENCE_DOMAINS = {
    "sourceguard": ("source_observation", "source_depth", "source_discovery", "source_library"),
    "logicguard": ("argument_model", "structured_artifact", "model_depth", "artifact_synthesis", "citation_semantics"),
    "traceguard": ("temporal_trace", "causal_trace", "competing_storyline", "prediction_boundary"),
    "flowguard": ("process_model", "process_freshness", "development_validation"),
    "documents": ("document_content", "document_mutation", "document_render", "document_visual"),
    "pdf": ("pdf_content", "pdf_render", "pdf_visual"),
}
CORE_PACKET_EVIDENCE = (
    ("sourceguard", "source_observation"),
    ("logicguard", "argument_model"),
)
NON_PASSING = (
    "not_run",
    "stale",
    "provider_unavailable",
    "dependency_unavailable",
    "access_gap",
    "render_not_run",
    "bounded",
    "downgraded",
    "partial",
    "blocked",
    "failed",
    "saved_but_modeling_incomplete",
)

OPERATION_ACTIONS = (
    "select_route",
    "invoke_adapter",
    "assemble_packet",
    "handoff_packet",
    "build_reader_brief",
    "write_artifact",
    "record_revision_provenance",
    "audit_artifact",
    "update_artifact",
    "source_changed",
    "close_operation",
)
DEVELOPMENT_ACTIONS = (
    "operation_artifact_changed",
    "development_input_changed",
    "freeze_validation",
    "stage_install",
    "activate_install",
    "project_global_route",
    "publish_release",
    "verify_backups",
    "quarantine_legacy_local",
    "recheck_after_first_privatization",
    "privatize_legacy_remote",
    "record_remote_deletion_handoff",
)
ADAPTER_STATUSES = ("current_pass",) + NON_PASSING
AUDIT_STATUSES = (
    "passed+passed",
    "passed+failed",
    "passed+not_run",
    "failed+passed",
    "failed+failed",
    "failed+not_run",
)


@dataclass(frozen=True)
class OperationEvent:
    """One abstract external input to the agent-operation plane."""

    action: str
    fingerprint: str = ""
    owner: str = ""
    native_owner: str = ""
    evidence_domain: str = ""
    status: str = ""
    child_routes: tuple[str, ...] = ()
    artifact_fingerprint: str = ""
    target: str = ""
    reason: str = ""


@dataclass(frozen=True)
class OperationState:
    """State owned by Logic Writing while producing one reader artifact."""

    plane: str = "agent_operation"
    request_fingerprint: str = ""
    route_owner: str = ""
    child_routes: tuple[str, ...] = ()
    route_status: str = "not_run"
    adapter_receipts: tuple[str, ...] = ()
    adapter_status: str = "not_run"
    packet_fingerprint: str = ""
    packet_status: str = "not_run"
    packet_current: bool = False
    handoff_status: str = "not_run"
    brief_fingerprint: str = ""
    brief_status: str = "not_run"
    brief_current: bool = False
    artifact_fingerprint: str = ""
    artifact_bound_brief: str = ""
    artifact_status: str = "not_run"
    artifact_current: bool = False
    revision_provenance_status: str = "not_run"
    deterministic_audit_status: str = "not_run"
    judgment_status: str = "not_run"
    audit_artifact_fingerprint: str = ""
    closure_status: str = "not_run"
    closure_artifact_fingerprint: str = ""
    closure_owner: str = ""
    no_progress_count: int = 0
    residual_risk: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    terminal: bool = False


@dataclass(frozen=True)
class DevelopmentEvent:
    """One abstract external input to the development-process plane."""

    action: str
    fingerprint: str = ""
    status: str = ""
    target: str = ""
    reason: str = ""


@dataclass(frozen=True)
class DevelopmentState:
    """State for source validation, installation, release, and retirement."""

    plane: str = "development_process"
    source_fingerprint: str = "source:v1"
    model_fingerprint: str = "model:v1"
    contract_fingerprint: str = "contract:v1"
    validation_fingerprint: str = ""
    validation_status: str = "not_run"
    validation_current: bool = False
    stage_fingerprint: str = ""
    stage_status: str = "not_run"
    active_fingerprint: str = ""
    install_status: str = "not_run"
    rollback_available: bool = True
    global_route_status: str = "not_run"
    release_status: str = "not_run"
    release_fingerprint: str = ""
    backups_verified: bool = False
    retired_local: tuple[str, ...] = ()
    privatized_remote: tuple[str, ...] = ()
    first_privatization_health_rechecked: bool = False
    visibility_receipts: tuple[str, ...] = ()
    user_deletion_handoff_status: str = "not_run"
    errors: tuple[str, ...] = ()
    terminal: bool = False


class _OperationBlock:
    accepted_input_type = OperationEvent
    input_description = "OperationEvent plus the current immutable OperationState"
    output_description = "The same event plus every permitted successor OperationState"
    idempotency = "same event and state yield the same successor set"

    @staticmethod
    def _pass(event: OperationEvent, state: OperationState, label: str) -> tuple[FunctionResult, ...]:
        return (FunctionResult(event, state, label=label),)


def _receipt_parts(receipt: str) -> tuple[str, str, str, str]:
    """Parse the canonical owner/status/domain/fingerprint model receipt."""

    parts = receipt.split(":", 3)
    if len(parts) != 4:
        return "", "", "", ""
    return parts[0], parts[1], parts[2], parts[3]


def _current_receipt_domains(receipts: tuple[str, ...]) -> set[tuple[str, str]]:
    return {
        (owner, domain)
        for receipt in receipts
        for owner, status, domain, _fingerprint in (_receipt_parts(receipt),)
        if status == "current_pass"
    }


class RejectUnknownOperationEvent(_OperationBlock):
    """Make the finite operation boundary visible before any side effect."""

    name = "RejectUnknownOperationEvent"
    reads = ("terminal",)
    writes = ("errors", "terminal")

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action == "invoke_adapter":
            invalid_status = event.status not in ADAPTER_STATUSES
        elif event.action == "audit_artifact":
            invalid_status = event.status not in AUDIT_STATUSES
        elif event.action == "record_revision_provenance":
            invalid_status = event.status not in ADAPTER_STATUSES
        else:
            invalid_status = bool(event.status)
        if event.action in OPERATION_ACTIONS and not invalid_status:
            return self._pass(event, state, "operation_event_admitted")
        return (
            FunctionResult(
                replace(event, action="__blocked__"),
                replace(
                    state,
                    errors=state.errors + ("unknown_or_malformed_operation_event",),
                    terminal=True,
                ),
                label="operation_event_blocked_before_side_effect",
            ),
        )


class SelectRoute(_OperationBlock):
    name = "SelectRoute"
    reads = ("request_fingerprint", "route_owner")
    writes = (
        "request_fingerprint",
        "route_owner",
        "child_routes",
        "route_status",
        "closure_status",
        "errors",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "select_route":
            return self._pass(event, state, "select_route_not_requested")
        if event.owner not in FINAL_OWNERS:
            next_state = replace(
                state,
                request_fingerprint=event.fingerprint,
                route_owner="",
                child_routes=(),
                route_status="blocked",
                errors=state.errors + ("route_owner_ambiguous_or_invalid",),
            )
            return (FunctionResult(event, next_state, label="route_blocked"),)
        illegal_children = tuple(route for route in event.child_routes if route not in FINAL_OWNERS)
        duplicate_owner = event.owner in event.child_routes
        if illegal_children or duplicate_owner or len(set(event.child_routes)) != len(event.child_routes):
            next_state = replace(
                state,
                request_fingerprint=event.fingerprint,
                route_owner=event.owner,
                route_status="blocked",
                errors=state.errors + ("invalid_child_route_set",),
            )
            return (FunctionResult(event, next_state, label="route_blocked"),)
        return (
            FunctionResult(
                replace(event, action="__blocked__"),
                replace(
                    state,
                    request_fingerprint=event.fingerprint,
                    route_owner=event.owner,
                    child_routes=event.child_routes,
                    route_status="current_pass",
                    closure_status="stale" if state.closure_status == "passed" else state.closure_status,
                    terminal=False,
                ),
                label="route_selected",
            ),
        )


class InvokeTypedGuardAdapter(_OperationBlock):
    name = "InvokeTypedGuardAdapter"
    reads = ("route_status", "route_owner", "adapter_receipts")
    writes = (
        "adapter_receipts",
        "adapter_status",
        "packet_current",
        "packet_status",
        "errors",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "invoke_adapter":
            return self._pass(event, state, "adapter_not_requested")
        domain_is_native = event.evidence_domain in NATIVE_EVIDENCE_DOMAINS.get(event.native_owner, ())
        if state.route_status != "current_pass" or event.native_owner not in NATIVE_OWNERS or not domain_is_native:
            return (
                FunctionResult(
                    event,
                    replace(
                        state,
                        adapter_status="blocked",
                        errors=state.errors + ("native_adapter_owner_domain_unavailable_or_route_stale",),
                    ),
                    label="adapter_blocked",
                ),
            )
        receipt = f"{event.native_owner}:{event.status}:{event.evidence_domain}:{event.fingerprint}"
        receipts = tuple(
            item
            for item in state.adapter_receipts
            if _receipt_parts(item)[:3:2] != (event.native_owner, event.evidence_domain)
        )
        receipts += (receipt,)
        status = "current_pass" if event.status == "current_pass" else event.status or "blocked"
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    adapter_receipts=receipts,
                    adapter_status=status,
                    packet_current=False,
                    packet_status="stale" if state.packet_status != "not_run" else state.packet_status,
                    terminal=False,
                ),
                label="adapter_receipt_recorded",
            ),
        )


class AssembleResearchPacket(_OperationBlock):
    name = "AssembleResearchPacket"
    reads = ("adapter_receipts", "adapter_status", "route_status")
    writes = (
        "packet_fingerprint",
        "packet_status",
        "packet_current",
        "handoff_status",
        "brief_current",
        "residual_risk",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "assemble_packet":
            return self._pass(event, state, "packet_not_requested")
        if state.route_status != "current_pass" or not state.adapter_receipts:
            return (
                FunctionResult(
                    event,
                    replace(state, packet_status="blocked", packet_current=False, residual_risk=("missing_native_receipts",)),
                    label="packet_blocked",
                ),
            )
        nonpassing = tuple(item for item in state.adapter_receipts if _receipt_parts(item)[1] != "current_pass")
        if nonpassing:
            return (
                FunctionResult(
                    event,
                    replace(
                        state,
                        packet_fingerprint=event.fingerprint,
                        packet_status="partial",
                        packet_current=False,
                        residual_risk=("nonpassing_native_receipt",),
                    ),
                    label="packet_partial",
                ),
            )
        missing_core = tuple(
            f"{owner}:{domain}"
            for owner, domain in CORE_PACKET_EVIDENCE
            if (owner, domain) not in _current_receipt_domains(state.adapter_receipts)
        )
        if missing_core:
            return (
                FunctionResult(
                    event,
                    replace(
                        state,
                        packet_fingerprint=event.fingerprint,
                        packet_status="blocked",
                        packet_current=False,
                        residual_risk=tuple(f"missing_core_content_evidence:{item}" for item in missing_core),
                    ),
                    label="packet_missing_core_content",
                ),
            )
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    packet_fingerprint=event.fingerprint,
                    packet_status="current_pass",
                    packet_current=True,
                    handoff_status="not_run",
                    brief_current=False,
                    residual_risk=(),
                    terminal=False,
                ),
                label="packet_current",
            ),
        )


class HandoffResearchPacket(_OperationBlock):
    name = "HandoffResearchPacket"
    reads = ("packet_fingerprint", "packet_current", "route_owner", "child_routes")
    writes = ("handoff_status", "errors")

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "handoff_packet":
            return self._pass(event, state, "handoff_not_requested")
        if not state.packet_current or event.fingerprint != state.packet_fingerprint:
            return (
                FunctionResult(event, replace(state, handoff_status="blocked", errors=state.errors + ("packet_identity_mismatch",)), label="handoff_blocked"),
            )
        return (FunctionResult(event, replace(state, handoff_status="current_pass"), label="packet_handoff_verified"),)


class BuildReaderBrief(_OperationBlock):
    name = "BuildReaderBrief"
    reads = ("packet_current", "handoff_status", "packet_fingerprint")
    writes = ("brief_fingerprint", "brief_status", "brief_current", "artifact_current", "terminal")

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "build_reader_brief":
            return self._pass(event, state, "brief_not_requested")
        if not state.packet_current or state.handoff_status not in {"current_pass", "not_run"}:
            return (FunctionResult(event, replace(state, brief_status="blocked", brief_current=False), label="brief_blocked"),)
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    brief_fingerprint=event.fingerprint,
                    brief_status="current_pass",
                    brief_current=True,
                    artifact_current=False,
                    terminal=False,
                ),
                label="reader_brief_current",
            ),
        )


class WriteArtifact(_OperationBlock):
    name = "WriteArtifact"
    reads = ("brief_current", "brief_fingerprint", "route_owner")
    writes = (
        "artifact_fingerprint",
        "artifact_bound_brief",
        "artifact_status",
        "artifact_current",
        "revision_provenance_status",
        "deterministic_audit_status",
        "judgment_status",
        "audit_artifact_fingerprint",
        "side_effects",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "write_artifact":
            return self._pass(event, state, "write_not_requested")
        if not state.brief_current or not state.route_owner:
            return (FunctionResult(event, replace(state, artifact_status="blocked", artifact_current=False), label="artifact_blocked"),)
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    artifact_fingerprint=event.artifact_fingerprint or event.fingerprint,
                    artifact_bound_brief=state.brief_fingerprint,
                    artifact_status="current",
                    artifact_current=True,
                    revision_provenance_status="not_run",
                    deterministic_audit_status="not_run",
                    judgment_status="not_run",
                    audit_artifact_fingerprint="",
                    side_effects=state.side_effects + ("reader_artifact_written",),
                    terminal=False,
                ),
                label="artifact_written",
            ),
        )


class RecordRevisionProvenance(_OperationBlock):
    name = "RecordRevisionProvenance"
    reads = ("route_owner", "artifact_current", "artifact_fingerprint")
    writes = ("revision_provenance_status", "terminal")

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "record_revision_provenance":
            return self._pass(event, state, "revision_provenance_not_requested")
        if state.route_owner != "academic-writing":
            return self._pass(event, state, "revision_provenance_not_applicable")
        current = state.artifact_current and event.status == "current_pass"
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    revision_provenance_status="current_pass" if current else (event.status or "blocked"),
                    terminal=False,
                ),
                label="revision_provenance_current" if current else "revision_provenance_blocked",
            ),
        )


class AuditActualArtifact(_OperationBlock):
    name = "AuditActualArtifact"
    reads = ("artifact_fingerprint", "artifact_current")
    writes = ("deterministic_audit_status", "judgment_status", "audit_artifact_fingerprint", "terminal")

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "audit_artifact":
            return self._pass(event, state, "audit_not_requested")
        artifact_id = event.artifact_fingerprint or event.fingerprint
        if not state.artifact_current or artifact_id != state.artifact_fingerprint:
            return (
                FunctionResult(
                    event,
                    replace(state, deterministic_audit_status="blocked", judgment_status="not_run"),
                    label="audit_blocked",
                ),
            )
        deterministic, _, judgment = (event.status or "failed").partition("+")
        judgment = judgment or "not_run"
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    deterministic_audit_status=deterministic,
                    judgment_status=judgment,
                    audit_artifact_fingerprint=artifact_id,
                    terminal=False,
                ),
                label="actual_artifact_audited",
            ),
        )


class UpdateArtifact(_OperationBlock):
    name = "UpdateArtifact"
    reads = ("artifact_fingerprint", "audit_artifact_fingerprint", "closure_status")
    writes = (
        "artifact_fingerprint",
        "revision_provenance_status",
        "deterministic_audit_status",
        "judgment_status",
        "closure_status",
        "closure_artifact_fingerprint",
        "errors",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "update_artifact":
            return self._pass(event, state, "update_not_requested")
        if not state.artifact_current:
            return (FunctionResult(event, replace(state, errors=state.errors + ("cannot_update_missing_artifact",)), label="update_blocked"),)
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    artifact_fingerprint=event.artifact_fingerprint or event.fingerprint,
                    revision_provenance_status=(
                        "stale" if state.route_owner == "academic-writing" else state.revision_provenance_status
                    ),
                    deterministic_audit_status="stale",
                    judgment_status="stale",
                    closure_status="stale",
                    closure_artifact_fingerprint="",
                    terminal=False,
                ),
                label="artifact_updated_audits_stale",
            ),
        )


class PropagateOperationStaleness(_OperationBlock):
    name = "PropagateOperationStaleness"
    reads = ("packet_current", "brief_current", "artifact_current", "closure_status")
    writes = (
        "packet_status",
        "packet_current",
        "handoff_status",
        "brief_status",
        "brief_current",
        "artifact_status",
        "artifact_current",
        "revision_provenance_status",
        "deterministic_audit_status",
        "judgment_status",
        "closure_status",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "source_changed":
            return self._pass(event, state, "operation_staleness_not_requested")
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    packet_status="stale" if state.packet_status != "not_run" else "not_run",
                    packet_current=False,
                    handoff_status="stale" if state.handoff_status != "not_run" else "not_run",
                    brief_status="stale" if state.brief_status != "not_run" else "not_run",
                    brief_current=False,
                    artifact_status="stale" if state.artifact_status != "not_run" else "not_run",
                    artifact_current=False,
                    revision_provenance_status=(
                        "stale" if state.revision_provenance_status != "not_run" else "not_run"
                    ),
                    deterministic_audit_status="stale" if state.deterministic_audit_status != "not_run" else "not_run",
                    judgment_status="stale" if state.judgment_status != "not_run" else "not_run",
                    closure_status="stale" if state.closure_status != "not_run" else "not_run",
                    terminal=False,
                ),
                label="operation_dependents_stale",
            ),
        )


class CloseOperation(_OperationBlock):
    name = "CloseOperation"
    reads = (
        "route_owner",
        "packet_current",
        "brief_current",
        "artifact_current",
        "revision_provenance_status",
        "deterministic_audit_status",
        "judgment_status",
    )
    writes = (
        "closure_status",
        "closure_owner",
        "closure_artifact_fingerprint",
        "no_progress_count",
        "residual_risk",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "close_operation":
            return self._pass(event, state, "closure_not_requested")
        ready = (
            state.route_owner in FINAL_OWNERS
            and state.packet_current
            and state.brief_current
            and state.artifact_current
            and state.artifact_bound_brief == state.brief_fingerprint
            and (
                state.route_owner != "academic-writing"
                or state.revision_provenance_status == "current_pass"
            )
            and state.deterministic_audit_status == "passed"
            and state.judgment_status == "passed"
            and state.audit_artifact_fingerprint == state.artifact_fingerprint
        )
        if ready:
            return (
                FunctionResult(
                    event,
                    replace(
                        state,
                        closure_status="passed",
                        closure_owner=state.route_owner,
                        closure_artifact_fingerprint=state.artifact_fingerprint,
                        no_progress_count=0,
                        terminal=True,
                    ),
                    label="operation_closed",
                ),
            )
        repeats = state.no_progress_count + 1
        terminal = repeats >= 2
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    closure_status="no_progress_blocked" if terminal else "blocked",
                    closure_owner=state.route_owner,
                    no_progress_count=repeats,
                    residual_risk=tuple(dict.fromkeys(state.residual_risk + ("required_current_evidence_missing",))),
                    terminal=terminal,
                ),
                label="no_progress_terminated" if terminal else "closure_blocked",
            ),
        )


class _DevelopmentBlock:
    accepted_input_type = DevelopmentEvent
    input_description = "DevelopmentEvent plus the current immutable DevelopmentState"
    output_description = "The same event plus every permitted successor DevelopmentState"
    idempotency = "same event and state yield the same successor set"

    @staticmethod
    def _pass(event: DevelopmentEvent, state: DevelopmentState, label: str) -> tuple[FunctionResult, ...]:
        return (FunctionResult(event, state, label=label),)


class RejectUnknownDevelopmentEvent(_DevelopmentBlock):
    """Block unknown development events before install or visibility effects."""

    name = "RejectUnknownDevelopmentEvent"
    reads = ("terminal",)
    writes = ("errors", "terminal")

    def apply(self, event: DevelopmentEvent, state: DevelopmentState) -> Iterable[FunctionResult]:
        status_actions = {
            "freeze_validation",
            "verify_backups",
            "recheck_after_first_privatization",
            "record_remote_deletion_handoff",
        }
        invalid_status = (
            event.action in status_actions and event.status not in {"current_pass", "blocked", "failed"}
        ) or (event.action not in status_actions and bool(event.status))
        if event.action in DEVELOPMENT_ACTIONS and not invalid_status:
            return self._pass(event, state, "development_event_admitted")
        return (
            FunctionResult(
                replace(event, action="__blocked__"),
                replace(
                    state,
                    errors=state.errors + ("unknown_or_malformed_development_event",),
                    terminal=True,
                ),
                label="development_event_blocked_before_side_effect",
            ),
        )


class PropagateDevelopmentStaleness(_DevelopmentBlock):
    name = "PropagateDevelopmentStaleness"
    reads = ("source_fingerprint", "model_fingerprint", "contract_fingerprint", "validation_current")
    writes = (
        "source_fingerprint",
        "model_fingerprint",
        "contract_fingerprint",
        "validation_status",
        "validation_current",
        "stage_status",
    )

    def apply(self, event: DevelopmentEvent, state: DevelopmentState) -> Iterable[FunctionResult]:
        if event.action == "operation_artifact_changed":
            return self._pass(event, state, "operation_change_does_not_stale_development")
        if event.action != "development_input_changed":
            return self._pass(event, state, "development_staleness_not_requested")
        field = event.target or "source"
        updates = {
            "validation_status": "stale" if state.validation_status != "not_run" else "not_run",
            "validation_current": False,
            "stage_status": "stale" if state.stage_status != "not_run" else "not_run",
        }
        if field == "model":
            updates["model_fingerprint"] = event.fingerprint
        elif field == "contract":
            updates["contract_fingerprint"] = event.fingerprint
        else:
            updates["source_fingerprint"] = event.fingerprint
        return (FunctionResult(event, replace(state, **updates), label="development_receipts_stale"),)


class FreezeValidation(_DevelopmentBlock):
    name = "FreezeValidation"
    reads = ("source_fingerprint", "model_fingerprint", "contract_fingerprint")
    writes = ("validation_fingerprint", "validation_status", "validation_current")

    def apply(self, event: DevelopmentEvent, state: DevelopmentState) -> Iterable[FunctionResult]:
        if event.action != "freeze_validation":
            return self._pass(event, state, "validation_not_requested")
        current = event.status == "current_pass" and bool(event.fingerprint)
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    validation_fingerprint=event.fingerprint,
                    validation_status="current_pass" if current else (event.status or "blocked"),
                    validation_current=current,
                ),
                label="validation_frozen" if current else "validation_blocked",
            ),
        )


class StageInstall(_DevelopmentBlock):
    name = "StageInstall"
    reads = ("validation_fingerprint", "validation_current")
    writes = ("stage_fingerprint", "stage_status")

    def apply(self, event: DevelopmentEvent, state: DevelopmentState) -> Iterable[FunctionResult]:
        if event.action != "stage_install":
            return self._pass(event, state, "stage_not_requested")
        if not state.validation_current or event.fingerprint != state.validation_fingerprint:
            return (FunctionResult(event, replace(state, stage_status="blocked"), label="stage_blocked"),)
        return (FunctionResult(event, replace(state, stage_fingerprint=event.fingerprint, stage_status="current_pass"), label="install_staged"),)


class ActivateInstall(_DevelopmentBlock):
    name = "ActivateInstall"
    reads = ("stage_fingerprint", "stage_status", "rollback_available")
    writes = ("active_fingerprint", "install_status")

    def apply(self, event: DevelopmentEvent, state: DevelopmentState) -> Iterable[FunctionResult]:
        if event.action != "activate_install":
            return self._pass(event, state, "activation_not_requested")
        if state.stage_status != "current_pass" or not state.rollback_available or event.fingerprint != state.stage_fingerprint:
            return (FunctionResult(event, replace(state, install_status="blocked"), label="activation_blocked"),)
        return (FunctionResult(event, replace(state, active_fingerprint=event.fingerprint, install_status="current_pass"), label="install_activated"),)


class ProjectGlobalRoute(_DevelopmentBlock):
    name = "ProjectGlobalRoute"
    reads = ("active_fingerprint", "install_status")
    writes = ("global_route_status",)

    def apply(self, event: DevelopmentEvent, state: DevelopmentState) -> Iterable[FunctionResult]:
        if event.action != "project_global_route":
            return self._pass(event, state, "global_route_not_requested")
        ok = state.install_status == "current_pass" and event.fingerprint == state.active_fingerprint
        return (FunctionResult(event, replace(state, global_route_status="current_pass" if ok else "blocked"), label="global_route_current" if ok else "global_route_blocked"),)


class PublishRelease(_DevelopmentBlock):
    name = "PublishRelease"
    reads = ("validation_current", "install_status", "global_route_status", "active_fingerprint")
    writes = ("release_status", "release_fingerprint")

    def apply(self, event: DevelopmentEvent, state: DevelopmentState) -> Iterable[FunctionResult]:
        if event.action != "publish_release":
            return self._pass(event, state, "release_not_requested")
        ok = (
            state.validation_current
            and state.install_status == "current_pass"
            and state.global_route_status == "current_pass"
            and event.fingerprint == state.active_fingerprint
        )
        return (
            FunctionResult(
                event,
                replace(state, release_status="current_pass" if ok else "blocked", release_fingerprint=event.fingerprint if ok else ""),
                label="release_published" if ok else "release_blocked",
            ),
        )


class VerifyBackups(_DevelopmentBlock):
    name = "VerifyBackups"
    reads = ("backups_verified",)
    writes = ("backups_verified",)

    def apply(self, event: DevelopmentEvent, state: DevelopmentState) -> Iterable[FunctionResult]:
        if event.action != "verify_backups":
            return self._pass(event, state, "backup_check_not_requested")
        return (FunctionResult(event, replace(state, backups_verified=event.status == "current_pass"), label="backups_verified" if event.status == "current_pass" else "backups_blocked"),)


class QuarantineLegacyLocal(_DevelopmentBlock):
    name = "QuarantineLegacyLocal"
    reads = ("release_status", "global_route_status", "backups_verified", "retired_local")
    writes = ("retired_local", "errors")

    def apply(self, event: DevelopmentEvent, state: DevelopmentState) -> Iterable[FunctionResult]:
        if event.action != "quarantine_legacy_local":
            return self._pass(event, state, "local_retirement_not_requested")
        ok = state.release_status == "current_pass" and state.global_route_status == "current_pass" and state.backups_verified
        if not ok or event.target not in {"research", "academic"}:
            return (FunctionResult(event, replace(state, errors=state.errors + ("local_retirement_gate_failed",)), label="local_retirement_blocked"),)
        retired = tuple(dict.fromkeys(state.retired_local + (event.target,)))
        return (FunctionResult(event, replace(state, retired_local=retired), label="legacy_local_quarantined"),)


class RecheckAfterFirstPrivatization(_DevelopmentBlock):
    name = "RecheckAfterFirstPrivatization"
    reads = ("privatized_remote", "release_status", "install_status", "global_route_status")
    writes = ("first_privatization_health_rechecked",)

    def apply(self, event: DevelopmentEvent, state: DevelopmentState) -> Iterable[FunctionResult]:
        if event.action != "recheck_after_first_privatization":
            return self._pass(event, state, "health_recheck_not_requested")
        ok = (
            state.privatized_remote == ("research",)
            and state.release_status == "current_pass"
            and state.install_status == "current_pass"
            and state.global_route_status == "current_pass"
            and event.status == "current_pass"
        )
        return (
            FunctionResult(
                event,
                replace(state, first_privatization_health_rechecked=ok),
                label="first_privatization_health_current" if ok else "health_recheck_blocked",
            ),
        )


class PrivatizeLegacyRemote(_DevelopmentBlock):
    name = "PrivatizeLegacyRemote"
    reads = (
        "release_status",
        "install_status",
        "global_route_status",
        "backups_verified",
        "retired_local",
        "privatized_remote",
        "first_privatization_health_rechecked",
    )
    writes = ("privatized_remote", "visibility_receipts", "errors")

    def apply(self, event: DevelopmentEvent, state: DevelopmentState) -> Iterable[FunctionResult]:
        if event.action != "privatize_legacy_remote":
            return self._pass(event, state, "remote_retirement_not_requested")
        common = (
            state.release_status == "current_pass"
            and state.install_status == "current_pass"
            and state.global_route_status == "current_pass"
            and state.backups_verified
            and set(state.retired_local) == {"research", "academic"}
        )
        order_ok = (
            event.target == "research" and not state.privatized_remote
        ) or (
            event.target == "academic"
            and state.privatized_remote == ("research",)
            and state.first_privatization_health_rechecked
        )
        if not common or not order_ok:
            return (FunctionResult(event, replace(state, errors=state.errors + ("remote_retirement_gate_or_order_failed",)), label="remote_retirement_blocked"),)
        privatized = state.privatized_remote + (event.target,)
        receipt = f"private:{event.target}:{event.fingerprint}"
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    privatized_remote=privatized,
                    visibility_receipts=state.visibility_receipts + (receipt,),
                ),
                label="legacy_remote_privatized",
            ),
        )


class RecordRemoteDeletionHandoff(_DevelopmentBlock):
    name = "RecordRemoteDeletionHandoff"
    reads = ("privatized_remote", "visibility_receipts", "user_deletion_handoff_status")
    writes = ("user_deletion_handoff_status", "errors", "terminal")

    def apply(self, event: DevelopmentEvent, state: DevelopmentState) -> Iterable[FunctionResult]:
        if event.action != "record_remote_deletion_handoff":
            return self._pass(event, state, "deletion_handoff_not_requested")
        ok = (
            state.privatized_remote == ("research", "academic")
            and len(state.visibility_receipts) == 2
            and event.status == "current_pass"
        )
        if not ok:
            return (
                FunctionResult(
                    event,
                    replace(
                        state,
                        user_deletion_handoff_status="blocked",
                        errors=state.errors + ("remote_deletion_handoff_gate_failed",),
                    ),
                    label="remote_deletion_handoff_blocked",
                ),
            )
        return (
            FunctionResult(
                event,
                replace(state, user_deletion_handoff_status="current_pass", terminal=True),
                label="remote_deletion_handoff_recorded",
            ),
        )


OPERATION_BLOCKS = (
    RejectUnknownOperationEvent(),
    SelectRoute(),
    InvokeTypedGuardAdapter(),
    AssembleResearchPacket(),
    HandoffResearchPacket(),
    BuildReaderBrief(),
    WriteArtifact(),
    RecordRevisionProvenance(),
    AuditActualArtifact(),
    UpdateArtifact(),
    PropagateOperationStaleness(),
    CloseOperation(),
)

DEVELOPMENT_BLOCKS = (
    RejectUnknownDevelopmentEvent(),
    PropagateDevelopmentStaleness(),
    FreezeValidation(),
    StageInstall(),
    ActivateInstall(),
    ProjectGlobalRoute(),
    PublishRelease(),
    VerifyBackups(),
    QuarantineLegacyLocal(),
    RecheckAfterFirstPrivatization(),
    PrivatizeLegacyRemote(),
    RecordRemoteDeletionHandoff(),
)


def operation_workflow(name: str = "logic_writing_agent_operation") -> Workflow:
    return Workflow(OPERATION_BLOCKS, name=name)


def development_workflow(name: str = "logic_writing_development_process") -> Workflow:
    return Workflow(DEVELOPMENT_BLOCKS, name=name)


def _fail(name: str, message: str) -> InvariantResult:
    return InvariantResult.fail(message, {"violation": name})


def exactly_one_final_owner(state: OperationState, trace) -> InvariantResult:
    del trace
    if state.route_status == "current_pass" and state.route_owner not in FINAL_OWNERS:
        return _fail("exactly_one_final_owner", "a current route lacks one recognized final owner")
    if state.route_owner and state.route_owner in state.child_routes:
        return _fail("exactly_one_final_owner", "the final owner is duplicated as its own child")
    return InvariantResult.pass_()


def specialist_authority_preserved(state: OperationState, trace) -> InvariantResult:
    del trace
    for receipt in state.adapter_receipts:
        owner, _status, domain, _fingerprint = _receipt_parts(receipt)
        if owner not in NATIVE_OWNERS or domain not in NATIVE_EVIDENCE_DOMAINS.get(owner, ()):
            return _fail("specialist_authority_preserved", f"unknown native owner/domain in {receipt}")
    return InvariantResult.pass_()


def packet_requires_core_content(state: OperationState, trace) -> InvariantResult:
    del trace
    if not state.packet_current:
        return InvariantResult.pass_()
    current = _current_receipt_domains(state.adapter_receipts)
    missing = tuple(item for item in CORE_PACKET_EVIDENCE if item not in current)
    if missing:
        return _fail(
            "packet_requires_core_content",
            f"packet passed without source observation and argument-model evidence: {missing!r}",
        )
    return InvariantResult.pass_()


def actual_artifact_required_for_audit(state: OperationState, trace) -> InvariantResult:
    del trace
    if state.deterministic_audit_status == "passed" and (
        not state.artifact_fingerprint or state.audit_artifact_fingerprint != state.artifact_fingerprint
    ):
        return _fail("actual_artifact_required_for_audit", "passing audit is not bound to the actual current artifact")
    return InvariantResult.pass_()


def closure_requires_current_chain(state: OperationState, trace) -> InvariantResult:
    del trace
    if state.closure_status != "passed":
        return InvariantResult.pass_()
    required = (
        state.packet_current,
        state.brief_current,
        state.artifact_current,
        state.route_owner != "academic-writing" or state.revision_provenance_status == "current_pass",
        state.deterministic_audit_status == "passed",
        state.judgment_status == "passed",
        state.audit_artifact_fingerprint == state.artifact_fingerprint,
        state.closure_artifact_fingerprint == state.artifact_fingerprint,
        state.closure_owner == state.route_owner,
    )
    if not all(required):
        return _fail("closure_requires_current_chain", "closure passed without a current source-to-artifact evidence chain")
    return InvariantResult.pass_()


def bounded_child_never_closes_parent(state: OperationState, trace) -> InvariantResult:
    del trace
    if state.closure_status == "passed" and state.closure_owner in state.child_routes:
        return _fail("bounded_child_never_closes_parent", "a child route issued final closure")
    return InvariantResult.pass_()


def operation_terminal_is_visible(state: OperationState, trace) -> InvariantResult:
    del trace
    if state.no_progress_count >= 2 and not state.terminal:
        return _fail("operation_terminal_is_visible", "repeated identical no-progress attempts did not terminate visibly")
    return InvariantResult.pass_()


OPERATION_INVARIANTS = (
    Invariant("exactly_one_final_owner", "One request has exactly one final owner", exactly_one_final_owner),
    Invariant("specialist_authority_preserved", "Every specialist receipt keeps its native owner", specialist_authority_preserved),
    Invariant("packet_requires_core_content", "A passing packet contains current source and logic evidence", packet_requires_core_content),
    Invariant("actual_artifact_required_for_audit", "Passing reader audit binds actual current text", actual_artifact_required_for_audit),
    Invariant("closure_requires_current_chain", "Final closure requires the current evidence chain", closure_requires_current_chain),
    Invariant("bounded_child_never_closes_parent", "Child routes close only bounded obligations", bounded_child_never_closes_parent),
    Invariant("operation_terminal_is_visible", "Repeated no-progress attempts terminate visibly", operation_terminal_is_visible),
)


def release_requires_frozen_validation(state: DevelopmentState, trace) -> InvariantResult:
    del trace
    if state.release_status == "current_pass" and not (
        state.validation_current
        and state.install_status == "current_pass"
        and state.global_route_status == "current_pass"
        and state.release_fingerprint == state.active_fingerprint
    ):
        return _fail("release_requires_frozen_validation", "release passed without current frozen validation and active install")
    return InvariantResult.pass_()


def retirement_requires_recoverable_cutover(state: DevelopmentState, trace) -> InvariantResult:
    del trace
    if state.privatized_remote and not (
        state.backups_verified
        and state.release_status == "current_pass"
        and state.install_status == "current_pass"
        and state.global_route_status == "current_pass"
        and set(state.retired_local) == {"research", "academic"}
    ):
        return _fail("retirement_requires_recoverable_cutover", "legacy remote retired before recoverable new cutover")
    return InvariantResult.pass_()


def retirement_order_is_sequential(state: DevelopmentState, trace) -> InvariantResult:
    del trace
    if state.privatized_remote not in {(), ("research",), ("research", "academic")}:
        return _fail("retirement_order_is_sequential", f"invalid retirement order {state.privatized_remote!r}")
    if state.privatized_remote == ("research", "academic") and not state.first_privatization_health_rechecked:
        return _fail("retirement_order_is_sequential", "academic repository privatized without post-research health recheck")
    return InvariantResult.pass_()


def operation_changes_do_not_stale_release(state: DevelopmentState, trace) -> InvariantResult:
    del trace
    if state.source_fingerprint == "operation-artifact":
        return _fail("operation_changes_do_not_stale_release", "operation artifact leaked into development source identity")
    return InvariantResult.pass_()


def remote_visibility_side_effect_at_most_once(state: DevelopmentState, trace) -> InvariantResult:
    del trace
    if len(state.privatized_remote) != len(set(state.privatized_remote)):
        return _fail("remote_visibility_side_effect_at_most_once", "a legacy remote was privatized more than once")
    targets = tuple(receipt.split(":", 2)[1] for receipt in state.visibility_receipts)
    if len(targets) != len(set(targets)):
        return _fail("remote_visibility_side_effect_at_most_once", "duplicate remote-visibility receipts were recorded")
    return InvariantResult.pass_()


def deletion_handoff_requires_private_remotes(state: DevelopmentState, trace) -> InvariantResult:
    del trace
    if state.user_deletion_handoff_status == "current_pass" and not (
        state.privatized_remote == ("research", "academic")
        and len(state.visibility_receipts) == 2
        and state.terminal
    ):
        return _fail("deletion_handoff_requires_private_remotes", "deletion handoff passed before both private visibility receipts existed")
    if state.terminal and not state.errors and state.user_deletion_handoff_status != "current_pass":
        return _fail("deletion_handoff_requires_private_remotes", "development process terminated without a current deletion handoff")
    return InvariantResult.pass_()


DEVELOPMENT_INVARIANTS = (
    Invariant("release_requires_frozen_validation", "Release consumes current frozen validation", release_requires_frozen_validation),
    Invariant("retirement_requires_recoverable_cutover", "Remote retirement follows recoverable cutover", retirement_requires_recoverable_cutover),
    Invariant("retirement_order_is_sequential", "Research retires first, then health recheck, then academic", retirement_order_is_sequential),
    Invariant("operation_changes_do_not_stale_release", "User artifact changes do not stale release evidence", operation_changes_do_not_stale_release),
    Invariant("remote_visibility_side_effect_at_most_once", "Each legacy remote visibility change occurs at most once", remote_visibility_side_effect_at_most_once),
    Invariant("deletion_handoff_requires_private_remotes", "User deletion handoff follows two verified privatizations", deletion_handoff_requires_private_remotes),
)


FUNCTION_BLOCK_OWNERS = {
    "RejectUnknownOperationEvent": ("Logic Writing operation boundary", "unknown input rejection"),
    "SelectRoute": ("Logic Writing router", "route decision"),
    "InvokeTypedGuardAdapter": ("Logic Writing adapter layer", "typed native receipt import"),
    "AssembleResearchPacket": ("investigation route", "ResearchPacket assembly"),
    "HandoffResearchPacket": ("receiving final route", "exact packet identity acceptance"),
    "BuildReaderBrief": ("final route", "sanitized ReaderBrief"),
    "WriteArtifact": ("final route", "reader artifact write"),
    "RecordRevisionProvenance": ("academic-writing route", "actual source-unit to target-unit provenance"),
    "AuditActualArtifact": ("final route", "current-artifact audit"),
    "UpdateArtifact": ("final route", "artifact revision and audit invalidation"),
    "PropagateOperationStaleness": ("FlowGuard operation plane", "operation evidence staleness"),
    "CloseOperation": ("final route", "final user-artifact closure"),
    "PropagateDevelopmentStaleness": ("FlowGuard development plane", "release evidence staleness"),
    "RejectUnknownDevelopmentEvent": ("Logic Writing development boundary", "unknown input rejection"),
    "FreezeValidation": ("single validation owner", "frozen release validation"),
    "StageInstall": ("SkillGuard", "isolated installation stage"),
    "ActivateInstall": ("SkillGuard", "atomic active installation"),
    "ProjectGlobalRoute": ("SkillGuard global router", "one active route projection"),
    "PublishRelease": ("release workflow", "GitHub commit/tag/release"),
    "VerifyBackups": ("retirement workflow", "predecessor recovery evidence"),
    "QuarantineLegacyLocal": ("retirement workflow", "old local installation removal"),
    "RecheckAfterFirstPrivatization": ("retirement workflow", "new route health after first privatization"),
    "PrivatizeLegacyRemote": ("retirement workflow", "GitHub repository visibility change to private"),
    "RecordRemoteDeletionHandoff": ("retirement workflow", "explicit user ownership of any later repository deletion"),
}
