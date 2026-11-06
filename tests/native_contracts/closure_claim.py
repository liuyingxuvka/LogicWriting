"""Saved provider reports constrain broad claims while their raw inputs remain current.

ResearchGuard inputs are checked by digest; a research report counts only for its own folder and keeps its
disagreement and wording risks. Every provider's saved status is copied unchanged, a missing or failed
provider is named, and only passing required reports with an independent read allow the broad claim.
Closure never runs a provider. WorldGuard identity, freshness, scope limits and the travel claim are
world_report; the root claim's wording license is wording_license.
"""
from dataclasses import dataclass, replace
from .provider_cases import PASSING, REPORT_CASES, ROOT, Event, NativeClosure, close_label, close_output, expected_status, provider, stale_report

@dataclass(frozen=True)
class State:
    owner: str
    independent: bool = True
    report: str = 'not_run'
    closed: bool = False
    copied: str = ''
    broad: bool = False
    named: bool = False
    research_risks: tuple[str, ...] = ()

def expected_research_risks(state):
    if provider(state) != 'researchguard':
        return ()
    return {'research_contested': ('research:contested',), 'research_source_only': ('research:root_claim_not_run',), 'research_foreign': ('research:root_claim_not_run',), 'research_live_withhold': ('research:wording_boundary',)}.get(state.report, ())

class Step:
    ignore, rewrite, omit = (False, False, False)

    def expected(self, event, state):
        if event.kind == 'report':
            return ('saved', replace(state, report=event.status, closed=False, copied='', broad=False, named=False, research_risks=()))
        current_status = expected_status(state)
        passing = current_status == PASSING[provider(state)]
        result = replace(state, closed=True, copied=PASSING[provider(state)] if self.rewrite else current_status, broad=state.independent and (passing or self.ignore), named=not passing and (not self.omit), research_risks=expected_research_risks(state))
        return (close_output(state), result)

class IgnoreReports(Step):
    ignore = True

class RewriteFailure(Step):
    rewrite = True

class OmitRisk(Step):
    omit = True

def broad_needs_reports(state):
    if state.broad and (not state.independent or expected_status(state) != PASSING[provider(state)]):
        return False
    return True

def status_copied(state):
    if state.closed and state.copied != expected_status(state):
        return False
    return True

def failure_named(state):
    if state.closed and expected_status(state) != PASSING[provider(state)] and (not state.named):
        return False
    return True

class ReadsMemberReports(Step):
    """Known bad: green member results replace the research tree verdict."""

    def expected(self, event, state):
        results = super().expected(event, state)
        if event.kind == 'close' and provider(state) == 'researchguard':
            return (results[0], replace(results[1], copied='passed', broad=state.independent, named=False))
        return results

class DropsResearchRisks(Step):
    """Known bad: discard the research disagreement or wording boundary."""

    def expected(self, event, state):
        results = super().expected(event, state)
        if event.kind == 'close' and provider(state) == 'researchguard':
            return (results[0], replace(results[1], research_risks=()))
        return results

def research_verdict_risks_are_preserved(state):
    if state.closed and state.research_risks != expected_research_risks(state):
        return False
    if state.closed and state.report == 'research_contested' and (provider(state) == 'researchguard') and (state.broad != state.independent):
        return False
    if state.closed and state.report == 'research_source_only' and (provider(state) == 'researchguard') and (state.broad != state.independent):
        return False
    return True

class ForeignResearchReportPasses(Step):
    """Known bad: a passing report of another research question passes closure."""

    def expected(self, event, state):
        results = super().expected(event, state)
        if event.kind == 'close' and provider(state) == 'researchguard' and (state.report == 'research_foreign'):
            return (results[0], replace(results[1], copied='passed', broad=state.independent, named=False))
        return results

def research_report_belongs_to_the_folder(state):
    if state.closed and provider(state) == 'researchguard' and (state.report == 'research_foreign') and (state.copied != 'failed' or not state.named):
        return False
    return True

def research_report_is_current(state):
    if state.closed and provider(state) == 'researchguard' and stale_report(state) and (state.copied != 'failed' or state.broad or (not state.named)):
        return False
    return True

class StaleResearchReportPasses(Step):

    def expected(self, event, state):
        rows = super().expected(event, state)
        if event.kind == 'close' and provider(state) == 'researchguard' and (state.report == 'research_stale'):
            return ('passed', replace(rows[1], copied='passed', broad=state.independent, named=False))
        return rows
EVENTS = tuple((Event('report', status) for status in REPORT_CASES)) + (Event('close'),)

class Native:
    """Replay the current closure over each saved report case; reuse immutable protocol fixtures."""

    def __init__(self):
        self.closure = NativeClosure()

    def reset(self, state):
        self.state = state
        self.root, self.request = self.closure.request(state.owner, state.independent, [])

    def observe(self, event):
        event, state = (event, self.state)
        if event.kind == 'report':
            self.root, self.request, _ = self.closure.save(state, event.status)
            state = replace(state, report=event.status, closed=False, copied='', broad=False, named=False, research_risks=())
            output = 'saved'
        else:
            closure = self.closure.derive(self.request)
            row = closure['provider_checks'][0]
            state = replace(state, closed=True, copied=row['status'], broad=closure['broad_claim_allowed'], named=any((r['defect_id'] == f'provider:{provider(state)}' for r in closure['residual_risk'])), research_risks=tuple(sorted((r['defect_id'] for r in closure['residual_risk'] if r['defect_id'].startswith('research:')))))
            output = closure['status']
        self.state = state
        return (output, state)

    def close(self):
        self.closure.close()
RULES = {'research_report_is_current': research_report_is_current, 'research_report_belongs_to_the_folder': research_report_belongs_to_the_folder, 'research_verdict_risks_are_preserved': research_verdict_risks_are_preserved, 'broad_claim_needs_every_required_provider': broad_needs_reports, 'provider_status_is_copied_unchanged': status_copied, 'missing_or_failed_provider_is_named': failure_named}
INITIAL_CASES = tuple((State(owner, independent) for owner in ('investigation', 'travel-guide') for independent in (True, False)))
INPUT_CASES = EVENTS
CALCULATE = Step().expected
BAD_EXPECTATIONS = {'stale_research_report_passes': StaleResearchReportPasses().expected, 'drops_research_risks': DropsResearchRisks().expected, 'closure_reads_member_reports': ReadsMemberReports().expected, 'closure_ignores_provider_reports': IgnoreReports().expected, 'failed_report_read_as_pass': RewriteFailure().expected, 'missing_provider_not_named': OmitRisk().expected, 'foreign_research_report_passes': ForeignResearchReportPasses().expected}
