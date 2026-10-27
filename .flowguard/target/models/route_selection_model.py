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

from flowguard import (FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace,
                       select_covering_traces)
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer

MODEL_ID = 'route_selection_model'
PARENT = 'routing'
COMPONENTS = ['routing']
IMPLEMENTED_BY = {'SelectRoute': 'skills/logic-writing/scripts/select_route.py:select_route'}
TESTED_BY = {'open_material_choice_blocks': ['tests/unit/test_routing.py:test_open_material_choice_asks_the_user_first'], 'exactly_one_final_owner': ['tests/unit/test_routing.py:test_terminal_deliverable_selects_exactly_one_owner', 'tests/unit/test_routing.py:test_ambiguous_deliverable_blocks_without_guessing_owner'], 'owner_follows_the_terminal_deliverable': ['tests/unit/test_routing.py:test_terminal_deliverable_selects_exactly_one_owner', 'tests/unit/test_routing.py:test_material_reader_intent_conflict_blocks_drafting'], 'bounded_research_is_a_child': ['tests/unit/test_routing.py:test_bounded_research_is_child_not_final_owner']}
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "logic-writing" / "scripts"
FINAL_OWNERS = ("investigation", "academic-writing", "fiction-writing", "travel-guide")
OWNER_OF = {
    "research_report": "investigation",
    "paper": "academic-writing",
    "short_story": "fiction-writing",
    "itinerary": "travel-guide",
}
TRIVIAL = ("grammar_only",)
UNKNOWN = ("unresolved",)
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
    name = "Step"
    reads = ('status',)
    writes = ('deliverable', 'conflict', 'open_choice', 'status', 'owner', 'children')
    def owner_for(self, event: Event) -> str:
            return OWNER_OF.get(event.deliverable, "")
    def has_open_choice(self, event: Event) -> bool:
            return event.open_choice
    def child_routes(self, event: Event, status: str, owner: str) -> tuple[str, ...]:
            return ("investigation",) if status == "current" and event.research and owner != "investigation" else ()
    def apply(self, event: Event, state: State):
        if state.status:
            return (FunctionResult('already_routed', state, label='request_ignored'),)
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
        return (FunctionResult(f'{status}:{owner}', new, label=f'route_{status}'),)
class OpenChoiceIgnored(Step):
    """Known-bad: choose an owner before the user answers a material question."""

    def has_open_choice(self, event: Event) -> bool:
        return False

class ResearchChildTakesOwnership(Step):
    """Known-bad: a request that needs research is handed to investigation as final owner."""

    def owner_for(self, event: Event) -> str:
        return "investigation" if event.research and event.deliverable in OWNER_OF else OWNER_OF.get(event.deliverable, "")

class OwnerAlsoAChild(Step):
    """Known-bad: a research request lists its final owner as its own child."""

    def child_routes(self, event: Event, status: str, owner: str) -> tuple[str, ...]:
        if status == "current" and event.research:
            return (*super().child_routes(event, status, owner), owner)
        return ()

class ResearchChildNotBounded(Step):
    """Known-bad: a specialist replaces the bounded investigation child."""

    def child_routes(self, event: Event, status: str, owner: str) -> tuple[str, ...]:
        return ("logicguard",) if status == "current" and event.research and owner != "investigation" else ()

def _open_material_choice_blocks(state: State, trace) -> InvariantResult:
    if state.open_choice and state.status == "current":
        return InvariantResult.fail("an open material reader choice was silently routed")
    return InvariantResult.pass_()

def _exactly_one_final_owner(state: State, trace) -> InvariantResult:
    if state.status == "current" and (state.owner not in FINAL_OWNERS or state.owner in state.children):
        return InvariantResult.fail("a current route lacks exactly one final owner")
    if state.status in {"skipped", "ambiguous", "blocked", "needs_user_choice"} and state.owner:
        return InvariantResult.fail("a non-current route still names an owner")
    return InvariantResult.pass_()

def _owner_follows_the_terminal_deliverable(state: State, trace) -> InvariantResult:
    if state.status == "current" and state.owner != OWNER_OF.get(state.deliverable):
        return InvariantResult.fail("the final owner does not follow the terminal deliverable")
    if state.conflict and state.status != "blocked":
        return InvariantResult.fail("a material ReaderIntent conflict did not block the request")
    return InvariantResult.pass_()

def _bounded_research_is_a_child(state: State, trace) -> InvariantResult:
    if set(state.children) - {"investigation"} or (state.children and state.owner == "investigation"):
        return InvariantResult.fail("research became something other than a bounded investigation child")
    return InvariantResult.pass_()

INVARIANTS = (
Invariant("open_material_choice_blocks", "a material choice stops routing until the user answers",
              _open_material_choice_blocks),
Invariant("exactly_one_final_owner", "one request has exactly one final owner, or none", _exactly_one_final_owner),
Invariant("owner_follows_the_terminal_deliverable", "the owner comes from the terminal deliverable",
              _owner_follows_the_terminal_deliverable),
Invariant("bounded_research_is_a_child", "research is a bounded investigation child", _bounded_research_is_a_child),
)
EVENTS = tuple(Event("request",deliverable=kind,research=research) for kind in (*OWNER_OF,*TRIVIAL,*UNKNOWN) for research in (False,True)) + (Event("request",deliverable="paper",conflict=True), Event("request",deliverable="paper",open_choice=True), Event("request",deliverable="paper",conflict=True,open_choice=True), Event("request",deliverable="grammar_only",open_choice=True))
def _explorer(step: Step) -> Explorer:
    return Explorer(workflow=Workflow((step,)), initial_states=(State(),), external_inputs=EVENTS,
                    invariants=INVARIANTS, max_sequence_length=2, progress_steps=0)
def build_explorer() -> Explorer:
    return _explorer(Step())
def broken_variants():
    return {'open_choice_ignored': _explorer(OpenChoiceIgnored()), 'research_child_takes_ownership': _explorer(ResearchChildTakesOwnership()), 'owner_also_a_child': _explorer(OwnerAlsoAChild()), 'research_child_not_bounded': _explorer(ResearchChildNotBounded())}
class _RealRouting:
    def reset(self, initial_state: State) -> None:
            for path in (ROOT, ROOT / "skills" / "logic-writing" / "scripts"):
                if str(path) not in sys.path:
                    sys.path.insert(0, str(path))
            from select_route import complete_request, select_route
            from tests.v2_support import route_request
            self.select_route, self.route_request, self.complete_request = select_route, route_request, complete_request
            self.root = Path(tempfile.mkdtemp(prefix="lw-route-model-"))
            self.state = initial_state
    def apply_step(self, step):
        event, state = step.function_input, self.state
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
        return ReplayObservation(function_name=step.function_name, observed_output=output, observed_state=state)
    def observe_state(self) -> State:
            return self.state
    def observe_output(self):
            return None
    def close(self) -> None:
            shutil.rmtree(getattr(self, "root", ""), ignore_errors=True)
def conformance():
    last = None
    for trace in select_covering_traces(build_explorer().explore().traces):
        adapter = _RealRouting()
        try:
            last = replay_trace(trace=trace,adapter=adapter,invariants=INVARIANTS,rules=(projected_state_matches(),projected_output_matches()))
        finally:adapter.close()
        if not last.ok:return last
    return last
