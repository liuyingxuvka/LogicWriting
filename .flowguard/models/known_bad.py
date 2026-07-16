"""Executable broken models that prove the three protected failure classes."""

from __future__ import annotations

from dataclasses import replace

from flowguard import FunctionResult, Workflow
from flowguard.explorer import Explorer

from .common import (
    DEVELOPMENT_INVARIANTS,
    OPERATION_INVARIANTS,
    DevelopmentEvent,
    DevelopmentState,
    OperationEvent,
    OperationState,
)
from .operation_freshness_closure_model import PASSED


class BrokenMetadataAudit:
    name = "BrokenMetadataAudit"
    reads = ("artifact_fingerprint",)
    writes = ("deterministic_audit_status", "judgment_status")
    input_description = "metadata-only audit request and operation state"
    output_description = "incorrectly passing audit state without actual artifact binding"
    idempotency = "deterministic broken behavior"
    accepted_input_type = OperationEvent

    def apply(self, event, state):
        return (
            FunctionResult(
                event,
                replace(state, deterministic_audit_status="passed", judgment_status="passed"),
                label="metadata_fake_green",
            ),
        )


class BrokenArtifactUpdate:
    name = "BrokenArtifactUpdate"
    reads = ("artifact_fingerprint", "closure_status")
    writes = ("artifact_fingerprint",)
    input_description = "material artifact edit and previously closed state"
    output_description = "incorrectly edited artifact with old audit and closure preserved"
    idempotency = "deterministic broken behavior"
    accepted_input_type = OperationEvent

    def apply(self, event, state):
        return (
            FunctionResult(
                event,
                replace(state, artifact_fingerprint=event.artifact_fingerprint),
                label="stale_audit_preserved",
            ),
        )


class BrokenRemotePrivatization:
    name = "BrokenRemotePrivatization"
    reads = ("release_status", "install_status", "backups_verified")
    writes = ("privatized_remote",)
    input_description = "legacy repository privatization request and unvalidated development state"
    output_description = "incorrectly privatized remote before cutover gates"
    idempotency = "deterministic broken behavior"
    accepted_input_type = DevelopmentEvent

    def apply(self, event, state):
        return (
            FunctionResult(
                event,
                replace(state, privatized_remote=(event.target,)),
                label="privatized_before_cutover",
            ),
        )


class BrokenProcessOnlyPacket:
    name = "BrokenProcessOnlyPacket"
    reads = ("adapter_receipts", "route_status")
    writes = ("packet_fingerprint", "packet_status", "packet_current")
    input_description = "process-only receipt and packet assembly request"
    output_description = "incorrectly passing packet without source or argument evidence"
    idempotency = "deterministic broken behavior"
    accepted_input_type = OperationEvent

    def apply(self, event, state):
        return (
            FunctionResult(
                event,
                replace(
                    state,
                    packet_fingerprint=event.fingerprint,
                    packet_status="current_pass",
                    packet_current=True,
                ),
                label="process_green_content_not_run",
            ),
        )


def run_known_bad_proofs():
    cases = {
        "metadata_fake_green": Explorer(
            workflow=Workflow((BrokenMetadataAudit(),), name="known_bad_metadata_fake_green"),
            initial_states=(OperationState(),),
            external_inputs=(OperationEvent("audit_metadata"),),
            invariants=OPERATION_INVARIANTS,
            max_sequence_length=1,
            progress_steps=0,
        ).explore(),
        "stale_audit_after_artifact_edit": Explorer(
            workflow=Workflow((BrokenArtifactUpdate(),), name="known_bad_stale_audit"),
            initial_states=(PASSED,),
            external_inputs=(OperationEvent("update_artifact", artifact_fingerprint="artifact:2"),),
            invariants=OPERATION_INVARIANTS,
            max_sequence_length=1,
            progress_steps=0,
        ).explore(),
        "privatize_legacy_before_installed_validation": Explorer(
            workflow=Workflow((BrokenRemotePrivatization(),), name="known_bad_early_privatization"),
            initial_states=(DevelopmentState(),),
            external_inputs=(DevelopmentEvent("privatize_legacy_remote", target="travel"),),
            invariants=DEVELOPMENT_INVARIANTS,
            max_sequence_length=1,
            progress_steps=0,
        ).explore(),
        "process_green_content_not_run": Explorer(
            workflow=Workflow((BrokenProcessOnlyPacket(),), name="known_bad_process_only_packet"),
            initial_states=(
                OperationState(
                    request_fingerprint="request:process-only",
                    route_owner="investigation",
                    route_status="current_pass",
                    adapter_receipts=("flowguard:current_pass:process_model:process:green",),
                    adapter_status="current_pass",
                ),
            ),
            external_inputs=(OperationEvent("assemble_packet", fingerprint="packet:process-only"),),
            invariants=OPERATION_INVARIANTS,
            max_sequence_length=1,
            progress_steps=0,
        ).explore(),
    }
    return cases
