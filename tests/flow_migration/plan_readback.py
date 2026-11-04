"""The plan readback shows every planned unit with its bound text and findings the same way from every chain file, also while the plan is ahead of the text."""
from __future__ import annotations
from dataclasses import dataclass, replace
from .reader_cases import _RealReaderChain

@dataclass(frozen=True)
class Event:
    kind: str
    quality: str = ''
    input: str = ''

@dataclass(frozen=True)
class State:
    readback_case: str = ''
    readback: str = ''
    readback_input: str = ''

class Step:

    def readback_for(self, case: str) -> str:
        if case == 'writer':
            return 'writer_shown'
        if case == 'anchors':
            return 'anchors_shown'
        return 'ahead_shown' if case == 'ahead' else 'shown' if case == 'leak' else 'clean'

    def expected(self, event, state):
        result = self.readback_for(event.quality)
        return ('read', replace(state, readback_case=event.quality, readback=result, readback_input=event.input))

class ReadbackHidesFindings(Step):
    """Known-bad: the plan readback shows the plan and text but not the checks' findings."""

    def readback_for(self, case: str) -> str:
        return 'hidden' if case == 'leak' else 'clean'

def _readback_shows_failing_units(state: State):
    if state.readback_case == 'leak' and state.readback != 'shown':
        return False
    return True

def readback_shows_the_plan_ahead_of_the_text(state):
    if state.readback_case == 'ahead' and state.readback != 'ahead_shown':
        return False
    return True

class BlockedChainHidesThePlan(Step):

    def readback_for(self, case):
        return 'hidden' if case == 'ahead' else super().readback_for(case)

def readback_is_the_same_from_every_chain_file(state):
    if state.readback_input and state.readback != Step().readback_for(state.readback_case):
        return False
    return True

class PlanFileReadsBackNoBinding(Step):

    def expected(self, event, state):
        results = super().expected(event, state)
        if event.input in ('reader-brief.json', 'closure-input.json'):
            return (results[0], replace(results[1], readback='unbound'))
        return results

def says_line_shows_its_anchors(state):
    if state.readback_case == 'anchors' and state.readback != 'anchors_shown':
        return False
    return True

class SaysLineHidesAMissingAnchor(Step):
    """Known-bad: anchors are merged for the planned unit, hiding its unanchored sentence."""

    def readback_for(self, case):
        return 'anchors_hidden' if case == 'anchors' else super().readback_for(case)

def writer_added_units_are_listed(state):
    if state.readback_case == 'writer' and state.readback != 'writer_shown':
        return False
    return True

class WriterUnitLeftUnlisted(Step):

    def readback_for(self, case):
        return 'writer_hidden' if case == 'writer' else super().readback_for(case)
CASES = ('clean', 'leak', 'ahead', 'anchors', 'writer')
INPUT_FILES = ('brief-request.json', 'reader-brief.json', 'closure-input.json', 'shared-writing.json', 'shared-writing-result.json')
EVENTS = tuple((Event('readback', case, name) for case in CASES for name in INPUT_FILES))
RULES = {'writer_added_units_are_listed': writer_added_units_are_listed, 'says_line_shows_its_anchors': says_line_shows_its_anchors, 'readback_is_the_same_from_every_chain_file': readback_is_the_same_from_every_chain_file, 'readback_shows_the_plan_ahead_of_the_text': readback_shows_the_plan_ahead_of_the_text, 'readback_shows_failing_units': _readback_shows_failing_units}
INITIAL_CASES = (State(),)
INPUT_CASES = EVENTS
CALCULATE = Step().expected
BAD_EXPECTATIONS = {'writer_unit_left_unlisted': WriterUnitLeftUnlisted().expected, 'plan_file_reads_back_no_binding': PlanFileReadsBackNoBinding().expected, 'blocked_chain_hides_the_plan': BlockedChainHidesThePlan().expected, 'readback_hides_findings': ReadbackHidesFindings().expected, 'says_line_hides_a_missing_anchor': SaysLineHidesAMissingAnchor().expected}
