"""Fiction tree: the composition plan owns unit identity, and domain surfaces only refer to it.

Each case is one input to the real fiction checks of the shipped long-form
project: the novel ledger as shipped, a ledger unit the plan does not have, a
ledger row repeating a field the plan owns, a world claim read from a saved
WorldGuard report or written by hand, and long-form closure over the complete
project or after its ledger is emptied.
"""
from __future__ import annotations
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / 'skills' / 'logic-writing' / 'routes' / 'fiction'
CASES = {'planned_ledger_unit': 'accepted', 'unplanned_ledger_unit': 'unit_not_in_plan', 'ledger_repeats_plan_field': 'retired_unit_field', 'world_status_from_report': 'pass', 'handwritten_world_status': 'worldguard_status_without_report', 'complete_project': 'passed', 'emptied_ledger': 'needs_repair'}

@dataclass(frozen=True)
class Event:
    case: str

@dataclass(frozen=True)
class State:
    case: str = ''
    result: str = ''

class Check:
    """Intended behavior: every fiction case gets the result in CASES."""

    def result_for(self, case: str) -> str:
        return CASES[case]

    def expected(self, event: Event, state: State):
        result = self.result_for(event.case)
        return (result, replace(state, case=event.case, result=result))

class AcceptsUnplannedUnit(Check):
    """Known-bad: a ledger unit outside the plan is accepted."""

    def result_for(self, case):
        return 'accepted' if case == 'unplanned_ledger_unit' else super().result_for(case)

class LedgerRepeatsPlanFields(Check):
    """Known-bad: a ledger row may restate a field the plan owns."""

    def result_for(self, case):
        return 'accepted' if case == 'ledger_repeats_plan_field' else super().result_for(case)

class HandwrittenWorldStatusPasses(Check):
    """Known-bad: a handwritten world status counts as a pass."""

    def result_for(self, case):
        return 'pass' if case == 'handwritten_world_status' else super().result_for(case)

class EmptyLedgerPasses(Check):
    """Known-bad: long-form closure passes after its ledger is emptied."""

    def result_for(self, case):
        return 'passed' if case == 'emptied_ledger' else super().result_for(case)

def _expects(cases: dict, message: str):

    def rule(state: State):
        if state.case in cases and state.result != cases[state.case]:
            return False
        return True
    return rule
EVENTS = tuple((Event(case) for case in CASES))

class _RealFiction:
    """Runs the real fiction checks on a copy of the shipped long-form project."""

    def reset(self, state: State) -> None:
        for path in (ROOT / 'skills' / 'logic-writing' / 'scripts', ROUTE / 'scripts'):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        import longform_closure_check
        import novel_ledger_check
        import story_ledger_check
        self.longform, self.novel, self.story = (longform_closure_check, novel_ledger_check, story_ledger_check)
        self.folder = Path(tempfile.mkdtemp(prefix='lw-fiction-contract-'))
        self.project = self.folder / 'project'
        shutil.copytree(ROUTE / 'examples' / 'longform_novel_project', self.project)
        shutil.copyfile(ROOT / 'tests' / 'fixtures' / 'trials' / 'trialB' / 'wg-v2.json', self.folder / 'wg-v2.json')
        self.state = state

    def _run(self, case: str) -> str:
        ledger_path = self.project / 'novel-ledger.json'
        if case in {'planned_ledger_unit', 'unplanned_ledger_unit', 'ledger_repeats_plan_field'}:
            ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
            if case == 'unplanned_ledger_unit':
                ledger['story_units'][0]['planned_unit_id'] = 'unknown-book'
            elif case == 'ledger_repeats_plan_field':
                ledger['story_units'][0]['contribution'] = 'Restated from the plan.'
            codes = {row['code'] for row in self.novel.validate_ledger(ledger, str(ledger_path))['issues']}
            if any((code.startswith('unit_not_in_plan:') for code in codes)):
                return 'unit_not_in_plan'
            return 'retired_unit_field' if 'retired_unit_field' in codes else 'accepted'
        if case == 'world_status_from_report':
            return self.story.read_worldguard_status({'worldguard_report': 'wg-v2.json'}, str(self.folder / 'ledger.json'))
        if case == 'handwritten_world_status':
            report = self.story.validate_ledger({'worldguard_claims': [{'worldguard_status': 'pass'}]}, str(self.folder / 'ledger.json'))
            codes = {row['code'] for row in report['issues']}
            return 'worldguard_status_without_report' if 'worldguard_status_without_report' in codes else 'pass'
        source = self.project / 'project-mesh.json'
        payload = json.loads(source.read_text(encoding='utf-8'))
        saved = ledger_path.read_bytes()
        try:
            if case == 'emptied_ledger':
                ledger_path.write_text('{}', encoding='utf-8')
            return 'passed' if self.longform.validate(payload, str(source))['passed'] else 'needs_repair'
        finally:
            ledger_path.write_bytes(saved)

    def observe(self, event):
        case = event.case
        result = self._run(case)
        self.state = replace(self.state, case=case, result=result)
        return (result, self.state)

    def close(self) -> None:
        shutil.rmtree(getattr(self, 'folder', ''), ignore_errors=True)
RULES = {'ledger_units_are_planned_units': _expects({'unplanned_ledger_unit': 'unit_not_in_plan', 'planned_ledger_unit': 'accepted'}, 'a ledger unit outside the plan was accepted'), 'unit_fields_live_only_in_the_plan': _expects({'ledger_repeats_plan_field': 'retired_unit_field'}, 'a ledger row restated a plan-owned field'), 'world_status_comes_from_native_reports': _expects({'handwritten_world_status': 'worldguard_status_without_report', 'world_status_from_report': 'pass'}, 'a handwritten world status replaced the native report'), 'emptied_ledger_fails_longform_closure': _expects({'emptied_ledger': 'needs_repair', 'complete_project': 'passed'}, 'long-form closure passed without its ledger')}
INITIAL_CASES = (State(),)
INPUT_CASES = EVENTS
CALCULATE = Check().expected
BAD_EXPECTATIONS = {'unplanned_ledger_unit_accepted': AcceptsUnplannedUnit().expected, 'ledger_repeats_plan_fields': LedgerRepeatsPlanFields().expected, 'handwritten_world_status_passes': HandwrittenWorldStatusPasses().expected, 'empty_ledger_passes': EmptyLedgerPasses().expected}
