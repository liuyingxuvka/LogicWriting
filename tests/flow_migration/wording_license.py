"""A saved research report that withholds or qualifies its root claim limits the closure's wording.

A required content unit citing an anchor that supports the restricted root also carries a limit anchor or a
limitation; an assert or source-only report, rebuttals, units citing other hypotheses and optional units stay
outside that license and keep the wording boundary as a residual risk. Replayed through run_chain on a copy
of the shipped investigation example.
"""
from dataclasses import dataclass, replace
from pathlib import Path
import json
import shutil
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / 'skills/logic-writing/assets/examples'
LICENSE_EXPECTED = {'source_only': 'passed', 'assert': 'passed', 'withhold': 'wording_exceeds_license', 'qualify': 'wording_exceeds_license', 'withhold_limit': 'passed+risk', 'qualify_limitation': 'passed+risk', 'counter': 'passed+risk', 'unrelated': 'passed+risk', 'optional': 'passed+risk'}

@dataclass(frozen=True)
class State:
    license_case: str = ''
    license_result: str = ''

@dataclass(frozen=True)
class Event:
    kind: str
    status: str = ''

class Step:

    def license_result(self, case):
        return LICENSE_EXPECTED[case]

    def expected(self, event, state):
        result = self.license_result(event.status)
        return (result, replace(state, license_case=event.status, license_result=result))

def wording_within_license(state):
    if state.license_case and state.license_result != LICENSE_EXPECTED[state.license_case]:
        return False
    return True

class WithheldClaimStatedPlainly(Step):

    def license_result(self, case):
        return 'passed+risk' if case == 'withhold' else super().license_result(case)
EVENTS = tuple((Event('license', case) for case in LICENSE_EXPECTED))

class Native:
    """Replay the current reader chain on the shipped investigation example, one wording case per copy."""

    def _license_probe(self, case):
        from run_chain import run_chain, _stamp_review
        with tempfile.TemporaryDirectory(prefix='lw-license-contract-') as temporary:
            folder = Path(temporary) / 'investigation'
            shutil.copytree(EXAMPLES / 'investigation', folder)
            report_path = folder / 'research-status.json'
            report = json.loads(report_path.read_text())
            if case != 'source_only':
                license = 'assert' if case == 'assert' else 'qualify' if case in ('qualify', 'qualify_limitation') else 'withhold'
                report['verdict']['root_claim'] = {'id': 'h-main-answer', 'wording_license': license, 'reason': 'The root claim remains bounded by its counterevidence.'}
                anchor = next((row for row in report['evidence'] if row['anchor'] == 'anc-314-supported'))
                anchor['directions'] = [{'route': 'logic', 'hypothesis': 'h-other' if case == 'unrelated' else 'h-main-answer', 'direction': 'oppose' if case == 'counter' else 'support', 'node': 'E_supported'}]
            report_path.write_text(json.dumps(report))
            path = folder / 'brief-request.json'
            request = json.loads(path.read_text())
            boundaries = request['content_boundaries']
            unit = next((row for row in boundaries['content_units'] if row['content_unit_id'] == 'cu-status-314'))
            if case == 'withhold_limit':
                unit['evidence_anchor_ids'].append('anc-314-phase3-undecided')
            elif case == 'qualify_limitation':
                unit['limitation_ids'] = ['lim-scope']
            elif case == 'optional':
                unit['required'] = False
            elif case == 'counter':
                next((row for row in boundaries['evidence_anchors'] if row['anchor_id'] == 'anc-314-supported'))['relation'] = 'counter'
                unit['evidence_anchor_ids'].append('anc-313-experimental')
                unit['safe_meaning'] = 'The evidence does not support the claim that free-threading is already the default.'
            path.write_text(json.dumps(request))
            if case not in ('withhold', 'qualify'):
                assert _stamp_review(folder)['exit_code'] == 0
            result = run_chain(folder)
            if result['exit_code']:
                return result['first_failure']['code']
            closure = result['results']['closure']['closure']
            if case in ('source_only', 'assert'):
                return closure['status']
            risk = any((row.get('defect_id') == 'research:wording_boundary' and row.get('owner') == 'investigation' for row in closure['residual_risk']))
            return 'passed+risk' if closure['status'] == 'passed' and risk else 'missing-risk'

    def reset(self, state):
        for path in (ROOT, ROOT / 'skills/logic-writing/scripts'):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        self.state = state

    def observe(self, event):
        result = self._license_probe(event.status)
        self.state = replace(self.state, license_case=event.status, license_result=result)
        return (result, self.state)
RULES = {'wording_within_license': wording_within_license}
INITIAL_CASES = (State(),)
INPUT_CASES = EVENTS
CALCULATE = Step().expected
BAD_EXPECTATIONS = {'withheld_claim_stated_plainly': WithheldClaimStatedPlainly().expected}
