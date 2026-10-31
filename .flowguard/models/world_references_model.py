"""World references: planned units name real world-contract ids, and unquoted ones stay visible risks.

Each case is one input to the real world-reference checks: a plan unit naming a
declared or an undeclared id, a plan with references but no contract, a review
that quotes or omits a reference, and a fiction ledger world claim that points
at a planned unit or at a unit outside the plan.
"""
from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from flowguard import (FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace,
                       select_covering_traces)
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer

MODEL_ID = "world_references"
PARENT = "world-references"
COMPONENTS = ["world-references"]
IMPLEMENTED_BY = {
    "ResolveRefs": "skills/logic-writing/scripts/world_refs.py:validate_world_refs",
    "QuoteRisks": "skills/logic-writing/scripts/world_refs.py:world_ref_unquoted",
    "ClaimUnits": "skills/logic-writing/scripts/world_refs.py:validate_world_claim_units",
}
TESTED_BY = {
    "world_refs_name_contract_ids": [
        "tests/unit/test_world_refs.py:test_world_refs_validate_literal_ids_and_composition_relative_paths",
        "tests/unit/test_world_mesh.py:test_world_refs_resolve_in_mesh_nodes",
        "tests/unit/test_world_mesh.py:test_world_contract_and_mesh_are_exclusive"],
    "unquoted_world_ref_is_a_risk_not_a_pass": [
        "tests/unit/test_world_refs.py:test_unquoted_world_reference_is_risk_and_only_actual_bound_text_counts"],
    "world_claim_row_is_a_planned_unit": [
        "tests/unit/test_world_refs.py:test_world_claim_source_row_is_a_plan_unit_with_world_references"],
}

ROOT = Path(__file__).resolve().parents[2]
# case -> the intended result of the real check
CASES = {
    "declared_ref": "accepted",
    "undeclared_ref": "unknown_world_ref",
    "no_contract": "world_contract_missing",
    "quoted_ref": "no_risk",
    "unquoted_ref": "world_ref_unquoted",
    "claim_on_planned_unit": "accepted",
    "claim_outside_plan": "unit_not_in_plan",
    "mesh_file_ref": "accepted",
    "mesh_embedded_ref": "accepted",
    "mesh_unknown_ref": "unknown_world_ref",
    "mesh_exclusive": "rejected",
}


@dataclass(frozen=True)
class Event:
    case: str


@dataclass(frozen=True)
class State:
    case: str = ""
    result: str = ""


class Check:
    """Intended behavior: every case gets the result in CASES."""

    name = "Check"
    reads = ("case",)
    writes = ("case", "result")

    def result_for(self, case: str) -> str:
        return CASES[case]

    def apply(self, event: Event, state: State):
        result = self.result_for(event.case)
        return (FunctionResult(result, replace(state, case=event.case, result=result), label=f"{event.case}:{result}"),)


class AcceptsUnknownRef(Check):
    """Known-bad: an id the contract never declares is accepted."""

    def result_for(self, case):
        return "accepted" if case in {"undeclared_ref", "no_contract"} else super().result_for(case)


class DropsUnquotedRef(Check):
    """Known-bad: a reference without a quotation passes silently."""

    def result_for(self, case):
        return "no_risk" if case == "unquoted_ref" else super().result_for(case)


class AcceptsClaimOutsidePlan(Check):
    """Known-bad: a ledger world claim may point at a unit the plan does not have."""

    def result_for(self, case):
        return "accepted" if case == "claim_outside_plan" else super().result_for(case)


def world_refs_name_contract_ids(state: State, trace) -> InvariantResult:
    if state.case.startswith('mesh_') and state.result != CASES[state.case]:
        return InvariantResult.fail('mesh references must resolve file and embedded ids and reject unknown or ambiguous inputs')
    if state.case in {"undeclared_ref", "no_contract"} and state.result == "accepted":
        return InvariantResult.fail("a world reference was accepted without a declared contract id")
    return InvariantResult.pass_()


def unquoted_world_ref_is_a_risk_not_a_pass(state: State, trace) -> InvariantResult:
    if state.case == "unquoted_ref" and state.result != "world_ref_unquoted":
        return InvariantResult.fail("an unquoted world reference is not reported as a risk")
    return InvariantResult.pass_()


def world_claim_row_is_a_planned_unit(state: State, trace) -> InvariantResult:
    if state.case == "claim_outside_plan" and state.result != "unit_not_in_plan":
        return InvariantResult.fail("a world claim outside the plan was accepted")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant("world_refs_name_contract_ids", "world_refs name ids declared by the world contract",
              world_refs_name_contract_ids),
    Invariant("unquoted_world_ref_is_a_risk_not_a_pass", "an unquoted world reference is a residual risk",
              unquoted_world_ref_is_a_risk_not_a_pass),
    Invariant("world_claim_row_is_a_planned_unit", "a ledger world claim points at a planned unit with world_refs",
              world_claim_row_is_a_planned_unit),
)
EVENTS = tuple(Event(case) for case in CASES)


def _explorer(step: Check) -> Explorer:
    return Explorer(workflow=Workflow((step,)), initial_states=(State(),), external_inputs=EVENTS,
                    invariants=INVARIANTS, max_sequence_length=1, progress_steps=0)


def build_explorer() -> Explorer:
    return _explorer(Check())


def broken_variants() -> dict:
    return {"unknown_world_ref_accepted": _explorer(AcceptsUnknownRef()),
            "unquoted_world_ref_dropped": _explorer(DropsUnquotedRef()),
            "world_claim_outside_plan_accepted": _explorer(AcceptsClaimOutsidePlan())}


class _RealWorldRefs:
    """Runs the real world_refs functions on one small contract, plan, review and ledger."""

    def reset(self, state: State) -> None:
        scripts = ROOT / "skills" / "logic-writing" / "scripts"
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        import world_refs
        from _common import ValidationError
        self.refs, self.error = world_refs, ValidationError
        self.folder = Path(tempfile.mkdtemp(prefix="lw-world-refs-model-"))
        (self.folder / "world.yaml").write_text(
            "claim: {claim_id: c_access}\ninputs:\n  events:\n    - {event_id: e_unlock, at: t1}\n", encoding="utf-8")
        self.state = state

    def _run(self, case: str) -> str:
        plan = {"planned_units": [{"planned_unit_id": "scene", "world_refs": ["e_unlock"]},
                                  {"planned_unit_id": "ordinary"}]}
        try:
            if case.startswith('mesh_'):
                import shutil
                folder = self.folder / 'tree'
                shutil.copytree(ROOT / 'tests/fixtures/consumers/worldguard_tree', folder)
                reference = ('door_opened_after_handover' if case == 'mesh_embedded_ref'
                             else 'never_declared' if case == 'mesh_unknown_ref' else 'e_unlock')
                plan['planned_units'][0]['world_refs'] = [reference]
                composition = {'world_mesh': 'tree/mesh_fixed.yaml'}
                if case == 'mesh_exclusive':
                    composition['world_contract'] = 'world.yaml'
                    plan['planned_units'][0]['world_refs'] = ['e_unlock']
                self.refs.validate_world_refs(plan, composition, self.folder)
                return 'accepted'
            if case in {"declared_ref", "undeclared_ref", "no_contract"}:
                if case == "undeclared_ref":
                    plan["planned_units"][0]["world_refs"] = ["never_declared"]
                composition = {} if case == "no_contract" else {"world_contract": "world.yaml"}
                self.refs.validate_world_refs(plan, composition, self.folder)
                return "accepted"
            if case in {"quoted_ref", "unquoted_ref"}:
                shared = {"unit_bindings": [{"planned_unit_id": "scene", "artifact_unit_ids": ["paragraph"]}]}
                evidence = [{"artifact_unit_id": "paragraph", "excerpt": "The key turned."}] if case == "quoted_ref" else []
                review = {"world_ref_checks": [{"planned_unit_id": "scene", "world_ref": "e_unlock", "evidence": evidence}]}
                risks = self.refs.world_ref_unquoted(plan, review, shared, lambda span: None)
                return risks[0].split(":", 1)[0] if risks else "no_risk"
            source = "scene" if case == "claim_on_planned_unit" else "ordinary"
            problems = self.refs.validate_world_claim_units(
                {"worldguard_claims": [{"id": "claim", "source_row_id": source}]}, plan)
            return problems[0].split(":", 1)[0] if problems else "accepted"
        except self.error as exc:
            if case == 'mesh_exclusive':
                return 'rejected'
            return str(exc).split(":", 1)[0]

    def apply_step(self, step) -> ReplayObservation:
        case = step.function_input.case
        result = self._run(case)
        self.state = replace(self.state, case=case, result=result)
        return ReplayObservation(function_name=step.function_name, observed_output=result, observed_state=self.state)

    def observe_state(self) -> State:
        return self.state

    def observe_output(self):
        return None

    def close(self) -> None:
        import shutil
        shutil.rmtree(getattr(self, "folder", ""), ignore_errors=True)


def conformance():
    """Replay one trace per case against the real world-reference checks."""
    last = None
    for trace in select_covering_traces(build_explorer().explore().traces):
        adapter = _RealWorldRefs()
        try:
            last = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                rules=(projected_state_matches(), projected_output_matches()))
        finally:
            adapter.close()
        if not last.ok:
            return last
    return last
