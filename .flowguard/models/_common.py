"""Shared executable state machines for Logic Writing.

Every block implements the FlowGuard contract::

    Input x State -> Set(Output x State)

The agent-operation plane models user work.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


FINAL_OWNERS = ("investigation", "academic-writing", "fiction-writing", "travel-guide")
NATIVE_OWNERS = (
    "sourceguard",
    "logicguard",
    "traceguard",
    "worldguard",
    "flowguard",
    "documents",
    "pdf",
)
NATIVE_EVIDENCE_DOMAINS = {
    "sourceguard": ("source_observation", "source_depth", "source_discovery", "source_library"),
    "logicguard": ("argument_model", "structured_artifact", "model_depth", "artifact_synthesis", "citation_semantics"),
    "traceguard": ("temporal_trace", "causal_trace", "competing_storyline", "prediction_boundary"),
    "worldguard": ("world_consistency",),
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
    "freeze_reader_intent",
    "validate_composition",
    "build_reader_brief",
    "draft_artifact",
    "integrate_artifact",
    "map_artifact",
    "bind_shared_writing",
    "record_revision_provenance",
    "deterministic_audit",
    "route_audit",
    "judge_artifact",
    "request_repair",
    "apply_repair",
    "record_repair_result",
    "source_changed",
    "close_operation",
)
ADAPTER_STATUSES = ("current_pass", "not_applicable") + NON_PASSING
REVIEW_STATUSES = ("passed", "repair", "blocked", "failed", "not_run", "stale")
REPAIR_STATUSES = ("progressed", "no_progress", "blocked")


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
    related_fingerprint: str = ""
    defect_lineage: str = ""
    artifact_mode: str = ""
    producer_id: str = ""
    judge_id: str = ""
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
    reader_intent_fingerprint: str = ""
    reader_intent_status: str = "not_run"
    composition_plan_fingerprint: str = ""
    composition_plan_status: str = "not_run"
    route_extension_fingerprint: str = ""
    brief_fingerprint: str = ""
    brief_status: str = "not_run"
    brief_current: bool = False
    artifact_fingerprint: str = ""
    artifact_bound_brief: str = ""
    artifact_status: str = "not_run"
    artifact_current: bool = False
    artifact_mode: str = "create_new"
    integration_status: str = "not_run"
    artifact_map_fingerprint: str = ""
    artifact_map_status: str = "not_run"
    shared_binding_fingerprint: str = ""
    shared_binding_status: str = "not_run"
    shared_binding_artifact_fingerprint: str = ""
    revision_provenance_status: str = "not_run"
    deterministic_audit_status: str = "not_run"
    route_audit_status: str = "not_run"
    judgment_status: str = "not_run"
    audit_artifact_fingerprint: str = ""
    judgment_artifact_fingerprint: str = ""
    producer_id: str = ""
    judge_id: str = ""
    repair_request_fingerprint: str = ""
    repair_request_artifact_fingerprint: str = ""
    repair_attempt_count: int = 0
    defect_lineage: str = ""
    consecutive_no_progress: int = 0
    last_repair_status: str = "not_run"
    closure_status: str = "not_run"
    closure_artifact_fingerprint: str = ""
    closure_owner: str = ""
    no_progress_count: int = 0
    residual_risk: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
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
        if state.consecutive_no_progress >= 1 and event.action != "close_operation":
            return (FunctionResult(replace(event, action="__blocked__"), replace(state, terminal=True),
                                   label="no_progress_lineage_is_terminal"),)
        if event.action == "invoke_adapter":
            invalid_status = event.status not in ADAPTER_STATUSES
        elif event.action in {"deterministic_audit", "route_audit", "judge_artifact"}:
            invalid_status = event.status not in REVIEW_STATUSES
        elif event.action == "record_repair_result":
            invalid_status = event.status not in REPAIR_STATUSES
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


class FreezeReaderIntent(_OperationBlock):
    name = "FreezeReaderIntent"
    reads = ("route_status", "request_fingerprint")
    writes = (
        "reader_intent_fingerprint",
        "reader_intent_status",
        "composition_plan_status",
        "brief_status",
        "brief_current",
        "closure_status",
        "closure_artifact_fingerprint",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "freeze_reader_intent":
            return self._pass(event, state, "reader_intent_not_requested")
        if state.route_status != "current_pass" or not state.request_fingerprint or not event.fingerprint:
            return (
                FunctionResult(
                    event,
                    replace(state, reader_intent_status="blocked", brief_current=False),
                    label="reader_intent_blocked",
                ),
            )
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    reader_intent_fingerprint=event.fingerprint,
                    reader_intent_status="current_pass",
                    composition_plan_status="not_run",
                    brief_status="not_run",
                    brief_current=False,
                    closure_status="stale" if state.closure_status == "passed" else state.closure_status,
                    closure_artifact_fingerprint="",
                    terminal=False,
                ),
                label="reader_intent_current",
            ),
        )


class ValidateCompositionPlan(_OperationBlock):
    name = "ValidateCompositionPlan"
    reads = ("reader_intent_status", "route_owner", "packet_current")
    writes = (
        "composition_plan_fingerprint",
        "composition_plan_status",
        "route_extension_fingerprint",
        "brief_current",
        "closure_status",
        "closure_artifact_fingerprint",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "validate_composition":
            return self._pass(event, state, "composition_not_requested")
        valid = (
            state.reader_intent_status == "current_pass"
            and state.packet_current
            and state.route_owner in FINAL_OWNERS
            and bool(event.fingerprint)
            and bool(event.related_fingerprint)
            and event.owner == state.route_owner
            and event.status in {"", "current_pass"}
        )
        if not valid:
            return (
                FunctionResult(
                    event,
                    replace(state, composition_plan_status="blocked", brief_current=False),
                    label="composition_blocked",
                ),
            )
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    composition_plan_fingerprint=event.fingerprint,
                    composition_plan_status="current_pass",
                    route_extension_fingerprint=event.related_fingerprint,
                    brief_current=False,
                    closure_status="stale" if state.closure_status == "passed" else state.closure_status,
                    closure_artifact_fingerprint="",
                    terminal=False,
                ),
                label="composition_current",
            ),
        )


class BuildReaderBrief(_OperationBlock):
    name = "BuildReaderBrief"
    reads = (
        "packet_current",
        "handoff_status",
        "reader_intent_status",
        "composition_plan_status",
        "route_extension_fingerprint",
    )
    writes = (
        "brief_fingerprint",
        "brief_status",
        "brief_current",
        "artifact_current",
        "closure_status",
        "closure_artifact_fingerprint",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "build_reader_brief":
            return self._pass(event, state, "brief_not_requested")
        if (
            not state.packet_current
            or state.handoff_status not in {"current_pass", "not_run"}
            or state.reader_intent_status != "current_pass"
            or state.composition_plan_status != "current_pass"
            or not state.route_extension_fingerprint
        ):
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
                    closure_status="stale" if state.closure_status == "passed" else state.closure_status,
                    closure_artifact_fingerprint="",
                    terminal=False,
                ),
                label="reader_brief_current",
            ),
        )


class DraftArtifact(_OperationBlock):
    name = "DraftArtifact"
    reads = ("brief_current", "brief_fingerprint", "route_owner", "composition_plan_status")
    writes = (
        "artifact_fingerprint",
        "artifact_bound_brief",
        "artifact_status",
        "artifact_current",
        "artifact_mode",
        "integration_status",
        "artifact_map_status",
        "shared_binding_status",
        "revision_provenance_status",
        "deterministic_audit_status",
        "route_audit_status",
        "judgment_status",
        "audit_artifact_fingerprint",
        "judgment_artifact_fingerprint",
        "closure_status",
        "closure_artifact_fingerprint",
        "side_effects",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "draft_artifact":
            return self._pass(event, state, "draft_not_requested")
        if not state.brief_current or not state.route_owner or state.composition_plan_status != "current_pass":
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
                    artifact_mode=event.artifact_mode or "create_new",
                    integration_status="not_run",
                    artifact_map_status="not_run",
                    shared_binding_status="not_run",
                    revision_provenance_status="not_run",
                    deterministic_audit_status="not_run",
                    route_audit_status="not_run",
                    judgment_status="not_run",
                    audit_artifact_fingerprint="",
                    judgment_artifact_fingerprint="",
                    closure_status="stale" if state.closure_status == "passed" else state.closure_status,
                    closure_artifact_fingerprint="",
                    side_effects=state.side_effects + ("reader_artifact_written",),
                    terminal=False,
                ),
                label="whole_artifact_drafted",
            ),
        )


class IntegrateArtifact(_OperationBlock):
    name = "IntegrateArtifact"
    reads = ("artifact_current", "artifact_fingerprint", "composition_plan_status")
    writes = ("integration_status", "closure_status", "closure_artifact_fingerprint", "terminal")

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "integrate_artifact":
            return self._pass(event, state, "integration_not_requested")
        current = (
            state.artifact_current
            and state.composition_plan_status == "current_pass"
            and (event.artifact_fingerprint or event.fingerprint) == state.artifact_fingerprint
        )
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    integration_status="current_pass" if current else "blocked",
                    closure_status="stale" if state.closure_status == "passed" else state.closure_status,
                    closure_artifact_fingerprint="",
                    terminal=False,
                ),
                label="artifact_integrated" if current else "integration_blocked",
            ),
        )


class MapArtifact(_OperationBlock):
    name = "MapArtifact"
    reads = ("artifact_current", "artifact_fingerprint", "integration_status")
    writes = (
        "artifact_map_fingerprint",
        "artifact_map_status",
        "shared_binding_status",
        "deterministic_audit_status",
        "route_audit_status",
        "judgment_status",
        "closure_status",
        "closure_artifact_fingerprint",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "map_artifact":
            return self._pass(event, state, "artifact_map_not_requested")
        current = (
            state.artifact_current
            and state.integration_status == "current_pass"
            and bool(event.fingerprint)
            and event.artifact_fingerprint == state.artifact_fingerprint
        )
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    artifact_map_fingerprint=event.fingerprint if current else "",
                    artifact_map_status="current_pass" if current else "blocked",
                    shared_binding_status="not_run",
                    deterministic_audit_status="not_run",
                    route_audit_status="not_run",
                    judgment_status="not_run",
                    closure_status="stale" if state.closure_status == "passed" else state.closure_status,
                    closure_artifact_fingerprint="",
                    terminal=False,
                ),
                label="artifact_map_current" if current else "artifact_map_blocked",
            ),
        )


class BindSharedWriting(_OperationBlock):
    name = "BindSharedWriting"
    reads = (
        "artifact_map_status",
        "artifact_fingerprint",
        "composition_plan_status",
        "route_extension_fingerprint",
    )
    writes = (
        "shared_binding_fingerprint",
        "shared_binding_status",
        "shared_binding_artifact_fingerprint",
        "closure_status",
        "closure_artifact_fingerprint",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "bind_shared_writing":
            return self._pass(event, state, "shared_binding_not_requested")
        current = (
            state.artifact_map_status == "current_pass"
            and state.composition_plan_status == "current_pass"
            and event.artifact_fingerprint == state.artifact_fingerprint
            and bool(event.fingerprint)
            and event.related_fingerprint == state.artifact_map_fingerprint
        )
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    shared_binding_fingerprint=event.fingerprint if current else "",
                    shared_binding_status="current_pass" if current else "blocked",
                    shared_binding_artifact_fingerprint=state.artifact_fingerprint if current else "",
                    closure_status="stale" if state.closure_status == "passed" else state.closure_status,
                    closure_artifact_fingerprint="",
                    terminal=False,
                ),
                label="shared_binding_current" if current else "shared_binding_blocked",
            ),
        )


class RecordRevisionProvenance(_OperationBlock):
    name = "RecordRevisionProvenance"
    reads = ("route_owner", "artifact_current", "artifact_fingerprint")
    writes = (
        "revision_provenance_status",
        "closure_status",
        "closure_artifact_fingerprint",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "record_revision_provenance":
            return self._pass(event, state, "revision_provenance_not_requested")
        expected = "not_applicable" if state.artifact_mode == "create_new" else "current_pass"
        current = state.artifact_current and event.status == expected
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    revision_provenance_status=expected if current else (event.status or "blocked"),
                    closure_status="stale" if state.closure_status == "passed" else state.closure_status,
                    closure_artifact_fingerprint="",
                    terminal=False,
                ),
                label="revision_provenance_current" if current else "revision_provenance_blocked",
            ),
        )


class DeterministicAudit(_OperationBlock):
    name = "DeterministicAudit"
    reads = ("artifact_fingerprint", "artifact_map_status", "shared_binding_status")
    writes = (
        "deterministic_audit_status",
        "audit_artifact_fingerprint",
        "closure_status",
        "closure_artifact_fingerprint",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "deterministic_audit":
            return self._pass(event, state, "deterministic_audit_not_requested")
        current = (
            state.artifact_map_status == "current_pass"
            and state.shared_binding_status == "current_pass"
            and event.artifact_fingerprint == state.artifact_fingerprint
        )
        status = event.status if current else "blocked"
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    deterministic_audit_status=status,
                    audit_artifact_fingerprint=state.artifact_fingerprint if current else "",
                    closure_status="stale" if state.closure_status == "passed" else state.closure_status,
                    closure_artifact_fingerprint="",
                    terminal=False,
                ),
                label="deterministic_artifact_audited" if current else "deterministic_audit_blocked",
            ),
        )


class RouteArtifactAudit(_OperationBlock):
    name = "RouteArtifactAudit"
    reads = ("artifact_fingerprint", "artifact_map_status", "route_owner")
    writes = ("route_audit_status", "closure_status", "closure_artifact_fingerprint", "terminal")

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "route_audit":
            return self._pass(event, state, "route_audit_not_requested")
        current = (
            state.artifact_map_status == "current_pass"
            and event.artifact_fingerprint == state.artifact_fingerprint
            and event.owner == state.route_owner
        )
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    route_audit_status=event.status if current else "blocked",
                    closure_status="stale" if state.closure_status == "passed" else state.closure_status,
                    closure_artifact_fingerprint="",
                    terminal=False,
                ),
                label="route_artifact_audited" if current else "route_audit_blocked",
            ),
        )


class JudgeArtifact(_OperationBlock):
    name = "JudgeArtifact"
    reads = (
        "artifact_fingerprint",
        "deterministic_audit_status",
        "route_audit_status",
        "producer_id",
    )
    writes = (
        "judgment_status",
        "judgment_artifact_fingerprint",
        "producer_id",
        "judge_id",
        "defect_lineage",
        "closure_status",
        "closure_artifact_fingerprint",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "judge_artifact":
            return self._pass(event, state, "judgment_not_requested")
        independent = bool(event.producer_id and event.judge_id and event.producer_id != event.judge_id)
        current = (
            state.deterministic_audit_status == "passed"
            and state.route_audit_status == "passed"
            and event.artifact_fingerprint == state.artifact_fingerprint
            and independent
        )
        status = event.status if current else "blocked"
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    judgment_status=status,
                    judgment_artifact_fingerprint=state.artifact_fingerprint if current else "",
                    producer_id=event.producer_id,
                    judge_id=event.judge_id,
                    defect_lineage=event.defect_lineage if status != "passed" else "",
                    closure_status="stale" if state.closure_status == "passed" else state.closure_status,
                    closure_artifact_fingerprint="",
                    terminal=False,
                ),
                label="independent_judgment_recorded" if current else "judgment_blocked",
            ),
        )


class RequestRepair(_OperationBlock):
    name = "RequestRepair"
    reads = ("artifact_fingerprint", "judgment_status", "defect_lineage", "route_owner")
    writes = (
        "repair_request_fingerprint",
        "repair_request_artifact_fingerprint",
        "defect_lineage",
        "closure_status",
        "closure_artifact_fingerprint",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "request_repair":
            return self._pass(event, state, "repair_request_not_requested")
        current = (
            state.judgment_status in {"repair", "blocked", "failed"}
            and bool(event.fingerprint)
            and event.artifact_fingerprint == state.artifact_fingerprint
            and event.owner == state.route_owner
            and bool(event.defect_lineage)
        )
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    repair_request_fingerprint=event.fingerprint if current else "",
                    repair_request_artifact_fingerprint=state.artifact_fingerprint if current else "",
                    defect_lineage=event.defect_lineage if current else state.defect_lineage,
                    closure_status="stale" if state.closure_status == "passed" else state.closure_status,
                    closure_artifact_fingerprint="",
                    terminal=False,
                ),
                label="repair_requested" if current else "repair_request_blocked",
            ),
        )


class ApplyRepair(_OperationBlock):
    name = "ApplyRepair"
    reads = (
        "repair_request_fingerprint",
        "repair_request_artifact_fingerprint",
        "artifact_fingerprint",
    )
    writes = (
        "artifact_fingerprint",
        "artifact_current",
        "integration_status",
        "artifact_map_fingerprint",
        "artifact_map_status",
        "shared_binding_fingerprint",
        "shared_binding_status",
        "shared_binding_artifact_fingerprint",
        "revision_provenance_status",
        "deterministic_audit_status",
        "route_audit_status",
        "judgment_status",
        "audit_artifact_fingerprint",
        "judgment_artifact_fingerprint",
        "closure_status",
        "closure_artifact_fingerprint",
        "errors",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "apply_repair":
            return self._pass(event, state, "repair_not_requested")
        if (
            not state.artifact_current
            or not state.repair_request_fingerprint
            or state.repair_request_artifact_fingerprint != state.artifact_fingerprint
        ):
            return (
                FunctionResult(
                    event,
                    replace(state, errors=state.errors + ("cannot_apply_unbound_repair",)),
                    label="repair_blocked",
                ),
            )
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    artifact_fingerprint=event.artifact_fingerprint or event.fingerprint,
                    integration_status="not_run",
                    artifact_map_fingerprint="",
                    artifact_map_status="stale",
                    shared_binding_fingerprint="",
                    shared_binding_status="stale",
                    shared_binding_artifact_fingerprint="",
                    revision_provenance_status=(
                        "stale" if state.revision_provenance_status != "not_run" else "not_run"
                    ),
                    deterministic_audit_status="stale",
                    route_audit_status="stale",
                    judgment_status="stale",
                    audit_artifact_fingerprint="",
                    judgment_artifact_fingerprint="",
                    closure_status="stale",
                    closure_artifact_fingerprint="",
                    terminal=False,
                ),
                label="repair_applied_evidence_stale",
            ),
        )


class RecordRepairResult(_OperationBlock):
    name = "RecordRepairResult"
    reads = (
        "repair_request_fingerprint",
        "artifact_fingerprint",
        "defect_lineage",
        "consecutive_no_progress",
    )
    writes = (
        "repair_request_fingerprint",
        "repair_request_artifact_fingerprint",
        "repair_attempt_count",
        "last_repair_status",
        "consecutive_no_progress",
        "no_progress_count",
        "terminal",
    )

    def apply(self, event: OperationEvent, state: OperationState) -> Iterable[FunctionResult]:
        if event.action != "record_repair_result":
            return self._pass(event, state, "repair_result_not_requested")
        bound = (
            bool(state.repair_request_fingerprint)
            and event.related_fingerprint == state.repair_request_fingerprint
            and event.defect_lineage == state.defect_lineage
            and event.artifact_fingerprint == state.artifact_fingerprint
        )
        if not bound:
            return (
                FunctionResult(event, replace(state, last_repair_status="blocked"), label="repair_result_blocked"),
            )
        no_progress = state.consecutive_no_progress + 1 if event.status == "no_progress" else 0
        terminal = no_progress >= 1
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    repair_request_fingerprint="",
                    repair_request_artifact_fingerprint="",
                    repair_attempt_count=state.repair_attempt_count + 1,
                    last_repair_status=event.status,
                    consecutive_no_progress=no_progress,
                    no_progress_count=no_progress,
                    terminal=terminal,
                ),
                label="repair_no_progress_terminated" if terminal else "repair_result_recorded",
            ),
        )


class PropagateOperationStaleness(_OperationBlock):
    name = "PropagateOperationStaleness"
    reads = ("packet_current", "brief_current", "artifact_current", "closure_status")
    writes = (
        "packet_status",
        "packet_current",
        "handoff_status",
        "reader_intent_status",
        "composition_plan_status",
        "brief_status",
        "brief_current",
        "artifact_status",
        "artifact_current",
        "integration_status",
        "artifact_map_status",
        "shared_binding_status",
        "revision_provenance_status",
        "deterministic_audit_status",
        "route_audit_status",
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
                    reader_intent_status=(
                        "stale" if state.reader_intent_status != "not_run" else "not_run"
                    ),
                    composition_plan_status=(
                        "stale" if state.composition_plan_status != "not_run" else "not_run"
                    ),
                    brief_status="stale" if state.brief_status != "not_run" else "not_run",
                    brief_current=False,
                    artifact_status="stale" if state.artifact_status != "not_run" else "not_run",
                    artifact_current=False,
                    integration_status="stale" if state.integration_status != "not_run" else "not_run",
                    artifact_map_status="stale" if state.artifact_map_status != "not_run" else "not_run",
                    shared_binding_status="stale" if state.shared_binding_status != "not_run" else "not_run",
                    revision_provenance_status=(
                        "stale" if state.revision_provenance_status != "not_run" else "not_run"
                    ),
                    deterministic_audit_status="stale" if state.deterministic_audit_status != "not_run" else "not_run",
                    route_audit_status="stale" if state.route_audit_status != "not_run" else "not_run",
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
        "reader_intent_status",
        "composition_plan_status",
        "brief_current",
        "artifact_current",
        "integration_status",
        "artifact_map_status",
        "shared_binding_status",
        "shared_binding_artifact_fingerprint",
        "artifact_mode",
        "revision_provenance_status",
        "deterministic_audit_status",
        "route_audit_status",
        "judgment_status",
        "judgment_artifact_fingerprint",
        "consecutive_no_progress",
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
            state.consecutive_no_progress == 0
            and state.route_owner in FINAL_OWNERS
            and state.packet_current
            and state.reader_intent_status == "current_pass"
            and state.composition_plan_status == "current_pass"
            and state.brief_current
            and state.artifact_current
            and state.artifact_bound_brief == state.brief_fingerprint
            and state.integration_status == "current_pass"
            and state.artifact_map_status == "current_pass"
            and state.shared_binding_status == "current_pass"
            and state.shared_binding_artifact_fingerprint == state.artifact_fingerprint
            and state.revision_provenance_status
            == ("not_applicable" if state.artifact_mode == "create_new" else "current_pass")
            and state.deterministic_audit_status == "passed"
            and state.route_audit_status == "passed"
            and state.judgment_status == "passed"
            and state.audit_artifact_fingerprint == state.artifact_fingerprint
            and state.judgment_artifact_fingerprint == state.artifact_fingerprint
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
        terminal = state.consecutive_no_progress >= 1
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    closure_status="no_progress_blocked" if terminal else "blocked",
                    closure_owner=state.route_owner,
                    no_progress_count=state.consecutive_no_progress,
                    residual_risk=tuple(dict.fromkeys(state.residual_risk + ("required_current_evidence_missing",))),
                    terminal=terminal,
                ),
                label="no_progress_terminated" if terminal else "closure_blocked",
            ),
        )


OPERATION_BLOCKS = (
    RejectUnknownOperationEvent(),
    SelectRoute(),
    InvokeTypedGuardAdapter(),
    AssembleResearchPacket(),
    HandoffResearchPacket(),
    FreezeReaderIntent(),
    ValidateCompositionPlan(),
    BuildReaderBrief(),
    DraftArtifact(),
    IntegrateArtifact(),
    MapArtifact(),
    BindSharedWriting(),
    RecordRevisionProvenance(),
    DeterministicAudit(),
    RouteArtifactAudit(),
    JudgeArtifact(),
    RequestRepair(),
    ApplyRepair(),
    RecordRepairResult(),
    PropagateOperationStaleness(),
    CloseOperation(),
)

def operation_workflow(name: str = "logic_writing_agent_operation") -> Workflow:
    return Workflow(OPERATION_BLOCKS, name=name)


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


def current_reader_chain_is_single_identity(state: OperationState, trace) -> InvariantResult:
    del trace
    if state.shared_binding_status == "current_pass" and (
        state.shared_binding_artifact_fingerprint != state.artifact_fingerprint
        or state.artifact_map_status != "current_pass"
        or state.composition_plan_status != "current_pass"
        or state.reader_intent_status != "current_pass"
    ):
        return _fail(
            "current_reader_chain_is_single_identity",
            "shared binding passed without one current ReaderIntent, composition plan, map, and artifact identity",
        )
    if state.judgment_status == "passed" and (
        state.producer_id == state.judge_id
        or state.judgment_artifact_fingerprint != state.artifact_fingerprint
        or state.route_audit_status != "passed"
    ):
        return _fail(
            "current_reader_chain_is_single_identity",
            "reader judgment passed without independent current route-bound evidence",
        )
    return InvariantResult.pass_()


def closure_requires_current_chain(state: OperationState, trace) -> InvariantResult:
    del trace
    if state.closure_status != "passed":
        return InvariantResult.pass_()
    required = (
        state.packet_current,
        state.reader_intent_status == "current_pass",
        state.composition_plan_status == "current_pass",
        state.brief_current,
        state.artifact_current,
        state.integration_status == "current_pass",
        state.artifact_map_status == "current_pass",
        state.shared_binding_status == "current_pass",
        state.shared_binding_artifact_fingerprint == state.artifact_fingerprint,
        state.revision_provenance_status
        == ("not_applicable" if state.artifact_mode == "create_new" else "current_pass"),
        state.deterministic_audit_status == "passed",
        state.route_audit_status == "passed",
        state.judgment_status == "passed",
        state.audit_artifact_fingerprint == state.artifact_fingerprint,
        state.judgment_artifact_fingerprint == state.artifact_fingerprint,
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
    if state.consecutive_no_progress >= 1 and not state.terminal:
        return _fail("operation_terminal_is_visible", "one actual no-progress result did not terminate visibly")
    if state.no_progress_count > state.repair_attempt_count:
        return _fail("operation_terminal_is_visible", "closure derivation manufactured repair progress")
    return InvariantResult.pass_()


OPERATION_INVARIANTS = (
    Invariant("exactly_one_final_owner", "One request has exactly one final owner", exactly_one_final_owner),
    Invariant("specialist_authority_preserved", "Every specialist receipt keeps its native owner", specialist_authority_preserved),
    Invariant("packet_requires_core_content", "A passing packet contains current source and logic evidence", packet_requires_core_content),
    Invariant("actual_artifact_required_for_audit", "Passing reader audit binds actual current text", actual_artifact_required_for_audit),
    Invariant("current_reader_chain_is_single_identity", "The reader chain binds one current identity", current_reader_chain_is_single_identity),
    Invariant("closure_requires_current_chain", "Final closure requires the current evidence chain", closure_requires_current_chain),
    Invariant("bounded_child_never_closes_parent", "Child routes close only bounded obligations", bounded_child_never_closes_parent),
    Invariant("operation_terminal_is_visible", "Repeated no-progress attempts terminate visibly", operation_terminal_is_visible),
)
