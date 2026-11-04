"""Sibling planned units appear in the text in plan order; the deterministic audit sends a swapped pair to repair and hands that result to reader_artifact."""
from __future__ import annotations
from dataclasses import dataclass, replace
from .reader_cases import _RealReaderChain

@dataclass(frozen=True)
class Event:
    kind: str
    quality: str = ''
OUTPUTS = {'order_audit': ('passed', 'plan_order_mismatch')}

@dataclass(frozen=True)
class State:
    order_case: str = ''
    order_audit: str = ''

class Step:

    def order_audit_for(self, case: str) -> str:
        return 'plan_order_mismatch' if case == 'swapped' else 'passed'

    def expected(self, event, state):
        result = self.order_audit_for(event.quality)
        return ('audited', replace(state, order_case=event.quality, order_audit=result))

class SwappedSectionsPass(Step):
    """Known-bad: the audit never compares the text order with the plan order."""

    def order_audit_for(self, case: str) -> str:
        return 'passed'

def _text_follows_plan_order(state: State):
    if state.order_case == 'swapped' and state.order_audit != 'plan_order_mismatch':
        return False
    return True
CASES = ('in_order', 'swapped')
EVENTS = tuple((Event('order', case) for case in CASES))
RULES = {'text_follows_plan_order': _text_follows_plan_order}
INITIAL_CASES = (State(),)
INPUT_CASES = EVENTS
CALCULATE = Step().expected
BAD_EXPECTATIONS = {'swapped_sections_pass': SwappedSectionsPass().expected}
