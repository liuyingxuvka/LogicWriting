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
COMPONENTS = ['reader-artifact']
IMPLEMENTED_BY = {
    'Close': 'skills/logic-writing/scripts/derive_closure.py:derive_closure',
    'Reports': 'skills/logic-writing/scripts/derive_closure.py:provider_checks',
}
TESTED_BY = {
    'broad_claim_needs_every_required_provider': ['tests/unit/test_freshness_closure.py:test_missing_required_provider_report_blocks_the_broad_claim'],
    'provider_status_is_copied_unchanged': ['tests/unit/test_freshness_closure.py:test_provider_status_is_copied_from_the_report_file'],
    'missing_or_failed_provider_is_named': ['tests/unit/test_freshness_closure.py:test_unreadable_report_is_not_a_pass'],
}
ROOT = Path(__file__).resolve().parents[2]
PASSING = {'sourceguard': 'stop_sufficient', 'worldguard': 'PASS'}


@dataclass(frozen=True)
class State:
    owner: str
    independent: bool = True
    report: str = 'not_run'
    closed: bool = False
    copied: str = ''
    broad: bool = False
    named: bool = False


@dataclass(frozen=True)
class Event:
    kind: str
    status: str = ''


def provider(state):
    return 'sourceguard' if state.owner == 'investigation' else 'worldguard'


class Step:
    name = 'Step'
    reads = ('owner', 'independent', 'report')
    writes = ('report', 'closed', 'copied', 'broad', 'named')
    ignore, rewrite, omit = False, False, False

    def apply(self, event, state):
        if event.kind == 'report':
            return (FunctionResult('saved', replace(state, report=event.status, closed=False,
                                                   copied='', broad=False, named=False), label='saved'),)
        passing = state.report == PASSING[provider(state)]
        result = replace(state, closed=True, copied=PASSING[provider(state)] if self.rewrite else state.report,
                         broad=state.independent and (passing or self.ignore),
                         named=not passing and not self.omit)
        return (FunctionResult('passed', result, label='closed'),)


class IgnoreReports(Step):
    ignore = True


class RewriteFailure(Step):
    rewrite = True


class OmitRisk(Step):
    omit = True


def broad_needs_reports(state, trace):
    if state.broad and (not state.independent or state.report != PASSING[provider(state)]):
        return InvariantResult.fail('broad claim without a passing required report and independent read')
    return InvariantResult.pass_()


def status_copied(state, trace):
    if state.closed and state.copied != state.report:
        return InvariantResult.fail('native status was rewritten')
    return InvariantResult.pass_()


def failure_named(state, trace):
    if state.closed and state.report != PASSING[provider(state)] and not state.named:
        return InvariantResult.fail('missing or failed provider is absent from residual risk')
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant('broad_claim_needs_every_required_provider', 'every required report passes', broad_needs_reports),
    Invariant('provider_status_is_copied_unchanged', 'native status remains unchanged', status_copied),
    Invariant('missing_or_failed_provider_is_named', 'all missing or failing providers are named', failure_named),
)
EVENTS = tuple(Event('report', status) for status in ('stop_sufficient', 'continue_search', 'PASS', 'FAIL', 'unreadable')) + (Event('close'),)


def explorer(step):
    return Explorer(workflow=Workflow((step,)),
                    initial_states=tuple(State(owner, independent) for owner in ('investigation', 'travel-guide')
                                         for independent in (True, False)),
                    external_inputs=EVENTS, invariants=INVARIANTS, max_sequence_length=2, progress_steps=0)


def build_explorer():
    return explorer(Step())


def broken_variants():
    return {'closure_ignores_provider_reports': explorer(IgnoreReports()),
            'failed_report_read_as_pass': explorer(RewriteFailure()),
            'missing_provider_not_named': explorer(OmitRisk())}


class Native:
    def reset(self, state):
        for path in (ROOT, ROOT / 'skills/logic-writing/scripts'):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        from tests.v2_support import complete_chain, closure_input
        from derive_closure import derive_closure
        from _common import fingerprint
        self.root = Path(tempfile.mkdtemp(prefix='lw-provider-model-'))
        self.request = closure_input(complete_chain(self.root, state.owner))
        self.request['provider_reports'] = []
        if not state.independent:
            judgment = self.request['judgment']
            judgment['judge_kind'] = 'self_review'
            judgment.pop('judgment_fingerprint')
            judgment['judgment_fingerprint'] = fingerprint(judgment)
        self.derive = derive_closure
        self.state = state

    def apply_step(self, step):
        event, state = step.function_input, self.state
        if event.kind == 'report':
            path = self.root / 'native.json'
            path.write_text('{}' if event.status == 'unreadable' else json.dumps({'status': event.status}))
            self.request['provider_reports'] = [{'provider': provider(state), 'path': str(path)}]
            state = replace(state, report=event.status, closed=False, copied='', broad=False, named=False)
            output = 'saved'
        else:
            closure = self.derive(self.request)['closure']
            row = closure['provider_checks'][0]
            state = replace(state, closed=True, copied=row['status'], broad=closure['broad_claim_allowed'],
                            named=any(r['defect_id'] == f'provider:{provider(state)}' for r in closure['residual_risk']))
            output = closure['status']
        self.state = state
        return ReplayObservation(function_name=step.function_name, observed_output=output, observed_state=state)

    def observe_state(self):
        return self.state

    def observe_output(self):
        return None


def conformance():
    result = None
    for trace in select_covering_traces(build_explorer().explore().traces):
        adapter = Native()
        try:
            result = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                  rules=(projected_state_matches(), projected_output_matches()))
        finally:
            shutil.rmtree(getattr(adapter, 'root', ''), ignore_errors=True)
        if not result.ok:
            return result
    return result
