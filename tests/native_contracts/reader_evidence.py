"""Brief evidence and request-source boundaries, separate from review sequencing.

The restatement check is a bounded lexical signal with explicit response ids,
not a semantic truth judgment. Every case calls real brief/closure code.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from .reader_cases import _RealReaderChain
EXPECTED = {'context': 'passed', 'missing': 'content_unit_unsupported', 'counter_only': 'content_unit_unsupported', 'restatement': 'content_unit_restates_unsupported', 'reason': 'passed+risk', 'optional': 'passed', 'nonresearch': 'passed', 'research_folder': 'content_unit_unsupported', 'academic_missing': 'content_unit_unsupported', 'qualified_answer': 'passed', 'quoted_answer': 'passed', 'rebutted_answer': 'passed', 'missing_closure': 'content_unit_unsupported', 'restatement_closure': 'content_unit_restates_unsupported'}
RESTATEMENT_CASES = frozenset(('restatement', 'restatement_closure', 'qualified_answer', 'quoted_answer', 'rebutted_answer'))
REQUEST_EXPECTED = {'verbatim': 'verbatim', 'missing_request': 'brief_request_missing', 'missing_source': 'content_unit_source_missing', 'paraphrase': 'quote_not_in_request', 'optional': 'verbatim', 'optional_case_changed': 'quote_not_in_request', 'spacing_changed': 'quote_not_in_request'}

@dataclass(frozen=True)
class Event:
    kind: str
    quality: str

@dataclass(frozen=True)
class State:
    evidence_case: str = ''
    evidence_result: str = ''
    request_case: str = ''
    request_result: str = ''

class Step:

    def result(self, case):
        return EXPECTED[case]

    def request_result(self, case):
        return REQUEST_EXPECTED[case]

    def expected(self, event, state):
        if event.kind == 'request':
            result = self.request_result(event.quality)
            return (result, replace(state, request_case=event.quality, request_result=result))
        result = self.result(event.quality)
        return (result, replace(state, evidence_case=event.quality, evidence_result=result))

def closure_requires_support(state):
    if state.evidence_case and state.evidence_case not in RESTATEMENT_CASES and (state.evidence_result != EXPECTED[state.evidence_case]):
        return False
    return True

def closure_refuses_unsupported_restatement(state):
    if state.evidence_case in RESTATEMENT_CASES and state.evidence_result != EXPECTED[state.evidence_case]:
        return False
    return True

class UnitWithoutAnchorCloses(Step):

    def result(self, case):
        return 'passed' if case in ('missing', 'counter_only', 'missing_closure') else super().result(case)

class UnsupportedRestatementCloses(Step):

    def result(self, case):
        return 'passed' if case in ('restatement', 'restatement_closure') else super().result(case)

def request_quote_is_verbatim(state):
    if state.request_case and state.request_result != REQUEST_EXPECTED[state.request_case]:
        return False
    return True

class ParaphrasedRequestQuotePasses(Step):

    def request_result(self, case):
        return 'verbatim' if case == 'paraphrase' else super().request_result(case)
EVENTS = tuple((Event('evidence', case) for case in EXPECTED)) + tuple((Event('request', case) for case in REQUEST_EXPECTED))
RULES = {'closure_requires_support': closure_requires_support, 'closure_refuses_unsupported_restatement': closure_refuses_unsupported_restatement, 'request_quote_is_verbatim': request_quote_is_verbatim}
INITIAL_CASES = (State(),)
INPUT_CASES = EVENTS
CALCULATE = Step().expected
BAD_EXPECTATIONS = {'unit_without_anchor_closes': UnitWithoutAnchorCloses().expected, 'unsupported_restatement_closes': UnsupportedRestatementCloses().expected, 'paraphrased_request_quote_passes': ParaphrasedRequestQuotePasses().expected}
