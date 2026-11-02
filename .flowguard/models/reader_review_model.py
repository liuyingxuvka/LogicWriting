"""Explicit review stamps bind current content, evidence and plan, not the folder they sit in.

Independent single-input cases reuse the native reader helper. The original
reader_artifact_model keeps its three-step review/edit/close protocol unchanged.
A stamp binds bytes, plan and evidence, never the folder they sit in: a stamped
folder moved elsewhere closes without a new stamp, and an edit there is still stale.
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
    'tests/unit/test_review_stamp.py:test_moving_a_stamped_folder_keeps_its_review',
    'tests/unit/test_review_stamp.py:test_complete_repair_review_can_be_stamped',
    'tests/unit/test_review_reread.py:test_restamping_an_edit_without_rereading_it_is_refused',
    'tests/unit/test_review_reread.py:test_quoting_the_new_wording_lets_the_review_be_stamped_again',
    'tests/unit/test_review_reread.py:test_removing_the_stamp_does_not_skip_the_reread',
    'tests/unit/test_review_reread.py:test_a_changed_heading_or_title_must_be_quoted_again',
    'tests/unit/test_review_reread.py:test_removing_the_saved_copy_and_the_stamp_is_not_a_first_review',
    'tests/unit/test_review_reread.py:test_a_review_never_stamped_needs_a_declared_first_review',
    'tests/unit/test_review_reread.py:test_a_saved_copy_rewritten_to_the_new_text_is_refused',
    'tests/unit/test_review_reread.py:test_a_review_stamped_before_cannot_be_declared_a_first_review',
    'tests/unit/test_review_reread.py:test_a_lost_copy_is_saved_again_only_on_the_text_its_sealed_stamp_names',
    'tests/unit/test_review_reread.py:test_a_quote_of_the_changed_word_alone_is_not_a_reread',
]}
CASES = {'unstamped': 'judgment_unstamped', 'stamped': 'passed', 'edited': 'judgment_stale',
         'unreviewed': 'judgment_content_unit_unreviewed:cu-perf',
         'failed_stamp': 'failed+unchanged', 'invalid_review': 'failed+unchanged',
         'repeat_stamp': 'stamped+unchanged', 'time_fields': 'stable', 'moved': 'passed',
         'valid_repair': 'stamped+needs_repair', 'restamp_unread': 'review_not_reread', 'restamp_reread': 'passed',
         'restamp_heading': 'review_not_reread', 'record_removed': 'review_text_unknown',
         'record_forged': 'reviewed_text_invalid', 'one_word_reread': 'review_not_reread',
         'stamped_declared_first': 'review_not_first', 'copy_restored': 'passed'}


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


class RestampCertifiesUnreadText(Review):
    """The 4.1.0 defect: --stamp-review re-certified edited text without any reread."""
    def result_for(self, case):
        return 'passed' if case == 'restamp_unread' else super().result_for(case)


class RestampSkipsHeadings(Review):
    """Round-1 review gap: only body units were compared, so a changed heading or title was re-certified unread."""
    def result_for(self, case):
        return 'passed' if case == 'restamp_heading' else super().result_for(case)


class RemovedRecordStartsOver(Review):
    """Round-1 review gap: with the saved copy and the stamp removed, a plain stamp certified the edit unread.

    Since round 2 the evidence fingerprints the earlier stamp computed still show it was stamped, so the
    expected answer is review_text_unknown, not a call for a first review."""
    def result_for(self, case):
        return 'passed' if case in ('record_removed', 'record_forged') else super().result_for(case)


class OneWordQuoteRereads(Review):
    """Round-2 review gap: quoting the changed word alone ('multi') counted as rereading its sentence."""
    def result_for(self, case):
        return 'passed' if case == 'one_word_reread' else super().result_for(case)


class StampedReviewRedeclaredFirst(Review):
    """Round-2 review gap: a stamped review whose copy was dropped was stamped on edited text as a first review."""
    def result_for(self, case):
        return 'passed' if case == 'stamped_declared_first' else super().result_for(case)


class MovedFolderStalesReview(Review):
    """The 4.1.0 defect: absolute paths in fingerprints made a moved copy look edited."""
    def result_for(self, case):
        return 'judgment_stale' if case == 'moved' else super().result_for(case)


def review_belongs_to_text(state, trace):
    if state.review_case and state.review_result != CASES[state.review_case]:
        return InvariantResult.fail('only an explicitly stamped current review covering every required unit may close; default runs never create or refresh its stamp')
    return InvariantResult.pass_()


INVARIANTS = (Invariant('review_belongs_to_text',
    'a review closes only the text and plan it was stamped on, covers every required unit, and is re-stamped on edited text only after quoting the whole sentence of each change, headings and title included; without its saved copy a review never stamped is stamped only as a declared first review, and one stamped before only on the text its sealed stamp names', review_belongs_to_text),)


def explorer(step):
    return Explorer(workflow=Workflow((step,)), initial_states=(State(),),
                    external_inputs=tuple(Event(quality=case) for case in CASES),
                    invariants=INVARIANTS, max_sequence_length=1, progress_steps=0)


def build_explorer():
    return explorer(Review())


def broken_variants():
    return {'edited_text_keeps_the_old_review': explorer(EditedTextKeepsOldReview()),
            'moved_folder_stales_the_review': explorer(MovedFolderStalesReview()),
            'restamp_certifies_unread_text': explorer(RestampCertifiesUnreadText()),
            'restamp_skips_headings': explorer(RestampSkipsHeadings()),
            'removed_record_starts_over': explorer(RemovedRecordStartsOver()),
            'one_word_quote_rereads': explorer(OneWordQuoteRereads()),
            'stamped_review_redeclared_first': explorer(StampedReviewRedeclaredFirst())}


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
