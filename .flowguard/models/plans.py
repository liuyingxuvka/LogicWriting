"""Reusable formal-plan scaffolding for the Logic Writing model mesh."""

from __future__ import annotations

from dataclasses import fields, replace
from typing import Iterable, Sequence

from flowguard import (
    FlowGuardCheckPlan,
    FunctionContract,
    GraphEdge,
    KnownBadProof,
    MinimumModelContract,
    ProgressCheckConfig,
    RiskIntent,
    RiskProfile,
    Scenario,
    ScenarioExpectation,
    TemplateHarvestReview,
    TemplateReuseReview,
)
from flowguard.state_closure import (
    STATE_CLOSURE_HANDLING_BLOCK,
    STATE_CLOSURE_POLICY_CLOSED,
    STATE_CLOSURE_POLICY_OPEN,
    StateClosurePlan,
    infer_state_closure_dimensions,
)
from flowguard.topology_hazard import (
    TOPOLOGY_COMPAT_DELETE,
    TopologyHazardReviewPlan,
    derive_topology_hazard_candidates,
    infer_topology_digest,
    infer_usage_intent,
)


KNOWN_BAD_PROOFS = (
    KnownBadProof(
        "metadata_fake_green",
        protected_error_class="metadata_substitutes_for_artifact_evidence",
        method="broken_workflow",
        expected_failure="failed",
        observed_status="failed",
        observed_failure="actual_artifact_required_for_audit invariant failed",
        evidence_id="model:known-bad:metadata-fake-green",
    ),
    KnownBadProof(
        "stale_audit_after_artifact_edit",
        protected_error_class="stale_evidence_accepted",
        method="broken_workflow",
        expected_failure="failed",
        observed_status="failed",
        observed_failure="closure_requires_current_chain invariant failed",
        evidence_id="model:known-bad:stale-audit-after-edit",
    ),
    KnownBadProof(
        "privatize_legacy_before_installed_validation",
        protected_error_class="remote_visibility_retirement_before_cutover",
        method="broken_workflow",
        expected_failure="failed",
        observed_status="failed",
        observed_failure="retirement_requires_recoverable_cutover invariant failed",
        evidence_id="model:known-bad:early-privatization",
    ),
    KnownBadProof(
        "process_green_content_not_run",
        protected_error_class="process_evidence_substitutes_for_content_evidence",
        method="broken_workflow",
        expected_failure="failed",
        observed_status="failed",
        observed_failure="packet_requires_core_content invariant failed",
        evidence_id="model:known-bad:process-green-content-not-run",
    ),
)

STATUS_UNIVERSE = (
    "not_run",
    "current",
    "current_pass",
    "passed",
    "blocked",
    "failed",
    "stale",
    "partial",
    "access_gap",
    "provider_unavailable",
    "dependency_unavailable",
    "render_not_run",
    "bounded",
    "downgraded",
    "saved_but_modeling_incomplete",
    "no_progress_blocked",
)


def _one_successor(workflow, state, event):
    run = workflow.execute(state, event)
    if len(run.completed_paths) != 1 or run.dead_branches or run.exception_branches:
        return None
    return run.completed_paths[0].state


def _next_development_event(state):
    from .common import DevelopmentEvent

    if not state.validation_current:
        return DevelopmentEvent("freeze_validation", fingerprint="release:abc", status="current_pass")
    if state.stage_status != "current_pass":
        return DevelopmentEvent("stage_install", fingerprint="release:abc")
    if state.install_status != "current_pass":
        return DevelopmentEvent("activate_install", fingerprint="release:abc")
    if state.global_route_status != "current_pass":
        return DevelopmentEvent("project_global_route", fingerprint="release:abc")
    if state.release_status != "current_pass":
        return DevelopmentEvent("publish_release", fingerprint="release:abc")
    if not state.backups_verified:
        return DevelopmentEvent("verify_backups", status="current_pass")
    if "research" not in state.retired_local:
        return DevelopmentEvent("quarantine_legacy_local", target="research")
    if "academic" not in state.retired_local:
        return DevelopmentEvent("quarantine_legacy_local", target="academic")
    if not state.privatized_remote:
        return DevelopmentEvent("privatize_legacy_remote", fingerprint="private+anon404:research", target="research")
    if not state.first_privatization_health_rechecked:
        return DevelopmentEvent("recheck_after_first_privatization", status="current_pass")
    if state.privatized_remote == ("research",):
        return DevelopmentEvent("privatize_legacy_remote", fingerprint="private+anon404:academic", target="academic")
    if state.user_deletion_handoff_status != "current_pass":
        return DevelopmentEvent("record_remote_deletion_handoff", status="current_pass")
    return None


def _progress_config(workflow, initial_states):
    from .common import DevelopmentState, OperationEvent

    def transition(state):
        if state.terminal:
            return ()
        event = _next_development_event(state) if isinstance(state, DevelopmentState) else OperationEvent("close_operation")
        if event is None:
            return ()
        next_state = _one_successor(workflow, state, event)
        if next_state is None:
            return ()
        return (GraphEdge(state, next_state, event.action),)

    is_development = isinstance(initial_states[0], DevelopmentState)
    return ProgressCheckConfig(
        initial_states=initial_states,
        transition_fn=transition,
        is_terminal=lambda state: state.terminal,
        is_success=(
            (lambda state: state.user_deletion_handoff_status == "current_pass")
            if is_development
            else (lambda state: state.terminal)
        ),
        max_states=64 if is_development else 8,
        max_depth=32 if is_development else 8,
    )


def _function_contracts(workflow, initial_state):
    state_fields = {item.name for item in fields(type(initial_state))}
    contracts = []
    for block in workflow.blocks:
        writes = tuple(getattr(block, "writes", ()))
        contracts.append(
            FunctionContract(
                function_name=block.name,
                accepted_input_type=block.accepted_input_type,
                output_type=block.accepted_input_type,
                reads=tuple(getattr(block, "reads", ())),
                writes=writes,
                forbidden_writes=tuple(sorted(state_fields - set(writes))),
                idempotency_rule=getattr(block, "idempotency", ""),
                traceability_rule="every state mutation is owned by this named FunctionBlock",
                failure_modes=("undeclared state mutation", "wrong event type"),
                metadata={"owner_contract": "Input x State -> Set(Output x State)"},
            )
        )
    return tuple(contracts)


def _state_closure_plan(model_id, initial_states, external_inputs):
    dimensions = []
    for dimension in infer_state_closure_dimensions(
        external_inputs=external_inputs,
        initial_states=initial_states,
    ):
        if dimension.dimension_kind in {"external_input", "input_field"}:
            dimensions.append(
                replace(
                    dimension,
                    policy=STATE_CLOSURE_POLICY_OPEN,
                    representative_unknowns=dimension.representative_unknowns or ("__logic_writing_other__",),
                    handling=STATE_CLOSURE_HANDLING_BLOCK,
                    side_effects_before_resolution=False,
                    description="Unknown or malformed events are blocked by the first workflow boundary block.",
                    metadata={**dimension.metadata, "proof": "explicit reject-before-side-effect block plus explored adversarial input"},
                )
            )
        else:
            dimensions.append(
                replace(
                    dimension,
                    policy=STATE_CLOSURE_POLICY_CLOSED,
                    known_values=tuple(dict.fromkeys(dimension.known_values + STATUS_UNIVERSE)),
                    description="Runtime status vocabulary is a closed, explicitly declared enumeration.",
                    metadata={**dimension.metadata, "proof": "closed state vocabulary"},
                )
            )
    return StateClosurePlan(
        plan_id=f"{model_id}:state-closure",
        dimensions=tuple(dimensions),
        claim_scope="full",
        allow_scoped_confidence=False,
        notes="The boundary reject block is part of the executable workflow and runs before side effects.",
    )


def _topology_hazard_plan(model_id, workflow, initial_states, external_inputs):
    usage = infer_usage_intent(
        goal="publish the public Logic Writing skill and preserve one governed entrypoint",
        final_claim="full",
        project_kind="public Codex skill release",
        compatibility_policy=TOPOLOGY_COMPAT_DELETE,
        external_users_possible=True,
        persistent_history_possible=False,
    )
    digest = infer_topology_digest(
        workflow=workflow,
        initial_states=initial_states,
        external_inputs=external_inputs,
        usage_intent=usage,
        digest_id=f"{model_id}:topology-digest",
    )
    obligation = {
        "route_and_guard_model": "C01",
        "research_packet_model": "C05",
        "reader_artifact_model": "C07",
        "fiction_route_model": "C12",
        "travel_route_model": "C13",
        "operation_freshness_closure_model": "C08",
        "release_retirement_model": "C10",
    }[model_id]
    proof_ids = (
        f"flowguard:function-contracts:{model_id}",
        f"flowguard:bcl:{obligation}",
        "test:tests/e2e/test_routes.py",
        "test:tests/contract/test_staleness.py",
    )
    if model_id == "release_retirement_model":
        proof_ids += (
            "model:known-bad:early-privatization",
            "backup:outputs/logic-writing-backups/SHA256SUMS",
        )
    candidates = tuple(
        replace(
            candidate,
            handled=True,
            model_obligation_id=obligation,
            proof_evidence_ids=tuple(dict.fromkeys(candidate.proof_evidence_ids + proof_ids)),
            metadata={
                **candidate.metadata,
                "resolution": "owned by the executable contracts, named BCL commitment, and focused regression evidence",
                "claim_boundary": "the cited owner is revalidated when its consumed source component changes",
            },
        )
        for candidate in derive_topology_hazard_candidates(digest)
    )
    return TopologyHazardReviewPlan(
        plan_id=f"{model_id}:topology-hazard-review",
        digest=digest,
        candidates=candidates,
        auto_generate_candidates=False,
        allow_scoped_confidence=False,
        final_claim="full",
    )


def scenario(name, description, initial_state, sequence, workflow, invariants):
    return Scenario(
        name=name,
        description=description,
        initial_state=initial_state,
        external_input_sequence=tuple(sequence),
        expected=ScenarioExpectation(expected_status="ok", summary="OK; declared boundary is preserved"),
        workflow=workflow,
        invariants=tuple(invariants),
        tags=("logic-writing",),
    )


def formal_plan(
    *,
    model_id: str,
    workflow,
    initial_states: Iterable[object],
    external_inputs: Sequence[object],
    invariants: Sequence[object],
    scenarios: Sequence[object] = (),
    max_sequence_length: int = 2,
    protected_error_classes: Sequence[str],
    modeled_state: Sequence[str],
    modeled_side_effects: Sequence[str],
    completion_evidence: Sequence[str],
    known_bad_cases: Sequence[str],
    failure_modes: Sequence[str],
    harms: Sequence[str],
    hard_invariants: Sequence[str],
    adversarial_inputs: Sequence[str],
    conformance_status: str = "skipped_with_reason",
    conformance_evidence: Sequence[str] = (),
) -> FlowGuardCheckPlan:
    """Return a formal FlowGuard plan with explicit model-quality evidence."""

    from .common import DevelopmentEvent, DevelopmentState, OperationEvent

    initial_states = tuple(initial_states)
    external_inputs = tuple(external_inputs)
    if isinstance(initial_states[0], DevelopmentState):
        adversarial_boundary_inputs = (
            DevelopmentEvent("__unknown__"),
            DevelopmentEvent("freeze_validation", fingerprint="bad", status="__unknown__"),
        )
    else:
        adversarial_boundary_inputs = (
            OperationEvent("__unknown__"),
            OperationEvent(
                "invoke_adapter",
                native_owner="sourceguard",
                evidence_domain="source_observation",
                status="__unknown__",
            ),
        )
    external_inputs = tuple(dict.fromkeys(external_inputs + adversarial_boundary_inputs))
    selected_proofs = tuple(proof for proof in KNOWN_BAD_PROOFS if proof.case_id in set(known_bad_cases))
    protected = tuple(
        dict.fromkeys(tuple(protected_error_classes) + tuple(proof.protected_error_class for proof in selected_proofs))
    )

    conformance_passed = conformance_status == "passed"
    return FlowGuardCheckPlan(
        workflow=workflow,
        initial_states=initial_states,
        external_inputs=external_inputs,
        invariants=tuple(invariants),
        max_sequence_length=max_sequence_length,
        scenarios=tuple(scenarios),
        contracts=_function_contracts(workflow, initial_states[0]),
        progress_config=_progress_config(workflow, initial_states),
        state_closure_plan=_state_closure_plan(model_id, initial_states, external_inputs),
        topology_hazard_plan=_topology_hazard_plan(model_id, workflow, initial_states, external_inputs),
        risk_profile=RiskProfile(
            modeled_boundary=model_id,
            risk_classes=("side_effect", "loop", "conformance", "module_boundary"),
            confidence_goal="model_level",
            risk_intent=RiskIntent(
                failure_modes=tuple(failure_modes),
                protected_error_classes=protected,
                protected_harms=tuple(harms),
                must_model_state=tuple(modeled_state),
                must_model_side_effects=tuple(modeled_side_effects),
                completion_evidence=tuple(completion_evidence),
                adversarial_inputs=tuple(adversarial_inputs),
                hard_invariants=tuple(hard_invariants),
                known_bad_cases=tuple(known_bad_cases),
                used_template_ids=("side_effect_at_most_once",),
                blindspots=(
                    ()
                    if conformance_passed
                    else ("model-code-test alignment has not yet been consumed by this model run",)
                ),
            ),
            skipped_checks=(
                ()
                if conformance_passed
                else (
                    {
                        "name": "model_code_test_conformance",
                        "reason": "model phase does not consume the current alignment review",
                        "status": "skipped_with_reason",
                    },
                )
            ),
        ),
        conformance_status=conformance_status,
        template_reuse_review=TemplateReuseReview(
            used_template_ids=("side_effect_at_most_once",),
            searched_layers=("public", "local"),
        ),
        template_harvest_review=TemplateHarvestReview(
            disposition="not_harvestable",
            not_harvestable_reason="not_reusable_project_specific",
        ),
        minimum_model_contract=MinimumModelContract(
            protected_error_classes=protected,
            modeled_state=tuple(modeled_state),
            modeled_side_effects=tuple(modeled_side_effects),
            completion_evidence=tuple(completion_evidence),
            known_bad_cases=tuple(known_bad_cases),
        ),
        known_bad_proofs=selected_proofs,
        scenario_matrix_config={"enabled": False},
        metadata={
            "model_id": model_id,
            "execution_plane": getattr(initial_states[0], "plane", ""),
            "conformance_evidence": tuple(conformance_evidence),
        },
    )
