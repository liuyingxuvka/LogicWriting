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

from flowguard import (FunctionResult, Invariant, InvariantResult, ReplayObservation,
                       Workflow, replay_trace)
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFacts

MODEL_ID = 'wording_license_model'
PARENT = 'reader-closure'
COMPONENTS = ['reader-closure', 'researchguard-handoff']
IMPLEMENTED_BY = {
    "WordingBoundary": "skills/logic-writing/scripts/researchguard_status.py:research_wording_boundary",
}
TESTED_BY = {
    "wording_within_license": [
        "tests/unit/test_evidence_rules.py:test_withheld_root_claim_needs_a_limit",
        "tests/unit/test_evidence_rules.py:test_limit_anchor_satisfies_the_license",
    ],
}
ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / 'skills/logic-writing/assets/examples'
LICENSE_EXPECTED = {'source_only': 'passed', 'assert': 'passed',
                    'withhold': 'wording_exceeds_license', 'qualify': 'wording_exceeds_license',
                    'withhold_limit': 'passed+risk', 'qualify_limitation': 'passed+risk',
                    'counter': 'passed+risk', 'unrelated': 'passed+risk', 'optional': 'passed+risk'}


@dataclass(frozen=True)
class State:
    license_case: str = ''
    license_result: str = ''


@dataclass(frozen=True)
class Event:
    kind: str
    status: str = ''


class Step:
    name = 'Step'
    reads = ()
    writes = ('license_case', 'license_result')

    def license_result(self, case):
        return LICENSE_EXPECTED[case]

    def apply(self, event, state):
        result = self.license_result(event.status)
        return (FunctionResult(result, replace(state, license_case=event.status, license_result=result),
                               label='license_' + event.status),)


def wording_within_license(state, trace):
    if state.license_case and state.license_result != LICENSE_EXPECTED[state.license_case]:
        return InvariantResult.fail('only required units citing support for the withheld or qualified root need a limit; other claims and rebuttals stay outside that license')
    return InvariantResult.pass_()


class WithheldClaimStatedPlainly(Step):
    def license_result(self, case):
        return 'passed+risk' if case == 'withhold' else super().license_result(case)


INVARIANTS = (
    Invariant('wording_within_license',
              'when the saved report withholds or qualifies the root claim, a required unit citing an anchor that supports it also carries a limit',
              wording_within_license),
)
EVENTS = tuple(Event('license', case) for case in LICENSE_EXPECTED)


def explorer(step):
    # Each case is one whole native chain run on a fresh copy; a second case never follows the first.
    return Explorer(workflow=Workflow((step,)), initial_states=(State(),),
                    external_inputs=EVENTS, invariants=INVARIANTS, max_sequence_length=1,
                    progress_steps=0)


def build_explorer():
    return explorer(Step())


def broken_variants():
    return {'withheld_claim_stated_plainly': explorer(WithheldClaimStatedPlainly())}


class Native:
    """Replay the current reader chain on the shipped investigation example, one wording case per copy."""
    def _license_probe(self, case):
        from run_chain import run_chain, _stamp_review
        with tempfile.TemporaryDirectory(prefix='lw-license-model-') as temporary:
            folder = Path(temporary) / 'investigation'
            shutil.copytree(EXAMPLES / 'investigation', folder)
            report_path = folder / 'research-status.json'
            report = json.loads(report_path.read_text())
            if case != 'source_only':
                license = 'assert' if case == 'assert' else 'qualify' if case in ('qualify', 'qualify_limitation') else 'withhold'
                report['verdict']['root_claim'] = {'id': 'h-main-answer', 'wording_license': license,
                                                   'reason': 'The root claim remains bounded by its counterevidence.'}
                anchor = next(row for row in report['evidence'] if row['anchor'] == 'anc-314-supported')
                anchor['directions'] = [{'route': 'logic', 'hypothesis': 'h-other' if case == 'unrelated' else 'h-main-answer',
                                         'direction': 'oppose' if case == 'counter' else 'support', 'node': 'E_supported'}]
            report_path.write_text(json.dumps(report))
            path = folder / 'brief-request.json'
            request = json.loads(path.read_text())
            boundaries = request['content_boundaries']
            unit = next(row for row in boundaries['content_units'] if row['content_unit_id'] == 'cu-status-314')
            if case == 'withhold_limit':
                unit['evidence_anchor_ids'].append('anc-314-phase3-undecided')
            elif case == 'qualify_limitation':
                unit['limitation_ids'] = ['lim-scope']
            elif case == 'optional':
                unit['required'] = False
            elif case == 'counter':
                next(row for row in boundaries['evidence_anchors'] if row['anchor_id'] == 'anc-314-supported')['relation'] = 'counter'
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
            risk = any(row.get('defect_id') == 'research:wording_boundary'
                       and row.get('owner') == 'investigation' for row in closure['residual_risk'])
            return 'passed+risk' if closure['status'] == 'passed' and risk else 'missing-risk'

    def reset(self, state):
        for path in (ROOT, ROOT / 'skills/logic-writing/scripts'):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        self.state = state

    def apply_step(self, step):
        event = step.function_input
        result = self._license_probe(event.status)
        self.state = replace(self.state, license_case=event.status, license_result=result)
        return ReplayObservation(function_name=step.function_name, observed_output=result, observed_state=self.state)

    def observe_state(self):
        return self.state

    def observe_output(self):
        return None


def conformance():
    result, adapter = None, Native()
    for trace in build_explorer().explore().traces:
        result = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                              rules=(projected_state_matches(), projected_output_matches()))
        if not result.ok:
            return result
    facts = CodeFacts(ROOT)
    facts.check("native wording license replay conforms", result.ok, result.format_text())
    return facts.report()

USES = {
    'LicenseProbe': 'skills/logic-writing/scripts/run_chain.py:run_chain',
    'StampReview': 'skills/logic-writing/scripts/run_chain.py:_stamp_review',
    'Close': 'skills/logic-writing/scripts/derive_closure.py:derive_closure',
}
