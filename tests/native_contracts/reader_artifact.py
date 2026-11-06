"""Independent functional contract: current-text quality determines closure; broad claims need an independent read.

Each final owner writes one artifact. Review builds current-byte evidence and
an explicitly classified ReaderJudgment. Current passing self-review can close
as passed but never allows a broad claim. Repair remains needs_repair, and a
material edit stales every earlier review and rejects closure.

Direct functional cases call the real reader-chain scripts in a temporary
folder; declared judge_kind does not prove who actually wrote the judgment.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from .reader_cases import _RealReaderChain
OWNERS = ('investigation', 'fiction-writing')

@dataclass(frozen=True)
class Event:
    kind: str
    quality: str = ''

@dataclass(frozen=True)
class State:
    owner: str
    reviewed: bool = False
    current: bool = False
    quality: str = ''
    independent: bool = False
    order_audit: str = ''
    closure: str = ''
    closure_owner: str = ''
    broad_claim: bool = False
    chain_native_status: str = ''
    chain_reported_status: str = ''

class Step:
    """Intended behavior of reviewing, editing and closing one written artifact."""

    def closure_result(self, state: State) -> str:
        if not (state.reviewed and state.current):
            return 'rejected'
        return 'passed' if state.quality == 'pass' and state.order_audit != 'repair' else 'needs_repair'

    def broad_claim_for(self, state: State, result: str) -> bool:
        return result == 'passed' and state.independent

    def closure_owner_for(self, state: State) -> str:
        return state.owner

    def command_status(self, quality):
        return 'passed' if quality == 'pass' else 'failed'

    def expected(self, event: Event, state: State):
        if event.kind == 'chain':
            native = 'passed' if event.quality == 'pass' else 'failed'
            return ('command', replace(state, chain_native_status=native, chain_reported_status=self.command_status(event.quality)))
        if event.kind == 'order':
            audit = {'passed': 'passed', 'plan_order_mismatch': 'repair'}[event.quality]
            return (event.quality, replace(state, order_audit=audit, closure='', closure_owner='', broad_claim=False))
        if event.kind in {'review', 'self_review'}:
            reviewed = replace(state, reviewed=True, current=True, quality=event.quality, independent=event.kind == 'review', closure='', closure_owner='', broad_claim=False)
            return ('reviewed', reviewed)
        if event.kind == 'edit':
            return ('edited', replace(state, current=False, closure='', closure_owner='', broad_claim=False))
        result = self.closure_result(state)
        return (result, replace(state, closure=result, closure_owner=self.closure_owner_for(state), broad_claim=self.broad_claim_for(state, result)))

class CloseIgnoresEdits(Step):
    """Known-bad: closure trusts a review made before the last edit."""

    def closure_result(self, state: State) -> str:
        if not state.reviewed:
            return 'rejected'
        return 'passed' if state.quality == 'pass' else 'needs_repair'

class CloseAcceptsSelfReview(Step):
    """Known-bad: a passing self-review licenses an unjustified broad claim."""

    def broad_claim_for(self, state: State, result: str) -> bool:
        return result == 'passed'

class RepairReportedAsPass(Step):
    """Known-bad: a current repair judgment is reported as passed."""

    def closure_result(self, state: State) -> str:
        return 'passed' if state.reviewed and state.current else 'rejected'

class CloseForSiblingOwner(Step):
    """Known-bad: a sibling route closes the artifact owned by another route."""

    def closure_owner_for(self, state: State) -> str:
        return OWNERS[(OWNERS.index(state.owner) + 1) % len(OWNERS)]

class ChainIgnoresFailedStep(Step):

    def command_status(self, quality):
        return 'passed'

class OrderMismatchPasses(Step):

    def closure_result(self, state):
        if not (state.reviewed and state.current):
            return 'rejected'
        return 'passed' if state.quality == 'pass' else 'needs_repair'

def _closure_requires_current_artifact(state: State):
    if state.closure == 'passed' and (not (state.reviewed and state.current)):
        return False
    return True

def _independent_reader_required(state: State):
    if state.broad_claim and (not state.independent):
        return False
    return True

def _needs_repair_never_passes(state: State):
    if state.chain_native_status == 'failed' and state.chain_reported_status == 'passed':
        return False
    if state.closure == 'passed' and (state.quality != 'pass' or state.order_audit == 'repair'):
        return False
    return True

def _closure_belongs_to_the_final_owner(state: State):
    if state.closure and state.closure_owner != state.owner:
        return False
    return True
EVENTS = (Event('review', 'pass'), Event('review', 'repair'), Event('self_review', 'pass'), Event('edit'), Event('close'), Event('order', 'passed'), Event('order', 'plan_order_mismatch'), Event('chain', 'pass'), Event('chain', 'repair'))
RULES = {'closure_requires_current_artifact': _closure_requires_current_artifact, 'independent_reader_required': _independent_reader_required, 'needs_repair_never_passes': _needs_repair_never_passes, 'closure_belongs_to_the_final_owner': _closure_belongs_to_the_final_owner}
INITIAL_CASES = tuple((State(owner) for owner in OWNERS))
INPUT_CASES = EVENTS
CALCULATE = Step().expected
BAD_EXPECTATIONS = {'close_ignores_edits': CloseIgnoresEdits().expected, 'close_accepts_self_review': CloseAcceptsSelfReview().expected, 'repair_reported_as_pass': RepairReportedAsPass().expected, 'closure_for_sibling_owner': CloseForSiblingOwner().expected, 'order_mismatch_passes': OrderMismatchPasses().expected, 'chain_ignores_failed_step': ChainIgnoresFailedStep().expected}
