"""Finite plans for the native Logic Writing state models.

Code/test conformance belongs to ordinary pytest. Optional FlowGuard capability
reviews are invoked separately; constructing a plan does not start a proof mesh.
"""
from __future__ import annotations
from typing import Iterable, Sequence
from flowguard import FlowGuardCheckPlan, Scenario, ScenarioExpectation


def scenario(name, description, initial_state, sequence, workflow, invariants):
    return Scenario(name=name, description=description, initial_state=initial_state,
        external_input_sequence=tuple(sequence),
        expected=ScenarioExpectation(expected_status="ok", summary="Declared state boundary is preserved"),
        workflow=workflow, invariants=tuple(invariants), tags=("logic-writing",))


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
    """Construct a native finite model; retain its human-readable boundary."""
    return FlowGuardCheckPlan(
        workflow=workflow, initial_states=tuple(initial_states), external_inputs=tuple(dict.fromkeys(external_inputs)),
        invariants=tuple(invariants), scenarios=tuple(scenarios), max_sequence_length=max_sequence_length,
        metadata={"model_id": model_id, "protected_error_classes": tuple(protected_error_classes),
                  "modeled_state": tuple(modeled_state), "modeled_side_effects": tuple(modeled_side_effects),
                  "completion_evidence": tuple(completion_evidence), "known_bad_cases": tuple(known_bad_cases),
                  "failure_modes": tuple(failure_modes), "harms": tuple(harms),
                  "hard_invariants": tuple(hard_invariants), "adversarial_inputs": tuple(adversarial_inputs)},
    )
