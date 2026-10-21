"""Executable model: one final owner per request, and specialists only through their own path.

A request names its terminal deliverable. Logic Writing selects exactly one of
the four final owners from that deliverable; a needed evidence search becomes a
bounded `investigation` child of academic, fiction or travel work; a trivial
request is skipped, an unknown one is ambiguous, and a material ReaderIntent
conflict blocks. LogicGuard, SourceGuard and TraceGuard run only through the
single `researchguard` console: a provider-root override is refused, and
ExperimentGuard and the ResearchGuard umbrella are out of scope.

Conformance replays model traces on the real `select_route` and on the real
`provider_preflight.preflight` (the branches that need no installed provider).
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from flowguard import (FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace,
                       select_covering_traces)
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer

MODEL_ID = "route_and_guard_model"
COMPONENTS = ["routing", "providers"]
IMPLEMENTED_BY = {
    "SelectRoute": "skills/logic-writing/scripts/select_route.py:select_route",
    "ProviderPreflight": "skills/logic-writing/scripts/provider_preflight.py:preflight",
}
TESTED_BY = {
    "exactly_one_final_owner": [
        "tests/unit/test_routing.py:test_terminal_deliverable_selects_exactly_one_owner",
        "tests/unit/test_routing.py:test_ambiguous_deliverable_blocks_without_guessing_owner",
    ],
    "owner_follows_the_terminal_deliverable": [
        "tests/unit/test_routing.py:test_terminal_deliverable_selects_exactly_one_owner",
        "tests/unit/test_routing.py:test_material_reader_intent_conflict_blocks_drafting",
    ],
    "bounded_research_is_a_child": [
        "tests/unit/test_routing.py:test_bounded_research_is_child_not_final_owner",
    ],
    "members_use_one_console": [
        "tests/unit/test_researchguard_provider_topology.py:test_each_member_uses_one_researchguard_console",
        "tests/unit/test_researchguard_provider_topology.py:test_console_on_path_is_used_when_researchguard_is_in_another_python",
    ],
    "no_alternate_provider_path": [
        "tests/unit/test_researchguard_provider_topology.py:test_member_provider_root_is_rejected_before_console_execution",
        "tests/unit/test_researchguard_provider_topology.py:test_scope_out_provider_runs_no_console",
        "tests/unit/test_researchguard_provider_topology.py:test_umbrella_scope_out_provider_runs_no_console",
    ],
}

ROOT = Path(__file__).resolve().parents[2]
FINAL_OWNERS = ("investigation", "academic-writing", "fiction-writing", "travel-guide")
OWNER_OF = {
    "research_report": "investigation",
    "paper": "academic-writing",
    "short_story": "fiction-writing",
    "itinerary": "travel-guide",
}
TRIVIAL = ("grammar_only",)
UNKNOWN = ("unresolved",)
MEMBERS = ("sourceguard", "logicguard", "traceguard")
SCOPE_OUT = ("experimentguard", "researchguard")


@dataclass(frozen=True)
class Event:
    kind: str                       # request | handoff
    deliverable: str = ""           # request: terminal deliverable kind
    research: bool = False          # request: substantial research is needed
    conflict: bool = False          # request: a material ReaderIntent conflict exists
    provider: str = ""              # handoff: provider id
    provider_root: bool = False     # handoff: the caller passes a provider-root override


@dataclass(frozen=True)
class State:
    deliverable: str = ""
    conflict: bool = False
    status: str = ""                # "" | current | skipped | ambiguous | blocked
    owner: str = ""
    children: tuple[str, ...] = ()
    provider: str = ""
    provider_root: bool = False
    provider_status: str = ""       # status of the last preflight
    console: str = ""               # console the last preflight would use


class Step:
    """Intended routing and specialist preflight behavior."""

    name = "Step"
    reads = ("status",)
    writes = ("deliverable", "conflict", "status", "owner", "children", "provider", "provider_root",
              "provider_status", "console")

    def owner_for(self, event: Event) -> str:
        return OWNER_OF.get(event.deliverable, "")

    def provider_result(self, event: Event) -> tuple[str, str]:
        if event.provider in SCOPE_OUT:
            return "blocked", ""
        return "blocked", "researchguard"       # members: the override is refused before any console runs

    def apply(self, event: Event, state: State):
        if event.kind == "request":
            if state.status:
                return (FunctionResult("already_routed", state, label="request_ignored"),)
            owner = self.owner_for(event)
            if event.conflict:
                status, owner = "blocked", ""
            elif event.deliverable in TRIVIAL:
                status, owner = "skipped", ""
            elif owner:
                status = "current"
            else:
                status = "ambiguous"
            children = ("investigation",) if status == "current" and event.research and owner != "investigation" else ()
            new = replace(state, deliverable=event.deliverable, conflict=event.conflict, status=status,
                          owner=owner, children=children)
            return (FunctionResult(f"{status}:{owner}", new, label=f"route_{status}"),)
        status, console = self.provider_result(event)
        new = replace(state, provider=event.provider, provider_root=event.provider_root,
                      provider_status=status, console=console)
        return (FunctionResult(status, new, label=f"preflight_{status}"),)


class ResearchChildTakesOwnership(Step):
    """Known-bad: a request that needs research is handed to investigation as final owner."""

    def owner_for(self, event: Event) -> str:
        return "investigation" if event.research and event.deliverable in OWNER_OF else OWNER_OF.get(event.deliverable, "")


class ProviderRootAccepted(Step):
    """Known-bad: a provider-root override becomes a second way to run a member."""

    def provider_result(self, event: Event) -> tuple[str, str]:
        if event.provider in SCOPE_OUT:
            return "blocked", ""
        return ("current_pass", "provider-root") if event.provider_root else ("blocked", "researchguard")


def _exactly_one_final_owner(state: State, trace) -> InvariantResult:
    if state.status == "current" and (state.owner not in FINAL_OWNERS or state.owner in state.children):
        return InvariantResult.fail("a current route lacks exactly one final owner")
    if state.status in {"skipped", "ambiguous", "blocked"} and state.owner:
        return InvariantResult.fail("a skipped, ambiguous or blocked request still names an owner")
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


def _members_use_one_console(state: State, trace) -> InvariantResult:
    if state.provider in MEMBERS and state.console != "researchguard":
        return InvariantResult.fail("a ResearchGuard member was routed to a console other than researchguard")
    return InvariantResult.pass_()


def _no_alternate_provider_path(state: State, trace) -> InvariantResult:
    if (state.provider_root or state.provider in SCOPE_OUT) and state.provider_status != "blocked":
        return InvariantResult.fail("a provider-root override or an out-of-scope provider was allowed to run")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant("exactly_one_final_owner", "one request has exactly one final owner, or none", _exactly_one_final_owner),
    Invariant("owner_follows_the_terminal_deliverable", "the owner comes from the terminal deliverable",
              _owner_follows_the_terminal_deliverable),
    Invariant("bounded_research_is_a_child", "research is a bounded investigation child", _bounded_research_is_a_child),
    Invariant("members_use_one_console", "LogicGuard, SourceGuard and TraceGuard use the researchguard console",
              _members_use_one_console),
    Invariant("no_alternate_provider_path", "no provider-root override and no out-of-scope provider runs",
              _no_alternate_provider_path),
)
EVENTS = (
    tuple(Event("request", deliverable=kind, research=research)
          for kind in (*OWNER_OF, *TRIVIAL, *UNKNOWN) for research in (False, True))
    + (Event("request", deliverable="paper", conflict=True),)
    + tuple(Event("handoff", provider=member, provider_root=True) for member in MEMBERS)
    + tuple(Event("handoff", provider=provider) for provider in SCOPE_OUT)
)


def _explorer(step: Step) -> Explorer:
    return Explorer(workflow=Workflow((step,)), initial_states=(State(),), external_inputs=EVENTS,
                    invariants=INVARIANTS, max_sequence_length=2, progress_steps=0)


def build_explorer() -> Explorer:
    return _explorer(Step())


def broken_variants() -> dict:
    return {"research_child_takes_ownership": _explorer(ResearchChildTakesOwnership()),
            "provider_root_accepted": _explorer(ProviderRootAccepted())}


class _RealRouting:
    """Calls the real select_route and provider preflight; no provider is executed."""

    def reset(self, initial_state: State) -> None:
        for path in (ROOT, ROOT / "skills" / "logic-writing" / "scripts"):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        import provider_preflight
        from select_route import select_route
        from tests.v2_support import route_request
        self.preflight, self.select_route, self.route_request = provider_preflight.preflight, select_route, route_request
        self.root = Path(tempfile.mkdtemp(prefix="lw-route-model-"))
        self.state = initial_state

    def close(self) -> None:
        shutil.rmtree(getattr(self, "root", ""), ignore_errors=True)

    def apply_step(self, step) -> ReplayObservation:
        event = step.function_input
        state = self.state
        if event.kind == "request":
            if state.status:
                output = "already_routed"
            else:
                request = self.route_request(event.deliverable, research=event.research)
                if event.conflict:
                    request["intent_conflicts"] = [{
                        "conflict_id": "conflict:structure", "fields": ["structure"],
                        "reason": "Two incompatible fixed outlines were supplied.", "material": True,
                    }]
                decision = self.select_route(request)
                owner = decision["final_owner"] or ""
                state = replace(state, deliverable=event.deliverable, conflict=event.conflict,
                                status=decision["status"], owner=owner, children=tuple(decision["child_routes"]))
                output = f"{decision['status']}:{owner}"
        else:
            result = self.preflight(event.provider, provider_root=str(self.root) if event.provider_root else None)
            output = result["status"]
            state = replace(state, provider=event.provider, provider_root=event.provider_root,
                            provider_status=output, console=str(result["evidence"].get("provider_console_id", "")))
        self.state = state
        return ReplayObservation(function_name=step.function_name, observed_output=output, observed_state=state)

    def observe_state(self) -> State:
        return self.state

    def observe_output(self):
        return None


def conformance():
    """Replay traces covering every modeled transition against the real routing and preflight code."""
    last = None
    for trace in select_covering_traces(build_explorer().explore().traces):
        adapter = _RealRouting()
        try:
            last = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                rules=(projected_state_matches(), projected_output_matches()))
        finally:
            adapter.close()
        if not last.ok:
            return last
    return last
