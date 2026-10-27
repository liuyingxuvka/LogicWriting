from __future__ import annotations
from dataclasses import dataclass, replace
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow, replay_trace, select_covering_traces
from flowguard.conformance import projected_state_matches, projected_output_matches
from flowguard.explorer import Explorer
from _reader_chain_fixture import _RealReaderChain, NativeReport
MODEL_ID = 'plan_order_model'
PARENT = 'reader-checks'
IMPLEMENTED_BY = {'ReaderAudit': 'skills/logic-writing/scripts/reader_checks.py:build_reader_audit'}
TESTED_BY = {'text_follows_plan_order': ['tests/unit/test_reader.py:test_audit_finds_text_out_of_plan_order']}
@dataclass(frozen=True)
class Event:
    kind: str                       # review | self_review | edit | close | import | order | readback
    quality: str = ""               # review: pass | repair; import: a key of IMPORT_RELATIONS; order: in_order | swapped; readback: clean | leak

OUTPUTS = {'order_audit': ('passed', 'plan_order_mismatch')}
@dataclass(frozen=True)
class State:
    order_case: str=''
    order_audit: str=''

class Step:
    name='Step'
    reads=()
    writes=('order_case', 'order_audit')
    def order_audit_for(self, case: str) -> str:
        return "plan_order_mismatch" if case == "swapped" else "passed"
    def apply(self,event,state):
        result=self.order_audit_for(event.quality)
        return (FunctionResult('audited',replace(state,order_case=event.quality,order_audit=result),label='order'+'_'+event.quality),)

class SwappedSectionsPass(Step):
    """Known-bad: the audit never compares the text order with the plan order."""

    def order_audit_for(self, case: str) -> str:
        return "passed"

def _text_follows_plan_order(state: State, trace) -> InvariantResult:
    if state.order_case == "swapped" and state.order_audit != "plan_order_mismatch":
        return InvariantResult.fail("sibling sections appear in the text out of plan order and the audit passed")
    return InvariantResult.pass_()

INVARIANTS = (Invariant("text_follows_plan_order", "sibling planned units appear in the text in plan order",
              _text_follows_plan_order),)
CASES = ('in_order', 'swapped')
EVENTS=tuple(Event('order',case) for case in CASES)
def _explorer(step):return Explorer(workflow=Workflow((step,)),initial_states=(State(),),external_inputs=EVENTS,invariants=INVARIANTS,max_sequence_length=1,progress_steps=0)
def build_explorer():return _explorer(Step())
def broken_variants():return {'swapped_sections_pass':_explorer(SwappedSectionsPass())}
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
