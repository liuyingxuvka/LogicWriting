"""Saved provider reports constrain broad claims while their raw inputs remain current.

ResearchGuard inputs are checked by digest; a research report counts only for its own folder and keeps its
disagreement and wording risks. Every provider's saved status is copied unchanged, a missing or failed
provider is named, and only passing required reports with an independent read allow the broad claim.
Closure never runs a provider. WorldGuard identity, freshness, scope limits and the travel claim are
world_report_model; the root claim's wording license is wording_license_model.
"""
from dataclasses import dataclass, replace

from flowguard import (FunctionResult, Invariant, InvariantResult, ReplayObservation,
                       Workflow, replay_trace, select_covering_traces)
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFacts

from _provider_closure_fixture import (PASSING, REPORT_CASES, ROOT, Event, NativeClosure, close_label,
                                       close_output, expected_status, provider, stale_report)

MODEL_ID = 'closure_claim_model'
PARENT = 'reader-closure'
COMPONENTS = ['reader-closure', 'researchguard-handoff']
IMPLEMENTED_BY = {
    "Reports": "skills/logic-writing/scripts/derive_closure.py:provider_checks",
    "ResearchVerdict": "skills/logic-writing/scripts/researchguard_status.py:assess_research_verdict",
    "ResearchIdentity": "skills/logic-writing/scripts/researchguard_status.py:research_report_identity_problems",
}
TESTED_BY = {
    "research_verdict_risks_are_preserved": [
        "tests/unit/test_closure_claim_model.py:test_provider_status_is_copied_from_the_report_file"
    ],
    "broad_claim_needs_every_required_provider": [
        "tests/unit/test_closure_claim_model.py:test_missing_required_provider_report_blocks_the_broad_claim"
    ],
    "provider_status_is_copied_unchanged": [
        "tests/unit/test_closure_claim_model.py:test_provider_status_is_copied_from_the_report_file"
    ],
    "missing_or_failed_provider_is_named": [
        "tests/unit/test_closure_claim_model.py:test_unreadable_report_is_not_a_pass"
    ],
    "research_report_belongs_to_the_folder": [
        "tests/unit/test_researchguard_status.py:test_report_from_another_folder_fails_the_provider_check"
    ],
    "research_report_is_current": [
        "tests/unit/test_closure_claim_model.py:test_stale_research_report_fails_the_provider_check",
        "tests/unit/test_closure_claim_model.py:test_report_missing_a_models_digest_is_stale",
    ],
}


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
    return {'research_contested': ('research:contested',),
            'research_source_only': ('research:root_claim_not_run',),
            'research_foreign': ('research:root_claim_not_run',),
            'research_live_withhold': ('research:wording_boundary',)}.get(state.report, ())


class Step:
    name = 'Step'
    reads = ('owner', 'independent', 'report')
    writes = ('report', 'closed', 'copied', 'broad', 'named', 'research_risks')
    ignore, rewrite, omit = False, False, False

    def apply(self, event, state):
        if event.kind == 'report':
            return (FunctionResult('saved', replace(state, report=event.status, closed=False,
                                                   copied='', broad=False, named=False, research_risks=()), label='saved'),)
        current_status = expected_status(state)
        passing = current_status == PASSING[provider(state)]
        result = replace(state, closed=True, copied=PASSING[provider(state)] if self.rewrite else current_status,
                         broad=state.independent and (passing or self.ignore),
                         named=not passing and not self.omit,
                         research_risks=expected_research_risks(state))
        return (FunctionResult(close_output(state), result, label=close_label(state)),)


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


class ForeignResearchReportPasses(Step):
    """Known bad: a passing report of another research question passes closure."""
    def apply(self, event, state):
        results = super().apply(event, state)
        if event.kind == 'close' and provider(state) == 'researchguard' and state.report == 'research_foreign':
            return tuple(replace(result, new_state=replace(result.new_state, copied='passed',
                broad=state.independent, named=False)) for result in results)
        return results


def research_report_belongs_to_the_folder(state, trace):
    if state.closed and provider(state) == 'researchguard' and state.report == 'research_foreign' and (state.copied != 'failed' or not state.named):
        return InvariantResult.fail('a research report of another question was counted for this folder')
    return InvariantResult.pass_()


def research_report_is_current(state, trace):
    if (
        state.closed
        and provider(state) == "researchguard"
        and stale_report(state)
        and (state.copied != "failed" or state.broad or not state.named)
    ):
        return InvariantResult.fail("stale research report licensed closure")
    return InvariantResult.pass_()


class StaleResearchReportPasses(Step):
    def apply(self,event,state):
        rows=super().apply(event,state)
        if event.kind=='close' and provider(state)=='researchguard' and state.report=='research_stale':
            return tuple(replace(row,output='passed',new_state=replace(row.new_state,copied='passed',broad=state.independent,named=False)) for row in rows)
        return rows


INVARIANTS = (
    Invariant('research_report_is_current','research inputs match the saved report',research_report_is_current),
    Invariant('research_report_belongs_to_the_folder', 'a research report counts only for its own research folder', research_report_belongs_to_the_folder),
    Invariant('research_verdict_risks_are_preserved', 'disagreement and wording boundaries remain honest', research_verdict_risks_are_preserved),
    Invariant('broad_claim_needs_every_required_provider', 'every required report passes', broad_needs_reports),
    Invariant('provider_status_is_copied_unchanged', 'native status remains unchanged', status_copied),
    Invariant('missing_or_failed_provider_is_named', 'all missing or failing providers are named', failure_named),
)
EVENTS = tuple(Event('report', status) for status in REPORT_CASES) + (Event('close'),)


def explorer(step):
    return Explorer(workflow=Workflow((step,)),
                    initial_states=tuple(State(owner, independent) for owner in ('investigation', 'travel-guide')
                                         for independent in (True, False)),
                    external_inputs=EVENTS, invariants=INVARIANTS, max_sequence_length=2,
                    progress_steps=0)


def build_explorer():
    return explorer(Step())


def broken_variants():
    return {'stale_research_report_passes':explorer(StaleResearchReportPasses()),
            'drops_research_risks': explorer(DropsResearchRisks()),
            'closure_reads_member_reports': explorer(ReadsMemberReports()),
            'closure_ignores_provider_reports': explorer(IgnoreReports()),
            'failed_report_read_as_pass': explorer(RewriteFailure()),
            'missing_provider_not_named': explorer(OmitRisk()),
            'foreign_research_report_passes': explorer(ForeignResearchReportPasses())}


class Native:
    """Replay the current closure over each saved report case; reuse immutable protocol fixtures."""
    def __init__(self):
        self.closure = NativeClosure()

    def reset(self, state):
        self.state = state
        self.root, self.request = self.closure.request(state.owner, state.independent, [])

    def apply_step(self, step):
        event, state = step.function_input, self.state
        if event.kind == 'report':
            self.root, self.request, _ = self.closure.save(state, event.status)
            state = replace(state, report=event.status, closed=False, copied='', broad=False,
                            named=False, research_risks=())
            output = 'saved'
        else:
            closure = self.closure.derive(self.request)
            row = closure['provider_checks'][0]
            state = replace(state, closed=True, copied=row['status'], broad=closure['broad_claim_allowed'],
                named=any(r['defect_id'] == f'provider:{provider(state)}' for r in closure['residual_risk']),
                research_risks=tuple(sorted(r['defect_id'] for r in closure['residual_risk'] if r['defect_id'].startswith('research:'))))
            output = closure['status']
        self.state = state
        return ReplayObservation(function_name=step.function_name, observed_output=output, observed_state=state)

    def observe_state(self):
        return self.state

    def observe_output(self):
        return None

    def close(self):
        self.closure.close()


def conformance():
    result, adapter = None, Native()
    try:
        for trace in select_covering_traces(build_explorer().explore().traces):
            result = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                  rules=(projected_state_matches(), projected_output_matches()))
            if not result.ok:
                return result
        facts = CodeFacts(ROOT)
        facts.unreferenced("skills/logic-writing/scripts/researchguard_handoff.py:build_researchguard_handoff")
        facts.check("native provider replay conforms", result.ok, result.format_text())
        return facts.report()
    finally:
        adapter.close()

USES = {
    'Close': 'skills/logic-writing/scripts/derive_closure.py:derive_closure',
    'WorldIdentity': 'skills/logic-writing/scripts/_common.py:worldguard_report_identity_problems',
    'InputDigests': 'skills/logic-writing/scripts/_common.py:input_digest_problems',
}

NOT_MODELED = {'skills/logic-writing/scripts/derive_closure.py:main': 'Command wrapper: reads the closure request file, calls derive_closure (bound as Close in USES) and writes the closure JSON.'}
