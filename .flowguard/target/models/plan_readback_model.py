from __future__ import annotations
from dataclasses import dataclass, replace
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow, replay_trace, select_covering_traces
from flowguard.conformance import projected_state_matches, projected_output_matches
from flowguard.explorer import Explorer
from _reader_chain_fixture import _RealReaderChain, NativeReport
MODEL_ID = 'plan_readback_model'
PARENT = 'reader-commands'
IMPLEMENTED_BY = {'ShowPlan': 'skills/logic-writing/scripts/show_plan.py:main', 'PlanView': 'skills/logic-writing/scripts/show_plan.py:plan_view'}
TESTED_BY = {'readback_shows_failing_units': ['tests/e2e/test_worked_examples.py:test_show_plan_shows_findings_on_the_failing_unit']}
@dataclass(frozen=True)
class Event:
    kind: str                       # review | self_review | edit | close | import | order | readback
    quality: str = ""               # review: pass | repair; import: a key of IMPORT_RELATIONS; order: in_order | swapped; readback: clean | leak

@dataclass(frozen=True)
class State:
    readback_case: str=''
    readback: str=''

class Step:
    name='Step'
    reads=()
    writes=('readback_case', 'readback')
    def readback_for(self, case: str) -> str:
        return "shown" if case == "leak" else "clean"
    def apply(self,event,state):
        result=self.readback_for(event.quality)
        return (FunctionResult('read',replace(state,readback_case=event.quality,readback=result),label='readback'+'_'+event.quality),)

class ReadbackHidesFindings(Step):
    """Known-bad: the plan readback shows the plan and text but not the checks' findings."""

    def readback_for(self, case: str) -> str:
        return "hidden" if case == "leak" else "clean"

def _readback_shows_failing_units(state: State, trace) -> InvariantResult:
    if state.readback_case == "leak" and state.readback != "shown":
        return InvariantResult.fail("a unit failing its audit reads back without the finding")
    return InvariantResult.pass_()

INVARIANTS = (Invariant("readback_shows_failing_units", "each failure on a unit is visible under that unit in the readback",
              _readback_shows_failing_units),)
CASES = ('clean', 'leak')
EVENTS=tuple(Event('readback',case) for case in CASES)
def _explorer(step):return Explorer(workflow=Workflow((step,)),initial_states=(State(),),external_inputs=EVENTS,invariants=INVARIANTS,max_sequence_length=1,progress_steps=0)
def build_explorer():return _explorer(Step())
def broken_variants():return {'readback_hides_findings':_explorer(ReadbackHidesFindings())}
def conformance():
    count=0
    for trace in build_explorer().explore().traces:
        if len(trace.steps)!=1:continue
        adapter=_RealReaderChain()
        try:report=replay_trace(trace=trace,adapter=adapter,invariants=INVARIANTS,rules=(projected_state_matches(),projected_output_matches()))
        finally:adapter.close()
        if not report.ok:return report
        count+=1
    return NativeReport(count,[])
