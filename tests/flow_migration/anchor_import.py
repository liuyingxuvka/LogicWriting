"""Imported fields stay source-owned; a researched brief's extra anchors need an explicit outside reason."""
from __future__ import annotations
from dataclasses import dataclass, replace
from .reader_cases import _RealReaderChain

@dataclass(frozen=True)
class Event:
    kind: str
    quality: str = ''
IMPORT_RELATIONS = {'oppose': 'counter', 'limit': 'limit', 'support': 'support', 'none': 'context', 'no_status': 'research_folder needs research_status', 'hand_conflict': 'anchor_relation_conflict'}
AUTHORITY_EXPECTED = {'research': 'passed', 'invented': 'anchor_not_in_research', 'outside': 'passed+risk', 'no_folder': 'passed', 'blank_reason': 'anchor_not_in_research'}

@dataclass(frozen=True)
class State:
    import_case: str = ''
    relation: str = ''
    report_fields_match: bool = True
    authority_case: str = ''
    authority_result: str = ''

class Step:

    def relation_for(self, case: str) -> str:
        return IMPORT_RELATIONS[case]

    def fields_match(self, case):
        return True

    def authority_result(self, case):
        return AUTHORITY_EXPECTED[case]

    def expected(self, event, state):
        if event.kind == 'anchor_authority':
            result = self.authority_result(event.quality)
            return (result, replace(state, authority_case=event.quality, authority_result=result))
        result = self.relation_for(event.quality)
        return ('imported', replace(state, import_case=event.quality, relation=result, report_fields_match=self.fields_match(event.quality)))

class ImportedCounterMarkedSupport(Step):
    """Known-bad: every imported anchor is written as support, whatever the research says."""

    def relation_for(self, case: str) -> str:
        return 'support'

def _imported_anchor_keeps_research_direction(state: State):
    if state.import_case and state.relation != IMPORT_RELATIONS[state.import_case]:
        return False
    return True

def imported_anchor_matches_the_report_row(state):
    if state.import_case and (not state.report_fields_match):
        return False
    return True

class ImportedAnchorIgnoresReportLocator(Step):

    def fields_match(self, case):
        return case != 'support'

def anchors_come_from_research(state):
    if state.authority_case and state.authority_result != AUTHORITY_EXPECTED[state.authority_case]:
        return False
    return True

class InventedAnchorImported(Step):

    def authority_result(self, case):
        return 'passed' if case == 'invented' else super().authority_result(case)
CASES = ('oppose', 'limit', 'support', 'none', 'no_status', 'hand_conflict')
EVENTS = tuple((Event('import', case) for case in CASES)) + tuple((Event('anchor_authority', case) for case in AUTHORITY_EXPECTED))
RULES = {'imported_anchor_matches_the_report_row': imported_anchor_matches_the_report_row, 'imported_anchor_keeps_research_direction': _imported_anchor_keeps_research_direction, 'anchors_come_from_research': anchors_come_from_research}
INITIAL_CASES = (State(),)
INPUT_CASES = EVENTS
CALCULATE = Step().expected
BAD_EXPECTATIONS = {'imported_anchor_ignores_the_report_locator': ImportedAnchorIgnoresReportLocator().expected, 'imported_counter_anchor_marked_support': ImportedCounterMarkedSupport().expected, 'invented_anchor_is_imported': InventedAnchorImported().expected}
