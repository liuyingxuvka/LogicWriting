"""Explicit review stamps bind current content, evidence, plan and file references.

Independent single-input cases reuse the native reader helper. The original
reader_artifact_model keeps its three-step review/edit/close protocol unchanged.
Copied fixtures are explicitly stamped in their final directory before edits;
moving a saved stamp changes file-reference identity, not the article bytes.
"""
from dataclasses import dataclass, replace

from flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer
from _reader_chain_fixture import _RealReaderChain

MODEL_ID = 'reader_review_model'
PARENT = 'reader-artifact'
COMPONENTS = ['reader-artifact', 'reader-checks', 'reader-closure', 'reader-commands']
IMPLEMENTED_BY = {
    'StampReview': 'skills/logic-writing/scripts/run_chain.py:_stamp_review',
    'PreserveJudgment': 'skills/logic-writing/scripts/reader_fill.py:fill_closure_fingerprints',
}
USES = {
    'StampCommand': 'skills/logic-writing/scripts/run_chain.py:main',
    'ReaderJudgment': 'skills/logic-writing/scripts/reader_checks.py:reader_judgment_from_current',
    'RunChain': 'skills/logic-writing/scripts/run_chain.py:run_chain',
    'Close': 'skills/logic-writing/scripts/derive_closure.py:derive_closure',
}
TESTED_BY = {'review_belongs_to_text': [
    'tests/unit/test_review_stamp.py:test_stamp_review_writes_the_fingerprints',
    'tests/unit/test_review_stamp.py:test_edited_text_makes_the_stamped_review_stale',
    'tests/unit/test_review_stamp.py:test_unstamped_review_is_refused_with_the_command',
    'tests/unit/test_review_stamp.py:test_required_unit_missing_from_the_review_fails',
    'tests/unit/test_review_stamp.py:test_fingerprints_ignore_time_fields',
    'tests/unit/test_review_stamp.py:test_stamp_failure_keeps_the_review_bytes',
    'tests/unit/test_review_stamp.py:test_moving_a_stamped_fixture_requires_explicit_rebinding',
    'tests/unit/test_review_stamp.py:test_complete_repair_review_can_be_stamped',
]}
CASES = {'unstamped': 'judgment_unstamped', 'stamped': 'passed', 'edited': 'judgment_stale',
         'unreviewed': 'judgment_content_unit_unreviewed:cu-perf',
         'failed_stamp': 'failed+unchanged', 'invalid_review': 'failed+unchanged',
         'repeat_stamp': 'stamped+unchanged', 'time_fields': 'stable', 'moved': 'judgment_stale',
         'valid_repair': 'stamped+needs_repair'}


@dataclass(frozen=True)
class Event:
    kind: str = 'stamp'
    quality: str = ''


@dataclass(frozen=True)
class State:
    review_case: str = ''
    review_result: str = ''


class Review:
    name = 'Review'
    reads = ()
    writes = ('review_case', 'review_result')

    def result_for(self, case):
        return CASES[case]

    def apply(self, event, state):
        result = self.result_for(event.quality)
        return (FunctionResult(result, replace(state, review_case=event.quality, review_result=result),
                               label='stamp_' + event.quality),)


class EditedTextKeepsOldReview(Review):
    def result_for(self, case):
        return 'passed' if case == 'edited' else super().result_for(case)


def review_belongs_to_text(state, trace):
    if state.review_case and state.review_result != CASES[state.review_case]:
        return InvariantResult.fail('only an explicitly stamped current review covering every required unit may close; default runs never create or refresh its stamp')
    return InvariantResult.pass_()


INVARIANTS = (Invariant('review_belongs_to_text',
    'a review closes only the text and plan it was stamped on, and covers every required unit', review_belongs_to_text),)


def explorer(step):
    return Explorer(workflow=Workflow((step,)), initial_states=(State(),),
                    external_inputs=tuple(Event(quality=case) for case in CASES),
                    invariants=INVARIANTS, max_sequence_length=1, progress_steps=0)


def build_explorer():
    return explorer(Review())


def broken_variants():
    return {'edited_text_keeps_the_old_review': explorer(EditedTextKeepsOldReview())}


def conformance():
    result = None
    for trace in build_explorer().explore().traces:
        if len(trace.steps) != 1:
            continue
        adapter = _RealReaderChain()
        try:
            result = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                  rules=(projected_state_matches(), projected_output_matches()))
        finally:
            adapter.close()
        if not result.ok:
            return result
    return result
