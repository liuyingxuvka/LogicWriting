"""Imported fields stay source-owned; a researched brief's extra anchors need an explicit outside reason."""
from __future__ import annotations
from dataclasses import dataclass, replace
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow, replay_trace, select_covering_traces
from flowguard.conformance import projected_state_matches, projected_output_matches
from flowguard.explorer import Explorer
from _reader_chain_fixture import _RealReaderChain, NativeReport
MODEL_ID = 'anchor_import_model'
PARENT = 'reader-inputs'
IMPLEMENTED_BY = {
    "ImportAnchors": "skills/logic-writing/scripts/reader_fill.py:fill_brief_fingerprints"
}
TESTED_BY = {
    "imported_anchor_matches_the_report_row": [
        "tests/unit/test_researchguard_status.py:test_imported_anchor_matches_the_report_row"
    ],
    "imported_anchor_keeps_research_direction": [
        "tests/unit/test_researchguard_status.py:test_imported_anchor_takes_the_research_direction"
    ],
    "anchors_come_from_research": [
        "tests/unit/test_evidence_rules.py:test_anchor_outside_the_research_report_fails",
        "tests/unit/test_evidence_rules.py:test_outside_research_reason_is_a_residual_risk",
    ],
}
@dataclass(frozen=True)
class Event:
    kind: str                       # review | self_review | edit | close | import | order | readback
    quality: str = ""               # review: pass | repair; import: a key of IMPORT_RELATIONS; order: in_order | swapped; readback: clean | leak

IMPORT_RELATIONS = {'oppose': 'counter', 'limit': 'limit', 'support': 'support', 'none': 'context', 'no_status': 'research_folder needs research_status', 'hand_conflict': 'anchor_relation_conflict'}
USES = {
    'Fill': 'skills/logic-writing/scripts/researchguard_status.py:fill_anchors_from_research',
    'BuildBriefRequest': 'skills/logic-writing/scripts/build_reader_brief.py:validate_request',
    'RunChain': 'skills/logic-writing/scripts/run_chain.py:run_chain',
    'DeriveClosure': 'skills/logic-writing/scripts/derive_closure.py:derive_closure',
}
AUTHORITY_EXPECTED = {'research': 'passed', 'invented': 'anchor_not_in_research',
                      'outside': 'passed+risk', 'no_folder': 'passed',
                      'blank_reason': 'anchor_not_in_research'}
@dataclass(frozen=True)
class State:
    import_case: str=''
    relation: str=''
    report_fields_match: bool=True
    authority_case: str=''
    authority_result: str=''

class Step:
    name='Step'
    reads=()
    writes=('import_case', 'relation', 'report_fields_match', 'authority_case', 'authority_result')
    def relation_for(self, case: str) -> str:
        return IMPORT_RELATIONS[case]
    def fields_match(self,case):return True
    def authority_result(self, case):return AUTHORITY_EXPECTED[case]
    def apply(self,event,state):
        if event.kind == 'anchor_authority':
            result = self.authority_result(event.quality)
            return (FunctionResult(result, replace(state, authority_case=event.quality,
                                                   authority_result=result),
                                   label='anchor_authority_' + event.quality),)
        result=self.relation_for(event.quality)
        return (FunctionResult('imported',replace(state,import_case=event.quality,relation=result,report_fields_match=self.fields_match(event.quality)),label='import'+'_'+event.quality),)

class ImportedCounterMarkedSupport(Step):
    """Known-bad: every imported anchor is written as support, whatever the research says."""

    def relation_for(self, case: str) -> str:
        return "support"

def _imported_anchor_keeps_research_direction(state: State, trace) -> InvariantResult:
    if state.import_case and state.relation != IMPORT_RELATIONS[state.import_case]:
        return InvariantResult.fail("an imported anchor lost its research direction")
    return InvariantResult.pass_()

def imported_anchor_matches_the_report_row(state,trace):
    if state.import_case and not state.report_fields_match:
        return InvariantResult.fail('imported locator, summary or boundary differs from the saved report')
    return InvariantResult.pass_()

class ImportedAnchorIgnoresReportLocator(Step):
    def fields_match(self,case):return case!='support'

def anchors_come_from_research(state, trace):
    if state.authority_case and state.authority_result != AUTHORITY_EXPECTED[state.authority_case]:
        return InvariantResult.fail('a researched anchor must be in the report or carry an outside reason retained as an owner-bound risk; without a folder this gate does not apply')
    return InvariantResult.pass_()

class InventedAnchorImported(Step):
    def authority_result(self, case):
        return 'passed' if case == 'invented' else super().authority_result(case)

INVARIANTS = (Invariant('imported_anchor_matches_the_report_row','import fields come from the report row',imported_anchor_matches_the_report_row),Invariant("imported_anchor_keeps_research_direction", "an imported anchor takes its relation from the research direction",
              _imported_anchor_keeps_research_direction),
              Invariant('anchors_come_from_research',
                        'with a research folder, every brief anchor is a row of the saved report or carries outside_research',
                        anchors_come_from_research))
CASES = ('oppose', 'limit', 'support', 'none', 'no_status', 'hand_conflict')
EVENTS=(tuple(Event('import',case) for case in CASES)
        + tuple(Event('anchor_authority',case) for case in AUTHORITY_EXPECTED))
def _explorer(step):return Explorer(workflow=Workflow((step,)),initial_states=(State(),),external_inputs=EVENTS,invariants=INVARIANTS,max_sequence_length=1,progress_steps=0)
def build_explorer():return _explorer(Step())
def broken_variants():return {'imported_anchor_ignores_the_report_locator':_explorer(ImportedAnchorIgnoresReportLocator()),'imported_counter_anchor_marked_support':_explorer(ImportedCounterMarkedSupport()),'invented_anchor_is_imported':_explorer(InventedAnchorImported())}
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
