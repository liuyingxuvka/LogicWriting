"""Explicit review stamps bind current content, evidence and plan, not the folder they sit in.

Independent single-input cases reuse the native reader helper. The original
reader_artifact keeps its three-step review/edit/close protocol unchanged.
A stamp binds bytes, plan and evidence, never the folder they sit in: a stamped
folder moved elsewhere closes without a new stamp, and an edit there is still stale.
"""
from dataclasses import dataclass, replace
from .reader_cases import _RealReaderChain
CASES = {'unstamped': 'judgment_unstamped', 'stamped': 'passed', 'edited': 'judgment_stale', 'unreviewed': 'judgment_content_unit_unreviewed:cu-perf', 'failed_stamp': 'failed+unchanged', 'invalid_review': 'failed+unchanged', 'repeat_stamp': 'stamped+unchanged', 'time_fields': 'stable', 'moved': 'passed', 'valid_repair': 'stamped+needs_repair', 'restamp_unread': 'review_not_reread', 'restamp_reread': 'passed', 'restamp_heading': 'review_not_reread', 'record_removed': 'review_text_unknown', 'record_forged': 'reviewed_text_invalid', 'one_word_reread': 'review_not_reread', 'stamped_declared_first': 'review_not_first', 'copy_restored': 'passed'}

@dataclass(frozen=True)
class Event:
    kind: str = 'stamp'
    quality: str = ''

@dataclass(frozen=True)
class State:
    review_case: str = ''
    review_result: str = ''

class Review:

    def result_for(self, case):
        return CASES[case]

    def expected(self, event, state):
        result = self.result_for(event.quality)
        return (result, replace(state, review_case=event.quality, review_result=result))

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

def review_belongs_to_text(state):
    if state.review_case and state.review_result != CASES[state.review_case]:
        return False
    return True
RULES = {'review_belongs_to_text': review_belongs_to_text}
INITIAL_CASES = (State(),)
INPUT_CASES = tuple((Event(quality=case) for case in CASES))
CALCULATE = Review().expected
BAD_EXPECTATIONS = {'edited_text_keeps_the_old_review': EditedTextKeepsOldReview().expected, 'moved_folder_stales_the_review': MovedFolderStalesReview().expected, 'restamp_certifies_unread_text': RestampCertifiesUnreadText().expected, 'restamp_skips_headings': RestampSkipsHeadings().expected, 'removed_record_starts_over': RemovedRecordStartsOver().expected, 'one_word_quote_rereads': OneWordQuoteRereads().expected, 'stamped_review_redeclared_first': StampedReviewRedeclaredFirst().expected}
