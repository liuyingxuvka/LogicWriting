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
ROOT = Path(__file__).resolve().parents[2]
CASES = {'declared_ref': 'accepted', 'undeclared_ref': 'unknown_world_ref', 'no_contract': 'world_contract_missing', 'quoted_ref': 'no_risk', 'unquoted_ref': 'world_ref_unquoted', 'claim_on_planned_unit': 'accepted', 'claim_outside_plan': 'unit_not_in_plan', 'mesh_file_ref': 'accepted', 'mesh_embedded_ref': 'accepted', 'mesh_unknown_ref': 'unknown_world_ref', 'mesh_exclusive': 'rejected'}

@dataclass(frozen=True)
class Event:
    case: str

@dataclass(frozen=True)
class State:
    case: str = ''
    result: str = ''

class Check:
    """Intended behavior: every case gets the result in CASES."""

    def result_for(self, case: str) -> str:
        return CASES[case]

    def expected(self, event: Event, state: State):
        result = self.result_for(event.case)
        return (result, replace(state, case=event.case, result=result))

class AcceptsUnknownRef(Check):
    """Known-bad: an id the contract never declares is accepted."""

    def result_for(self, case):
        return 'accepted' if case in {'undeclared_ref', 'no_contract'} else super().result_for(case)

class DropsUnquotedRef(Check):
    """Known-bad: a reference without a quotation passes silently."""

    def result_for(self, case):
        return 'no_risk' if case == 'unquoted_ref' else super().result_for(case)

class AcceptsClaimOutsidePlan(Check):
    """Known-bad: a ledger world claim may point at a unit the plan does not have."""

    def result_for(self, case):
        return 'accepted' if case == 'claim_outside_plan' else super().result_for(case)

def world_refs_name_contract_ids(state: State):
    if state.case.startswith('mesh_') and state.result != CASES[state.case]:
        return False
    if state.case in {'undeclared_ref', 'no_contract'} and state.result == 'accepted':
        return False
    return True

def unquoted_world_ref_is_a_risk_not_a_pass(state: State):
    if state.case == 'unquoted_ref' and state.result != 'world_ref_unquoted':
        return False
    return True

def world_claim_row_is_a_planned_unit(state: State):
    if state.case == 'claim_outside_plan' and state.result != 'unit_not_in_plan':
        return False
    return True
EVENTS = tuple((Event(case) for case in CASES))

class _RealWorldRefs:
    """Runs the real world_refs functions on one small contract, plan, review and ledger."""

    def reset(self, state: State) -> None:
        scripts = ROOT / 'skills' / 'logic-writing' / 'scripts'
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        import world_refs
        from _common import ValidationError
        self.refs, self.error = (world_refs, ValidationError)
        self.folder = Path(tempfile.mkdtemp(prefix='lw-world-refs-contract-'))
        (self.folder / 'world.yaml').write_text('claim: {claim_id: c_access}\ninputs:\n  events:\n    - {event_id: e_unlock, at: t1}\n', encoding='utf-8')
        self.state = state

    def _run(self, case: str) -> str:
        plan = {'planned_units': [{'planned_unit_id': 'scene', 'world_refs': ['e_unlock']}, {'planned_unit_id': 'ordinary'}]}
        try:
            if case.startswith('mesh_'):
                import shutil
                folder = self.folder / 'tree'
                shutil.copytree(ROOT / 'tests/fixtures/consumers/worldguard_tree', folder)
                reference = 'door_opened_after_handover' if case == 'mesh_embedded_ref' else 'never_declared' if case == 'mesh_unknown_ref' else 'e_unlock'
                plan['planned_units'][0]['world_refs'] = [reference]
                composition = {'world_mesh': 'tree/mesh_fixed.yaml'}
                if case == 'mesh_exclusive':
                    composition['world_contract'] = 'world.yaml'
                    plan['planned_units'][0]['world_refs'] = ['e_unlock']
                self.refs.validate_world_refs(plan, composition, self.folder)
                return 'accepted'
            if case in {'declared_ref', 'undeclared_ref', 'no_contract'}:
                if case == 'undeclared_ref':
                    plan['planned_units'][0]['world_refs'] = ['never_declared']
                composition = {} if case == 'no_contract' else {'world_contract': 'world.yaml'}
                self.refs.validate_world_refs(plan, composition, self.folder)
                return 'accepted'
            if case in {'quoted_ref', 'unquoted_ref'}:
                shared = {'unit_bindings': [{'planned_unit_id': 'scene', 'artifact_unit_ids': ['paragraph']}]}
                evidence = [{'artifact_unit_id': 'paragraph', 'excerpt': 'The key turned.'}] if case == 'quoted_ref' else []
                review = {'world_ref_checks': [{'planned_unit_id': 'scene', 'world_ref': 'e_unlock', 'evidence': evidence}]}
                risks = self.refs.world_ref_unquoted(plan, review, shared, lambda span: None)
                return risks[0].split(':', 1)[0] if risks else 'no_risk'
            source = 'scene' if case == 'claim_on_planned_unit' else 'ordinary'
            problems = self.refs.validate_world_claim_units({'worldguard_claims': [{'id': 'claim', 'source_row_id': source}]}, plan)
            return problems[0].split(':', 1)[0] if problems else 'accepted'
        except self.error as exc:
            if case == 'mesh_exclusive':
                return 'rejected'
            return str(exc).split(':', 1)[0]

    def observe(self, event):
        case = event.case
        result = self._run(case)
        self.state = replace(self.state, case=case, result=result)
        return (result, self.state)

    def close(self) -> None:
        import shutil
        shutil.rmtree(getattr(self, 'folder', ''), ignore_errors=True)
RULES = {'world_refs_name_contract_ids': world_refs_name_contract_ids, 'unquoted_world_ref_is_a_risk_not_a_pass': unquoted_world_ref_is_a_risk_not_a_pass, 'world_claim_row_is_a_planned_unit': world_claim_row_is_a_planned_unit}
INITIAL_CASES = (State(),)
INPUT_CASES = EVENTS
CALCULATE = Check().expected
BAD_EXPECTATIONS = {'unknown_world_ref_accepted': AcceptsUnknownRef().expected, 'unquoted_world_ref_dropped': DropsUnquotedRef().expected, 'world_claim_outside_plan_accepted': AcceptsClaimOutsidePlan().expected}
