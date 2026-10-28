"""Trip feasibility: the trip plan's own rules decide what a travel guide may claim.

Each case is one real trip-plan input from the travel examples: the base plan, a
handwritten world status, a requested claim above the saved evidence, a current
near-future plan with a passing or a failing saved WorldGuard report, an
unreachable fallback, and a travel composition naming known or unknown routes.
The closure model decides how closure uses the resulting claim level.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from flowguard import (FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace,
                       select_covering_traces)
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer

MODEL_ID = "trip_feasibility"
PARENT = "travel-model"
COMPONENTS = ["travel-model"]
IMPLEMENTED_BY = {
    "ReviewPlan": "skills/logic-writing/routes/travel/scripts/travel_contract.py:review_plan",
    "ClaimLevel": "skills/logic-writing/routes/travel/scripts/travel_contract.py:derive_allowed_claim_level",
    "CompositionRefs": "skills/logic-writing/routes/travel/scripts/travel_contract.py:validate_composition_refs",
}
USES = {
    'ApplyMutations': 'skills/logic-writing/routes/travel/scripts/fixture_mutation.py:apply_mutations',
}
TESTED_BY = {
    "handwritten_world_status_is_rejected": ["tests/unit/test_travel.py:test_handwritten_world_status_is_rejected"],
    "claim_level_never_exceeds_saved_evidence": [
        "tests/unit/test_travel.py:test_requested_claim_level_cannot_exceed_saved_evidence"],
    "failing_world_report_limits_the_claim": ["tests/unit/test_travel.py:test_failing_world_report_limits_the_claim_level"],
    "composition_refs_resolve_in_the_trip_plan": ["tests/unit/test_travel.py:test_composition_refs_resolve_in_the_trip_plan"],
    "fallbacks_are_reachable": ["tests/unit/test_travel.py:test_native_travel_plan_preserves_fallback_reachability"],
}
NOT_MODELED = {
    "skills/logic-writing/routes/travel/scripts/travel_contract.py:validate_plan_file": "Reads one plan file and returns the issues of review_plan, which this model replays; file-read errors become plan.file issues.",
}

ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "skills" / "logic-writing" / "routes" / "travel"
CASES = {
    "base_plan": "initial_plan",
    "handwritten_status": "rejected",
    "claim_overreach": "overreach",
    "current_passing_report": "bookable",
    "current_failing_report": "initial_plan",
    "fallback_unreachable": "unreachable",
    "composition_known_refs": "resolved",
    "composition_unknown_route": "unknown_ref",
}


@dataclass(frozen=True)
class Event:
    case: str


@dataclass(frozen=True)
class State:
    case: str = ""
    result: str = ""


class Review:
    """Intended behavior: every trip-plan case gets the result in CASES."""

    name = "Review"
    reads = ("case",)
    writes = ("case", "result")

    def result_for(self, case: str) -> str:
        return CASES[case]

    def apply(self, event: Event, state: State):
        result = self.result_for(event.case)
        return (FunctionResult(result, replace(state, case=event.case, result=result), label=f"{event.case}:{result}"),)


class AcceptsHandwrittenPass(Review):
    """Known-bad: a handwritten world status is read instead of the saved report."""

    def result_for(self, case):
        return "initial_plan" if case == "handwritten_status" else super().result_for(case)


class RaisesClaimWithoutEvidence(Review):
    """Known-bad: the requested claim level replaces the derived one."""

    def result_for(self, case):
        return "bookable" if case == "claim_overreach" else super().result_for(case)


class IgnoresFailingReport(Review):
    """Known-bad: a failing saved world report still allows booking."""

    def result_for(self, case):
        return "bookable" if case == "current_failing_report" else super().result_for(case)


class AcceptsUnknownRoute(Review):
    """Known-bad: the composition may name a route the trip plan does not have."""

    def result_for(self, case):
        return "resolved" if case == "composition_unknown_route" else super().result_for(case)


class AcceptsUnreachableFallback(Review):
    """Known-bad: a fallback no route node reaches is accepted."""

    def result_for(self, case):
        return "initial_plan" if case == "fallback_unreachable" else super().result_for(case)


def _expects(case: str, wanted: str, message: str):
    def rule(state: State, trace) -> InvariantResult:
        if state.case == case and state.result != wanted:
            return InvariantResult.fail(message)
        return InvariantResult.pass_()
    return rule


INVARIANTS = (
    Invariant("handwritten_world_status_is_rejected", "world status comes only from saved WorldGuard reports",
              _expects("handwritten_status", "rejected", "a handwritten world status was accepted")),
    Invariant("claim_level_never_exceeds_saved_evidence", "a requested claim above the derived level is an issue",
              _expects("claim_overreach", "overreach", "the requested claim level exceeded the saved evidence")),
    Invariant("failing_world_report_limits_the_claim", "a failing saved world report allows only initial planning",
              _expects("current_failing_report", "initial_plan", "a failing world report allowed a higher claim")),
    Invariant("composition_refs_resolve_in_the_trip_plan", "composition refs name routes and nodes of the trip plan",
              _expects("composition_unknown_route", "unknown_ref", "an unknown composition route was accepted")),
    Invariant("fallbacks_are_reachable", "every fallback is reachable from a route node",
              _expects("fallback_unreachable", "unreachable", "an unreachable fallback was accepted")),
)
EVENTS = tuple(Event(case) for case in CASES)


def _explorer(step: Review) -> Explorer:
    return Explorer(workflow=Workflow((step,)), initial_states=(State(),), external_inputs=EVENTS,
                    invariants=INVARIANTS, max_sequence_length=1, progress_steps=0)


def build_explorer() -> Explorer:
    return _explorer(Review())


def broken_variants() -> dict:
    return {"handwritten_pass_accepted": _explorer(AcceptsHandwrittenPass()),
            "claim_level_raised_without_evidence": _explorer(RaisesClaimWithoutEvidence()),
            "failing_world_report_ignored": _explorer(IgnoresFailingReport()),
            "unknown_composition_ref_accepted": _explorer(AcceptsUnknownRoute()),
            "unreachable_fallback_accepted": _explorer(AcceptsUnreachableFallback())}


class _RealTripPlan:
    """Runs the real trip-plan review on the shipped travel examples."""

    def reset(self, state: State) -> None:
        for path in (ROOT / "skills" / "logic-writing" / "scripts", ROUTE / "scripts"):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        import travel_contract
        from fixture_mutation import apply_mutations
        self.contract, self.mutate = travel_contract, apply_mutations
        self.folder = Path(tempfile.mkdtemp(prefix="lw-trip-model-"))
        self.state = state

    def _example(self, *parts):
        return json.loads((ROUTE.joinpath(*parts)).read_text(encoding="utf-8"))

    def _run(self, case: str) -> str:
        plan_path = ROUTE / "examples" / "good_city_couple_trip" / "plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if case.startswith("composition_"):
            assets = ROOT / "skills" / "logic-writing" / "assets" / "examples" / "travel"
            trip = json.loads((assets / "trip-plan.json").read_text(encoding="utf-8"))
            composition = json.loads((assets / "brief-request.json").read_text(encoding="utf-8"))["route_composition"]
            if case == "composition_unknown_route":
                composition["body_sections"][0]["route_refs"] = ["unknown-route"]
            issues = self.contract.validate_composition_refs(trip, composition)
            return "unknown_ref" if any(row["code"] == "travel_composition.route_ref.unknown" for row in issues) else "resolved"
        if case == "handwritten_status":
            plan["world_feasibility"]["checks"][0]["status"] = "pass"
        elif case == "claim_overreach":
            plan["trip_context"]["requested_claim_level"] = "bookable"
        elif case.startswith("current_"):
            plan = self.mutate(plan, self._example("examples", "positive_cases", "near_future_bookable.json")["mutations"])
            if case == "current_failing_report":
                failed = self.folder / "world-fail.json"
                failed.write_text(json.dumps({"status": "FAIL"}), encoding="utf-8")
                plan["world_feasibility"]["checks"][0]["worldguard_report"] = str(failed)
        elif case == "fallback_unreachable":
            plan = self.mutate(plan, self._example("examples", "failure_cases", "fallback_unreachable.json")["mutations"])
        review = self.contract.review_plan(plan, plan_path=plan_path, repository_root=ROOT)
        codes = {row["code"] for row in review["issues"]}
        if case.startswith("current_"):
            # The near-future case requests booking; the saved report decides what is allowed.
            return review["allowed_claim_level"]
        if "world_feasibility.status.retired" in codes:
            return "rejected"
        if "trip_context.requested_claim_level.overreach" in codes:
            return "overreach"
        if "fallback_options.reachability.unproven" in codes:
            return "unreachable"
        return review["allowed_claim_level"] if not codes else "invalid"

    def apply_step(self, step) -> ReplayObservation:
        case = step.function_input.case
        result = self._run(case)
        self.state = replace(self.state, case=case, result=result)
        return ReplayObservation(function_name=step.function_name, observed_output=result, observed_state=self.state)

    def observe_state(self) -> State:
        return self.state

    def observe_output(self):
        return None

    def close(self) -> None:
        shutil.rmtree(getattr(self, "folder", ""), ignore_errors=True)


def conformance():
    """Replay one trace per trip-plan case against travel_contract."""
    last = None
    for trace in select_covering_traces(build_explorer().explore().traces):
        adapter = _RealTripPlan()
        try:
            last = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                rules=(projected_state_matches(), projected_output_matches()))
        finally:
            adapter.close()
        if not last.ok:
            return last
    return last
