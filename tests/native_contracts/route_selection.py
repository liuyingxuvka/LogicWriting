"""Select one final owner with bounded research children."""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'skills' / 'logic-writing' / 'scripts'
FINAL_OWNERS = ('investigation', 'academic-writing', 'fiction-writing', 'travel-guide')
OWNER_OF = {'research_report': 'investigation', 'paper': 'academic-writing', 'short_story': 'fiction-writing', 'itinerary': 'travel-guide'}
TRIVIAL = ('grammar_only',)
UNKNOWN = ('unresolved',)

@dataclass(frozen=True)
class Event:
    kind: str
    deliverable: str = ''
    research: bool = False
    conflict: bool = False
    open_choice: bool = False

@dataclass(frozen=True)
class State:
    deliverable: str = ''
    conflict: bool = False
    open_choice: bool = False
    status: str = ''
    owner: str = ''
    children: tuple[str, ...] = ()

class Step:

    def owner_for(self, event: Event) -> str:
        return OWNER_OF.get(event.deliverable, '')

    def has_open_choice(self, event: Event) -> bool:
        return event.open_choice

    def child_routes(self, event: Event, status: str, owner: str) -> tuple[str, ...]:
        return ('investigation',) if status == 'current' and event.research and (owner != 'investigation') else ()

    def expected(self, event: Event, state: State):
        if state.status:
            return ('already_routed', state)
        owner = self.owner_for(event)
        if event.conflict:
            status, owner = ('blocked', '')
        elif event.deliverable in TRIVIAL:
            status, owner = ('skipped', '')
        elif self.has_open_choice(event):
            status, owner = ('needs_user_choice', '')
        elif owner:
            status = 'current'
        else:
            status = 'ambiguous'
        children = self.child_routes(event, status, owner)
        new = replace(state, deliverable=event.deliverable, conflict=event.conflict, open_choice=event.open_choice, status=status, owner=owner, children=children)
        return (f'{status}:{owner}', new)

class OpenChoiceIgnored(Step):
    """Known-bad: choose an owner before the user answers a material question."""

    def has_open_choice(self, event: Event) -> bool:
        return False

class ResearchChildTakesOwnership(Step):
    """Known-bad: a request that needs research is handed to investigation as final owner."""

    def owner_for(self, event: Event) -> str:
        return 'investigation' if event.research and event.deliverable in OWNER_OF else OWNER_OF.get(event.deliverable, '')

class OwnerAlsoAChild(Step):
    """Known-bad: a research request lists its final owner as its own child."""

    def child_routes(self, event: Event, status: str, owner: str) -> tuple[str, ...]:
        if status == 'current' and event.research:
            return (*super().child_routes(event, status, owner), owner)
        return ()

class ResearchChildNotBounded(Step):
    """Known-bad: a specialist replaces the bounded investigation child."""

    def child_routes(self, event: Event, status: str, owner: str) -> tuple[str, ...]:
        return ('logicguard',) if status == 'current' and event.research and (owner != 'investigation') else ()

def _open_material_choice_blocks(state: State):
    if state.open_choice and state.status == 'current':
        return False
    return True

def _exactly_one_final_owner(state: State):
    if state.status == 'current' and (state.owner not in FINAL_OWNERS or state.owner in state.children):
        return False
    if state.status in {'skipped', 'ambiguous', 'blocked', 'needs_user_choice'} and state.owner:
        return False
    return True

def _owner_follows_the_terminal_deliverable(state: State):
    if state.status == 'current' and state.owner != OWNER_OF.get(state.deliverable):
        return False
    if state.conflict and state.status != 'blocked':
        return False
    return True

def _bounded_research_is_a_child(state: State):
    if set(state.children) - {'investigation'} or (state.children and state.owner == 'investigation'):
        return False
    return True
EVENTS = tuple((Event('request', deliverable=kind, research=research) for kind in (*OWNER_OF, *TRIVIAL, *UNKNOWN) for research in (False, True))) + (Event('request', deliverable='paper', conflict=True), Event('request', deliverable='paper', open_choice=True), Event('request', deliverable='paper', conflict=True, open_choice=True), Event('request', deliverable='grammar_only', open_choice=True))

class _RealRouting:

    def reset(self, initial_state: State) -> None:
        for path in (ROOT, ROOT / 'skills' / 'logic-writing' / 'scripts'):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        from select_route import complete_request, select_route
        from tests.v2_support import route_request
        self.select_route, self.route_request, self.complete_request = (select_route, route_request, complete_request)
        self.root = Path(tempfile.mkdtemp(prefix='lw-route-contract-'))
        self.state = initial_state

    def observe(self, event):
        event, state = (event, self.state)
        if state.status:
            output = 'already_routed'
        else:
            request = self.route_request(event.deliverable, research=event.research)
            if event.conflict:
                request['intent_conflicts'] = [{'conflict_id': 'conflict:structure', 'fields': ['structure'], 'reason': 'Two incompatible fixed outlines were supplied.', 'material': True}]
            if event.open_choice:
                intent = request['writing_request']['reader_intent']
                intent['unresolved_choices'] = [{'choice_id': 'ch-lang', 'question': 'English or Chinese?', 'material': True}]
                intent.pop('intent_fingerprint')
                request['writing_request'].pop('request_fingerprint')
                self.complete_request(request)
            decision = self.select_route(request)
            owner = decision['final_owner'] or ''
            state = replace(state, deliverable=event.deliverable, conflict=event.conflict, open_choice=event.open_choice, status=decision['status'], owner=owner, children=tuple(decision['child_routes']))
            output = f"{decision['status']}:{owner}"
        self.state = state
        return (output, state)

    def close(self) -> None:
        shutil.rmtree(getattr(self, 'root', ''), ignore_errors=True)
RULES = {'open_material_choice_blocks': _open_material_choice_blocks, 'exactly_one_final_owner': _exactly_one_final_owner, 'owner_follows_the_terminal_deliverable': _owner_follows_the_terminal_deliverable, 'bounded_research_is_a_child': _bounded_research_is_a_child}
INITIAL_CASES = (State(),)
INPUT_CASES = EVENTS
CALCULATE = Step().expected
BAD_EXPECTATIONS = {'open_choice_ignored': OpenChoiceIgnored().expected, 'research_child_takes_ownership': ResearchChildTakesOwnership().expected, 'owner_also_a_child': OwnerAlsoAChild().expected, 'research_child_not_bounded': ResearchChildNotBounded().expected}
