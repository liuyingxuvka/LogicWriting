"""Each route wrapper reviews for its native owner and preserves repair results."""
from __future__ import annotations
from dataclasses import dataclass, replace
from pathlib import Path
import copy, importlib.util, io, shutil, sys, tempfile
from contextlib import redirect_stdout
from flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace, select_covering_traces
from flowguard.conformance import projected_state_matches, projected_output_matches
from flowguard.explorer import Explorer
ROOT=Path(__file__).resolve().parents[2]
MODEL_ID='route_review_model'
PARENT='system'
COMPONENTS=['academic','fiction','investigation','travel']
IMPLEMENTED_BY={'ReviewAcademic': 'skills/logic-writing/routes/academic/scripts/validate_academic_artifact.py:validate_academic_artifact', 'ReviewFiction': 'skills/logic-writing/routes/fiction/scripts/validate_fiction_artifact.py:validate_fiction_artifact', 'ReviewInvestigation': 'skills/logic-writing/routes/investigation/scripts/validate_investigation_artifact.py:validate_investigation_artifact', 'ReviewTravel': 'skills/logic-writing/routes/travel/scripts/validate_travel_artifact.py:validate_travel_artifact'}
USES={'Review':'skills/logic-writing/scripts/reader_checks.py:validate_route_artifact_review'}
TESTED_BY={'route_command_reviews_for_its_own_owner':['tests/unit/test_route_review.py:test_route_command_reviews_for_its_own_owner'],'failed_review_is_partial':['tests/unit/test_route_review.py:test_failed_route_review_is_partial']}
ROUTES={'academic-writing': 'academic', 'fiction-writing': 'fiction', 'investigation': 'investigation', 'travel-guide': 'travel'}
@dataclass(frozen=True)
class Event:
    owner:str
    passed:bool=True
    sibling:bool=False
@dataclass(frozen=True)
class State:
    sibling:bool=False
    rejected:bool=False
    passed:bool=True
    status:str=''
class Step:
    name='Review'
    reads=()
    writes=('sibling','rejected','passed','status')
    def rejected(self,event):return event.sibling
    def status(self,event):return 'current_pass' if event.passed else 'partial'
    def apply(self,event,state):
        rejected=self.rejected(event)
        status='rejected' if rejected else self.status(event)
        return (FunctionResult(status,State(event.sibling,rejected,event.passed,status),label='review'),)
class WrongOwner(Step):
    def rejected(self,event):return False
class RepairPasses(Step):
    def status(self,event):return 'current_pass'
def _own(state,trace):
    return InvariantResult.fail('the route accepted a sibling ReaderBrief') if state.sibling and not state.rejected else InvariantResult.pass_()
def _partial(state,trace):
    return InvariantResult.fail('native repair did not remain partial') if not state.rejected and state.status and state.status!=('current_pass' if state.passed else 'partial') else InvariantResult.pass_()
INVARIANTS=(Invariant('route_command_reviews_for_its_own_owner','a sibling route brief is refused',_own),Invariant('failed_review_is_partial','only a passed review is current_pass',_partial))
EVENTS=tuple(Event(owner,passed,sibling) for owner in ROUTES for passed in (True,False) for sibling in (False,True))
class Native:
    def reset(self,state):
        self.state=state;self.folder=Path(tempfile.mkdtemp(prefix='lw-route-review-'))
    def apply_step(self,step):
        from tests.v2_support import complete_chain
        from _common import ValidationError
        import importlib
        event=step.function_input
        chain=complete_chain(self.folder/'chain',event.owner,pass_quality=event.passed)
        route=ROUTES[event.owner]
        path=str(ROOT/f'skills/logic-writing/routes/{route}/scripts')
        if path not in sys.path:sys.path.insert(0,path)
        function=getattr(importlib.import_module(f'validate_{route}_artifact'),f'validate_{route}_artifact')
        brief=copy.deepcopy(chain['reader_brief'])
        if event.sibling:
            sibling=next(owner for owner in ROUTES if owner!=event.owner)
            brief=complete_chain(self.folder/'sibling',sibling)['reader_brief']
        request={'review':chain['route_review'],'route_composition':chain['route_composition'],'artifact_map':chain['artifact_map'],'reader_brief':brief,'shared_writing':chain['shared_writing']}
        try:
            result=function(request);status=result['status'];rejected=False
        except ValidationError as exc:
            if 'sibling' not in str(exc):raise
            status='rejected';rejected=True
        self.state=State(event.sibling,rejected,event.passed,status)
        return ReplayObservation(function_name=step.function_name,observed_output=status,observed_state=self.state)
    def observe_state(self):return self.state
    def observe_output(self):return None
    def close(self):shutil.rmtree(self.folder,ignore_errors=True)

def _explorer(step):
    return Explorer(workflow=Workflow((step,)),initial_states=(State(),),external_inputs=EVENTS,invariants=INVARIANTS,max_sequence_length=1,progress_steps=0)
def build_explorer():return _explorer(Step())
def conformance():
    last=None
    for path in (ROOT,ROOT/'skills/logic-writing/scripts'):
        if str(path) not in sys.path:sys.path.insert(0,str(path))
    for trace in select_covering_traces(build_explorer().explore().traces):
        adapter=Native()
        try:last=replay_trace(trace=trace,adapter=adapter,invariants=INVARIANTS,rules=(projected_state_matches(),projected_output_matches()))
        finally:adapter.close()
        if not last.ok:return last
    return last
def broken_variants():return {'route_command_uses_another_owner':_explorer(WrongOwner()),'failed_review_reported_current':_explorer(RepairPasses())}

NOT_MODELED = {'skills/logic-writing/routes/fiction/scripts/run_native_regression.py:main': 'Fiction regression driver that runs the native fiction validators on their example cases; covered by scripts/run_fiction_regression.py in CI.', 'skills/logic-writing/routes/fiction/scripts/run_route_regression.py:main': 'Fiction regression driver that runs the route cases and compares their expected codes; covered by scripts/run_fiction_regression.py in CI.', 'skills/logic-writing/routes/travel/scripts/validate_failure_cases.py:main': 'Travel regression command that applies each failure case to the base trip and compares its expected issue codes.', 'skills/logic-writing/routes/travel/scripts/validate_positive_cases.py:main': 'Travel regression command that applies each positive case to the base trip and expects no issue.', 'skills/logic-writing/routes/travel/scripts/validate_travel_plan.py:main': 'Command wrapper that prints the issues of travel_contract.review_plan for one plan file.', 'skills/logic-writing/routes/travel/scripts/validate_travel_text_outputs.py:main': 'Travel text regression command for saved guide texts; tests/unit/test_travel.py runs it on a good and a bullet-only guide.', 'skills/logic-writing/routes/fiction/scripts/run_longform_regression.py:main': 'The finite regression driver executes native domain validators; its subprocess/output wrapper is tested by the fiction regression contract, while the domain validators own writing semantics.', 'skills/logic-writing/routes/fiction/scripts/run_story_model_mesh_regression.py:main': 'Finite developer regression orchestration writes only requested report files and is covered by native fiction regression checks, not a separate writing-state machine.'}
