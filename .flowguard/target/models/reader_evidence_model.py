"""Finite evidence gates for researched units, separate from review sequencing.

The restatement check is a bounded lexical signal with explicit response ids,
not a semantic truth judgment. Every case replays real brief/closure code.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow, replay_trace
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer
from _reader_chain_fixture import _RealReaderChain, NativeReport

MODEL_ID = 'reader_evidence_model'
PARENT = 'reader-artifact'
COMPONENTS = ['reader-plan', 'reader-closure', 'reader-commands']
IMPLEMENTED_BY = {
    'BuildBriefRequest': 'skills/logic-writing/scripts/build_reader_brief.py:validate_request',
}
USES = {
    'BuildReaderBrief': 'skills/logic-writing/scripts/reader_plan.py:build_reader_brief',
    'DeriveClosure': 'skills/logic-writing/scripts/derive_closure.py:derive_closure',
    'RunChain': 'skills/logic-writing/scripts/run_chain.py:run_chain',
    'CurrentReaderAudit': 'skills/logic-writing/scripts/reader_checks.py:build_reader_audit_from_current',
    'FillCheckFingerprints': 'skills/logic-writing/scripts/reader_fill.py:fill_check_fingerprints',
    'FillClosureFingerprints': 'skills/logic-writing/scripts/reader_fill.py:fill_closure_fingerprints',
}
TESTED_BY = {
    'closure_requires_support': [
        'tests/unit/test_evidence_rules.py:test_unit_without_anchor_is_unsupported',
        'tests/unit/test_evidence_rules.py:test_unsupported_reason_is_a_residual_risk',
        'tests/unit/test_evidence_rules.py:test_shipped_examples_meet_the_evidence_rules',
        'tests/unit/test_evidence_rules.py:test_evidence_scope_boundaries',
    ],
    'closure_refuses_unsupported_restatement': [
        'tests/unit/test_evidence_rules.py:test_unit_restating_an_unsupported_alternative_fails',
        'tests/unit/test_evidence_rules.py:test_answered_unsupported_alternative_is_allowed',
    ],
}
EXPECTED = {
    'context': 'passed',
    'missing': 'content_unit_unsupported',
    'counter_only': 'content_unit_unsupported',
    'restatement': 'content_unit_restates_unsupported',
    'reason': 'passed+risk',
    'optional': 'passed',
    'nonresearch': 'passed',
    'research_folder': 'content_unit_unsupported',
    'academic_missing': 'content_unit_unsupported',
    'qualified_answer': 'passed',
    'quoted_answer': 'passed',
    'rebutted_answer': 'passed',
    'missing_closure': 'content_unit_unsupported',
    'restatement_closure': 'content_unit_restates_unsupported',
}
RESTATEMENT_CASES = frozenset(('restatement', 'restatement_closure', 'qualified_answer',
                              'quoted_answer', 'rebutted_answer'))


@dataclass(frozen=True)
class Event:
    kind: str
    quality: str


@dataclass(frozen=True)
class State:
    evidence_case: str = ''
    evidence_result: str = ''


class Step:
    name = 'Evidence'
    reads = ()
    writes = ('evidence_case', 'evidence_result')

    def result(self, case):
        return EXPECTED[case]

    def apply(self, event, state):
        result = self.result(event.quality)
        return (FunctionResult(result, replace(state, evidence_case=event.quality,
                                               evidence_result=result),
                               label='evidence_' + event.quality),)


def closure_requires_support(state, trace):
    if (state.evidence_case and state.evidence_case not in RESTATEMENT_CASES
            and state.evidence_result != EXPECTED[state.evidence_case]):
        return InvariantResult.fail('required researched units need non-counter evidence or an explicit reason retained as risk; scope exceptions stay usable')
    return InvariantResult.pass_()


def closure_refuses_unsupported_restatement(state, trace):
    if (state.evidence_case in RESTATEMENT_CASES
            and state.evidence_result != EXPECTED[state.evidence_case]):
        return InvariantResult.fail('an unsupported restatement is refused; a declared qualified, quoted or rebutted answer stays usable')
    return InvariantResult.pass_()


class UnitWithoutAnchorCloses(Step):
    def result(self, case):
        return 'passed' if case in ('missing', 'counter_only', 'missing_closure') else super().result(case)


class UnsupportedRestatementCloses(Step):
    def result(self, case):
        return 'passed' if case in ('restatement', 'restatement_closure') else super().result(case)


INVARIANTS = (
    Invariant('closure_requires_support',
              'a required unit closes only with an evidence anchor that is not only counter, or a stated unsupported_reason',
              closure_requires_support),
    Invariant('closure_refuses_unsupported_restatement',
              'a required unit that restates an unsupported alternative does not close unless it answers it',
              closure_refuses_unsupported_restatement),
)
EVENTS = tuple(Event('evidence', case) for case in EXPECTED)


def _explorer(step):
    return Explorer(workflow=Workflow((step,)), initial_states=(State(),),
                    external_inputs=EVENTS, invariants=INVARIANTS,
                    max_sequence_length=1, progress_steps=0)


def build_explorer():
    return _explorer(Step())


def broken_variants():
    return {'unit_without_anchor_closes': _explorer(UnitWithoutAnchorCloses()),
            'unsupported_restatement_closes': _explorer(UnsupportedRestatementCloses())}


def conformance():
    mismatches = []
    traces = build_explorer().explore().traces
    for trace in traces:
        adapter = _RealReaderChain()
        try:
            report = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                  rules=(projected_state_matches(), projected_output_matches()))
        finally:
            adapter.close()
        if not report.ok:
            mismatches.append(trace.steps[0].function_input.quality + ': ' + report.format_text())
    return NativeReport(len(traces), mismatches)
