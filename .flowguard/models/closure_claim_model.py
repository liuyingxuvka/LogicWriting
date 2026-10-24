"""Saved provider reports constrain broad claims without changing textual closure."""
from dataclasses import dataclass, replace
from pathlib import Path
import json
import shutil
import sys
import tempfile

from flowguard import (FunctionResult, Invariant, InvariantResult, ReplayObservation,
                       Workflow, replay_trace, select_covering_traces)
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer

MODEL_ID = 'closure_claim_model'
PARENT = 'reader_artifact_model'
COMPONENTS = ['reader-closure', 'travel-model', 'researchguard-handoff']
IMPLEMENTED_BY = {
    'Close': 'skills/logic-writing/scripts/derive_closure.py:derive_closure',
    'Reports': 'skills/logic-writing/scripts/derive_closure.py:provider_checks',
    'ResearchVerdict': 'skills/logic-writing/scripts/researchguard_status.py:assess_research_verdict',
    'TravelClaims': 'skills/logic-writing/routes/travel/scripts/travel_contract.py:review_plan',
}
TESTED_BY = {
    'research_verdict_risks_are_preserved': ['tests/unit/test_freshness_closure.py:test_provider_status_is_copied_from_the_report_file', 'tests/unit/test_researchguard_status.py:test_researchguard_verdict_decides_the_provider_check'],
    "travel_world_failure_limits_claim": ["tests/unit/test_travel.py:test_failing_world_report_limits_the_claim_level"],
    'broad_claim_needs_every_required_provider': ['tests/unit/test_freshness_closure.py:test_missing_required_provider_report_blocks_the_broad_claim'],
    'provider_status_is_copied_unchanged': ['tests/unit/test_freshness_closure.py:test_provider_status_is_copied_from_the_report_file'],
    'missing_or_failed_provider_is_named': ['tests/unit/test_freshness_closure.py:test_unreadable_report_is_not_a_pass'],
}
ROOT = Path(__file__).resolve().parents[2]
PASSING = {'researchguard': 'passed', 'worldguard': 'PASS'}
RESEARCH_PASS = {'research_ready', 'research_contested', 'research_source_only'}
RESEARCH_FAIL = {'research_search_open', 'research_errors', 'research_live_withhold', 'research_alternative_conflict'}


@dataclass(frozen=True)
class State:
    owner: str
    independent: bool = True
    report: str = 'not_run'
    closed: bool = False
    copied: str = ''
    broad: bool = False
    named: bool = False
    travel_claim_level: str = 'initial_plan'
    research_risks: tuple[str, ...] = ()


@dataclass(frozen=True)
class Event:
    kind: str
    status: str = ''


def provider(state):
    return 'researchguard' if state.owner == 'investigation' else 'worldguard'


def expected_status(state):
    if state.report == 'not_run':
        return 'not_run'
    if provider(state) == 'worldguard':
        return state.report if state.report in {'PASS', 'FAIL'} else 'unreadable'
    return 'passed' if state.report in RESEARCH_PASS else 'failed' if state.report in RESEARCH_FAIL else 'unreadable'


def expected_research_risks(state):
    if provider(state) != 'researchguard':
        return ()
    return {'research_contested': ('research:contested',),
            'research_source_only': ('research:root_claim_not_run',),
            'research_live_withhold': ('research:wording_boundary',)}.get(state.report, ())


def report_input(owner, case):
    """Finite native input cases, including the source-only shipped verdict shape."""
    if case in {'PASS', 'FAIL'}:
        return {'status': case}, []
    if case not in RESEARCH_PASS | RESEARCH_FAIL:
        return {}, []
    document = json.loads((ROOT / 'tests/fixtures/trials/research-status.json').read_text(encoding="utf-8"))
    verdict = document['verdict']
    if case != 'research_source_only':
        verdict['root_claim'] = {'id': 'h-main-answer', 'wording_license': 'assert',
                                 'reason': 'Native argument support is sufficient within scope.'}
    if case == 'research_contested':
        verdict['contested'] = True
    elif case == 'research_search_open':
        verdict['search'] = 'continue_search'
    elif case == 'research_errors':
        verdict['errors'] = 1
    elif case == 'research_live_withhold':
        verdict['root_claim'].update(wording_license='withhold', reason='Native counterevidence remains.')
        verdict['live_hypotheses'].append('h-other')
        document['hypotheses'].append({'id': 'h-other'})
    elif case == 'research_alternative_conflict':
        document['hypotheses'].append({'id': 'h-other', 'experiment': {'status': 'eliminated'}})
        return document, ([{'alternative_id': 'h-other', 'safe_meaning': 'An eliminated alternative is still called live.',
                            'status': 'live', 'content_unit_ids': ['content:answer']}] if owner == 'investigation' else [])
    return document, []


class Step:
    name = 'Step'
    reads = ('owner', 'independent', 'report')
    writes = ('report', 'closed', 'copied', 'broad', 'named', 'travel_claim_level', 'research_risks')
    ignore, rewrite, omit = False, False, False

    def apply(self, event, state):
        if event.kind == 'report':
            return (FunctionResult('saved', replace(state, report=event.status, closed=False,
                                                   copied='', broad=False, named=False, travel_claim_level='initial_plan', research_risks=()), label='saved'),)
        current_status = expected_status(state)
        passing = current_status == PASSING[provider(state)]
        result = replace(state, closed=True, copied=PASSING[provider(state)] if self.rewrite else current_status,
                         broad=state.independent and (passing or self.ignore),
                         named=not passing and not self.omit,
                         travel_claim_level='bookable' if state.owner == 'travel-guide' and passing else 'initial_plan',
                         research_risks=expected_research_risks(state))
        case_label = 'foreign_report' if (state.owner == 'travel-guide' and state.report in RESEARCH_PASS | RESEARCH_FAIL) or (state.owner == 'investigation' and state.report in {'PASS', 'FAIL'}) else state.report
        return (FunctionResult('passed', result, label=f'closed:{state.owner}:{case_label}'),)


class IgnoreReports(Step):
    ignore = True


class RewriteFailure(Step):
    rewrite = True


class OmitRisk(Step):
    omit = True


def broad_needs_reports(state, trace):
    if state.broad and (not state.independent or expected_status(state) != PASSING[provider(state)]):
        return InvariantResult.fail('broad claim without a passing required report and independent read')
    return InvariantResult.pass_()


def status_copied(state, trace):
    if state.closed and state.copied != expected_status(state):
        return InvariantResult.fail('native status was rewritten')
    return InvariantResult.pass_()


def failure_named(state, trace):
    if state.closed and expected_status(state) != PASSING[provider(state)] and not state.named:
        return InvariantResult.fail('missing or failed provider is absent from residual risk')
    return InvariantResult.pass_()


class TravelReadsHandwrittenWorldStatus(Step):
    """Known bad: a travel declaration overwrites a failing saved report."""
    def apply(self, event, state):
        results = super().apply(event, state)
        if event.kind == 'close' and state.owner == 'travel-guide':
            return tuple(replace(result, new_state=replace(result.new_state,
                copied='PASS', travel_claim_level='bookable', broad=state.independent)) for result in results)
        return results


def travel_world_failure_limits_claim(state, trace):
    if state.owner == 'travel-guide' and state.closed and expected_status(state) != 'PASS' and state.travel_claim_level != 'initial_plan':
        return InvariantResult.fail('a non-pass saved world report permits only initial planning')
    return InvariantResult.pass_()


class ReadsMemberReports(Step):
    """Known bad: green member results replace the research tree verdict."""
    def apply(self, event, state):
        results = super().apply(event, state)
        if event.kind == 'close' and provider(state) == 'researchguard':
            return tuple(replace(result, new_state=replace(result.new_state,
                copied='passed', broad=state.independent, named=False)) for result in results)
        return results


class DropsResearchRisks(Step):
    """Known bad: discard the research disagreement or wording boundary."""
    def apply(self, event, state):
        results = super().apply(event, state)
        if event.kind == 'close' and provider(state) == 'researchguard':
            return tuple(replace(result, new_state=replace(result.new_state,
                research_risks=())) for result in results)
        return results


def research_verdict_risks_are_preserved(state, trace):
    if state.closed and state.research_risks != expected_research_risks(state):
        return InvariantResult.fail('contested or non-assert research wording risk was lost')
    if state.closed and state.report == 'research_contested' and provider(state) == 'researchguard' and state.broad != state.independent:
        return InvariantResult.fail('contested was turned into a research gate')
    if state.closed and state.report == 'research_source_only' and provider(state) == 'researchguard' and state.broad != state.independent:
        return InvariantResult.fail('source-only sufficiency was incorrectly treated as a missing assert gate')
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant('research_verdict_risks_are_preserved', 'disagreement and wording boundaries remain honest', research_verdict_risks_are_preserved),
    Invariant("travel_world_failure_limits_claim", "travel reads saved world status", travel_world_failure_limits_claim),
    Invariant('broad_claim_needs_every_required_provider', 'every required report passes', broad_needs_reports),
    Invariant('provider_status_is_copied_unchanged', 'native status remains unchanged', status_copied),
    Invariant('missing_or_failed_provider_is_named', 'all missing or failing providers are named', failure_named),
)
EVENTS = tuple(Event('report', status) for status in (*sorted(RESEARCH_PASS | RESEARCH_FAIL), 'PASS', 'FAIL', 'unreadable')) + (Event('close'),)


def explorer(step):
    return Explorer(workflow=Workflow((step,)),
                    initial_states=tuple(State(owner, independent) for owner in ('investigation', 'travel-guide')
                                         for independent in (True, False)),
                    external_inputs=EVENTS, invariants=INVARIANTS, max_sequence_length=2, progress_steps=0)


def build_explorer():
    return explorer(Step())


def broken_variants():
    return {'drops_research_risks': explorer(DropsResearchRisks()),
            'closure_reads_member_reports': explorer(ReadsMemberReports()),
            'travel_reads_handwritten_world_status': explorer(TravelReadsHandwrittenWorldStatus()),
            'closure_ignores_provider_reports': explorer(IgnoreReports()),
            'failed_report_read_as_pass': explorer(RewriteFailure()),
            'missing_provider_not_named': explorer(OmitRisk())}


class Native:
    """Replay current closure and trip validators; reuse immutable protocol fixtures."""
    def reset(self, state):
        self.state = state
        self._fixture([])

    def _fixture(self, alternatives):
        from copy import deepcopy
        from unittest.mock import patch
        for path in (ROOT, ROOT / 'skills/logic-writing/scripts'):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        from tests import v2_support as fixtures
        from derive_closure import derive_closure
        from _common import fingerprint
        state = self.state
        key = (state.owner, state.independent, bool(alternatives))
        if not hasattr(self, 'cache'):
            self.cache = {}
        if key not in self.cache:
            root = Path(tempfile.mkdtemp(prefix='lw-provider-model-'))
            native_build = fixtures.build_reader_brief
            def build_with_inputs(**kwargs):
                # Change the input before native fingerprinting; no production check is mocked.
                kwargs['content_boundaries'] = deepcopy(kwargs['content_boundaries'])
                kwargs['content_boundaries']['alternatives'] = deepcopy(alternatives)
                return native_build(**kwargs)
            with patch.object(fixtures, 'build_reader_brief', build_with_inputs):
                request = fixtures.closure_input(fixtures.complete_chain(root, state.owner))
            request['provider_reports'] = []
            if not state.independent:
                judgment = request['judgment']
                judgment['judge_kind'] = 'self_review'
                judgment.pop('judgment_fingerprint')
                judgment['judgment_fingerprint'] = fingerprint(judgment)
            self.cache[key] = (root, request)
        self.root, request = self.cache[key]
        self.request = deepcopy(request)
        self.derive = derive_closure
        if state.owner == 'travel-guide':
            travel = ROOT / 'skills/logic-writing/routes/travel'
            if str(travel / 'scripts') not in sys.path:
                sys.path.insert(0, str(travel / 'scripts'))
            from fixture_mutation import apply_mutations
            from travel_contract import review_plan
            self.trip_path = travel / 'examples/good_city_couple_trip/plan.json'
            base = json.loads(self.trip_path.read_text(encoding="utf-8"))
            current = json.loads((travel / 'examples/positive_cases/near_future_bookable.json').read_text(encoding="utf-8"))
            self.trip = apply_mutations(base, current['mutations'])
            self.trip['world_feasibility']['checks'][0]['worldguard_report'] = str(self.root / 'unavailable-world.json')
            self.review_trip = review_plan

    def apply_step(self, step):
        event, state = step.function_input, self.state
        if event.kind == 'report':
            document, alternatives = report_input(state.owner, event.status)
            self._fixture(alternatives)
            path = self.root / 'native.json'
            path.write_text('{}' if event.status == 'unreadable' else json.dumps(document), encoding='utf-8')
            self.request['provider_reports'] = [{'provider': provider(state), 'path': str(path)}]
            if state.owner == 'travel-guide':
                self.trip['world_feasibility']['checks'][0]['worldguard_report'] = str(path)
            state = replace(state, report=event.status, closed=False, copied='', broad=False,
                            named=False, travel_claim_level='initial_plan', research_risks=())
            output = 'saved'
        else:
            closure = self.derive(self.request)['closure']
            row = closure['provider_checks'][0]
            state = replace(state, closed=True, copied=row['status'], broad=closure['broad_claim_allowed'],
                named=any(r['defect_id'] == f'provider:{provider(state)}' for r in closure['residual_risk']),
                research_risks=tuple(sorted(r['defect_id'] for r in closure['residual_risk'] if r['defect_id'].startswith('research:'))),
                travel_claim_level=self.review_trip(self.trip, plan_path=self.trip_path)['allowed_claim_level'] if state.owner == 'travel-guide' else 'initial_plan')
            output = closure['status']
        self.state = state
        return ReplayObservation(function_name=step.function_name, observed_output=output, observed_state=state)

    def observe_state(self):
        return self.state

    def observe_output(self):
        return None

    def close(self):
        for root, _ in getattr(self, 'cache', {}).values():
            shutil.rmtree(root, ignore_errors=True)


def conformance():
    result, adapter = None, Native()
    try:
        for trace in select_covering_traces(build_explorer().explore().traces):
            result = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                  rules=(projected_state_matches(), projected_output_matches()))
            if not result.ok:
                return result
        return result
    finally:
        adapter.close()
