"""Native model declaration for writer/judge execution binding."""

from models.common import OPERATION_INVARIANTS, OperationEvent, OperationState, operation_workflow
from models.plans import formal_plan, scenario
from flowguard import KnownBadProof, MinimumModelContract, FlowGuardCheckPlan

from models.owners._mesh_support import MODEL_PATHS, PARENTS, TEST_PATHS

MODEL_ID = "execution_binding"
PARENT_MODEL_ID = PARENTS[MODEL_ID]


def declaration() -> dict[str, object]:
    return {
        "model_id": MODEL_ID,
        "parent_model_id": PARENT_MODEL_ID,
        "model_path": MODEL_PATHS[MODEL_ID],
        "tests": list(TEST_PATHS[MODEL_ID]),
        "obligations": ["A10:execution_record", "A10:input_fingerprint", "A10:synthetic_rejection"],
    }


def build_plan(*, conformance_status="skipped_with_reason", conformance_evidence=()):
    workflow = operation_workflow("logic_writing_agent_operation")
    good = (
        OperationEvent("bind_execution", fingerprint="exec:1", status="current_pass"),
        OperationEvent("record_execution", fingerprint="input:1", status="current_pass"),
        OperationEvent("complete_execution", fingerprint="output:1", status="current_pass"),
    )
    synthetic = (
        OperationEvent("bind_shared_writing", fingerprint="exec:synthetic", status="current_pass"),
        OperationEvent("record_revision_provenance", fingerprint="input:synthetic", status="current_pass"),
    )
    base = formal_plan(
        model_id=MODEL_ID,
        workflow=workflow,
        initial_states=(OperationState(),),
        external_inputs=good + synthetic,
        invariants=OPERATION_INVARIANTS,
        scenarios=(
            scenario("current_execution_record", "Current execution records bind input and output identity", OperationState(), good, workflow, OPERATION_INVARIANTS),
            scenario("synthetic_execution_rejected", "Synthetic execution records cannot produce completion", OperationState(), synthetic, workflow, OPERATION_INVARIANTS),
        ),
        protected_error_classes=("synthetic_execution_admitted", "missing_input_fingerprint"),
        modeled_state=("execution_record", "input_fingerprint", "execution_status"),
        modeled_side_effects=("execution_record_persisted",),
        completion_evidence=("input_fingerprint_recorded", "output_fingerprint_recorded",),
        known_bad_cases=("synthetic_execution_rejected", "missing_input_fingerprint"),
        failure_modes=("synthetic execution is accepted", "execution input identity is missing"),
        harms=("a fabricated judge result is treated as independent evidence",),
        hard_invariants=("execution input is fingerprint-bound", "synthetic execution cannot complete"),
        adversarial_inputs=("synthetic execution", "missing input fingerprint"),
        conformance_status=conformance_status,
        conformance_evidence=conformance_evidence,
    )
    values = dict(base.__dict__)
    values["minimum_model_contract"] = MinimumModelContract(
            protected_error_classes=("synthetic_execution_admitted", "missing_input_fingerprint"),
            modeled_state=("execution_record", "input_fingerprint", "execution_status"),
            modeled_side_effects=("execution_record_persisted",),
            completion_evidence=("input_fingerprint_recorded", "output_fingerprint_recorded"),
            known_bad_cases=("synthetic_execution_rejected", "missing_input_fingerprint"),
    )
    values["known_bad_proofs"] = (
            KnownBadProof(
                case_id="synthetic_execution_rejected",
                protected_error_class="synthetic_execution_admitted",
                method="broken_workflow",
                expected_failure="failed",
                observed_status="failed",
                observed_failure="synthetic execution cannot complete",
                evidence_id="model:known-bad:execution-binding-synthetic",
            ),
            KnownBadProof(
                case_id="missing_input_fingerprint",
                protected_error_class="missing_input_fingerprint",
                method="broken_workflow",
                expected_failure="failed",
                observed_status="failed",
                observed_failure="execution input identity is missing",
                evidence_id="model:known-bad:execution-binding-input",
            ),
    )
    return FlowGuardCheckPlan(**values)
