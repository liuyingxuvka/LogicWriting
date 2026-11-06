"""Trip feasibility: the trip plan's own rules decide what a travel guide may claim.

Each case is one real trip-plan input from the travel examples: the base plan, a
handwritten world status, a requested claim above the saved evidence, a current
near-future plan with a passing or a failing saved WorldGuard report, an
unreachable fallback, and a travel composition naming known or unknown routes.
The closure contract decides how closure uses the resulting claim level.
"""
from __future__ import annotations
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / 'skills' / 'logic-writing' / 'routes' / 'travel'
CASES = {'base_plan': 'initial_plan', 'handwritten_status': 'rejected', 'claim_overreach': 'overreach', 'current_passing_report': 'bookable', 'current_failing_report': 'initial_plan', 'fallback_unreachable': 'unreachable', 'composition_known_refs': 'resolved', 'composition_unknown_route': 'unknown_ref'}

@dataclass(frozen=True)
class Event:
    case: str

@dataclass(frozen=True)
class State:
    case: str = ''
    result: str = ''

class Review:
    """Intended behavior: every trip-plan case gets the result in CASES."""

    def result_for(self, case: str) -> str:
        return CASES[case]

    def expected(self, event: Event, state: State):
        result = self.result_for(event.case)
        return (result, replace(state, case=event.case, result=result))

class AcceptsHandwrittenPass(Review):
    """Known-bad: a handwritten world status is read instead of the saved report."""

    def result_for(self, case):
        return 'initial_plan' if case == 'handwritten_status' else super().result_for(case)

class RaisesClaimWithoutEvidence(Review):
    """Known-bad: the requested claim level replaces the derived one."""

    def result_for(self, case):
        return 'bookable' if case == 'claim_overreach' else super().result_for(case)

class IgnoresFailingReport(Review):
    """Known-bad: a failing saved world report still allows booking."""

    def result_for(self, case):
        return 'bookable' if case == 'current_failing_report' else super().result_for(case)

class AcceptsUnknownRoute(Review):
    """Known-bad: the composition may name a route the trip plan does not have."""

    def result_for(self, case):
        return 'resolved' if case == 'composition_unknown_route' else super().result_for(case)

class AcceptsUnreachableFallback(Review):
    """Known-bad: a fallback no route node reaches is accepted."""

    def result_for(self, case):
        return 'initial_plan' if case == 'fallback_unreachable' else super().result_for(case)

def _expects(case: str, wanted: str, message: str):

    def rule(state: State):
        if state.case == case and state.result != wanted:
            return False
        return True
    return rule
EVENTS = tuple((Event(case) for case in CASES))

class _RealTripPlan:
    """Runs the real trip-plan review on the shipped travel examples."""

    def reset(self, state: State) -> None:
        for path in (ROOT / 'skills' / 'logic-writing' / 'scripts', ROUTE / 'scripts'):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        import travel_contract
        from fixture_mutation import apply_mutations
        self.contract, self.mutate = (travel_contract, apply_mutations)
        self.folder = Path(tempfile.mkdtemp(prefix='lw-trip-contract-'))
        self.state = state

    def _example(self, *parts):
        return json.loads(ROUTE.joinpath(*parts).read_text(encoding='utf-8'))

    def _run(self, case: str) -> str:
        plan_path = ROUTE / 'examples' / 'good_city_couple_trip' / 'plan.json'
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        if case.startswith('composition_'):
            assets = ROOT / 'skills' / 'logic-writing' / 'assets' / 'examples' / 'travel'
            trip = json.loads((assets / 'trip-plan.json').read_text(encoding='utf-8'))
            composition = json.loads((assets / 'brief-request.json').read_text(encoding='utf-8'))['route_composition']
            if case == 'composition_unknown_route':
                composition['body_sections'][0]['route_refs'] = ['unknown-route']
            issues = self.contract.validate_composition_refs(trip, composition)
            return 'unknown_ref' if any((row['code'] == 'travel_composition.route_ref.unknown' for row in issues)) else 'resolved'
        if case == 'handwritten_status':
            plan['world_feasibility']['checks'][0]['status'] = 'pass'
        elif case == 'claim_overreach':
            plan['trip_context']['requested_claim_level'] = 'bookable'
        elif case.startswith('current_'):
            plan = self.mutate(plan, self._example('examples', 'positive_cases', 'near_future_bookable.json')['mutations'])
            if case == 'current_failing_report':
                failed = self.folder / 'world-fail.json'
                failed.write_text(json.dumps({'status': 'FAIL'}), encoding='utf-8')
                plan['world_feasibility']['checks'][0]['worldguard_report'] = str(failed)
        elif case == 'fallback_unreachable':
            plan = self.mutate(plan, self._example('examples', 'failure_cases', 'fallback_unreachable.json')['mutations'])
        review = self.contract.review_plan(plan, plan_path=plan_path, repository_root=ROOT)
        codes = {row['code'] for row in review['issues']}
        if case.startswith('current_'):
            return review['allowed_claim_level']
        if 'world_feasibility.status.retired' in codes:
            return 'rejected'
        if 'trip_context.requested_claim_level.overreach' in codes:
            return 'overreach'
        if 'fallback_options.reachability.unproven' in codes:
            return 'unreachable'
        return review['allowed_claim_level'] if not codes else 'invalid'

    def observe(self, event):
        case = event.case
        result = self._run(case)
        self.state = replace(self.state, case=case, result=result)
        return (result, self.state)

    def close(self) -> None:
        shutil.rmtree(getattr(self, 'folder', ''), ignore_errors=True)
RULES = {'handwritten_world_status_is_rejected': _expects('handwritten_status', 'rejected', 'a handwritten world status was accepted'), 'claim_level_never_exceeds_saved_evidence': _expects('claim_overreach', 'overreach', 'the requested claim level exceeded the saved evidence'), 'failing_world_report_limits_the_claim': _expects('current_failing_report', 'initial_plan', 'a failing world report allowed a higher claim'), 'composition_refs_resolve_in_the_trip_plan': _expects('composition_unknown_route', 'unknown_ref', 'an unknown composition route was accepted'), 'fallbacks_are_reachable': _expects('fallback_unreachable', 'unreachable', 'an unreachable fallback was accepted')}
INITIAL_CASES = (State(),)
INPUT_CASES = EVENTS
CALCULATE = Review().expected
BAD_EXPECTATIONS = {'handwritten_pass_accepted': AcceptsHandwrittenPass().expected, 'claim_level_raised_without_evidence': RaisesClaimWithoutEvidence().expected, 'failing_world_report_ignored': IgnoresFailingReport().expected, 'unknown_composition_ref_accepted': AcceptsUnknownRoute().expected, 'unreachable_fallback_accepted': AcceptsUnreachableFallback().expected}
