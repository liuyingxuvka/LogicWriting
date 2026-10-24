"""Fiction tree: the composition plan owns unit identity, and domain surfaces only refer to it.

Each case is one input to the real fiction checks of the shipped long-form
project: the novel ledger as shipped, a ledger unit the plan does not have, a
ledger row repeating a field the plan owns, a world claim read from a saved
WorldGuard report or written by hand, and long-form closure over the complete
project or after its ledger is emptied.
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

MODEL_ID = "fiction_tree"
PARENT = "fiction-model"
COMPONENTS = ["fiction-model"]
IMPLEMENTED_BY = {
    "LongformClosure": "skills/logic-writing/routes/fiction/scripts/longform_closure_check.py:validate",
    "StoryLedger": "skills/logic-writing/routes/fiction/scripts/story_ledger_check.py:validate_ledger",
    "WorldStatus": "skills/logic-writing/routes/fiction/scripts/story_ledger_check.py:read_worldguard_status",
    "ArcsThreads": "skills/logic-writing/routes/fiction/scripts/novel_ledger_check.py:validate_arcs_threads",
    "ProjectSurface": "skills/logic-writing/routes/fiction/scripts/fiction_plan.py:project_surface",
}
TESTED_BY = {
    "ledger_units_are_planned_units": ["tests/unit/test_fiction.py:test_ledger_unit_must_be_a_planned_unit"],
    "unit_fields_live_only_in_the_plan": [
        "tests/unit/test_fiction.py:test_unit_fields_live_only_in_the_plan",
        "tests/unit/test_fiction.py:test_unit_plans_take_shared_fields_from_the_planned_units"],
    "world_status_comes_from_native_reports": ["tests/unit/test_fiction.py:test_worldguard_status_comes_from_native_reports"],
    "emptied_ledger_fails_longform_closure": [
        "tests/unit/test_fiction.py:test_emptied_ledger_fails_longform_closure",
        "tests/unit/test_fiction.py:test_longform_binding_negative_cannot_pass_from_input_failure"],
}
NOT_MODELED = {
    "skills/logic-writing/routes/fiction/scripts/chapter_interface_check.py:Reporter.error": "Collects findings in memory for the report this check prints; the pass or fail decision is made in its validate function.",
    "skills/logic-writing/routes/fiction/scripts/longform_closure_check.py:Reporter.error": "Collects findings in memory for the report this check prints; the pass or fail decision is made in its validate function.",
    "skills/logic-writing/routes/fiction/scripts/novel_ledger_check.py:Reporter.issue": "Collects findings in memory for the report this check prints; the pass or fail decision is made in its validate function.",
    "skills/logic-writing/routes/fiction/scripts/promise_payoff_check.py:Reporter.issue": "Collects findings in memory for the report this check prints; the pass or fail decision is made in its validate function.",
    "skills/logic-writing/routes/fiction/scripts/scene_contract_check.py:Reporter.issue": "Collects findings in memory for the report this check prints; the pass or fail decision is made in its validate function.",
    "skills/logic-writing/routes/fiction/scripts/story_contribution_check.py:Reporter.error": "Collects findings in memory for the report this check prints; the pass or fail decision is made in its validate function.",
    "skills/logic-writing/routes/fiction/scripts/story_contribution_check.py:Reporter.warning": "Collects findings in memory for the report this check prints; the pass or fail decision is made in its validate function.",
    "skills/logic-writing/routes/fiction/scripts/story_ledger_check.py:Reporter.issue": "Collects findings in memory for the report this check prints; the pass or fail decision is made in its validate function.",
    "skills/logic-writing/routes/fiction/scripts/storyline_project_mesh_check.py:Reporter.error": "Collects findings in memory for the report this check prints; the pass or fail decision is made in its validate function.",
    "skills/logic-writing/routes/fiction/scripts/turning_point_check.py:Reporter.issue": "Collects findings in memory for the report this check prints; the pass or fail decision is made in its validate function.",
    "skills/logic-writing/routes/fiction/scripts/voice_style_continuity_check.py:Reporter.error": "Collects findings in memory for the report this check prints; the pass or fail decision is made in its validate function.",
    "skills/logic-writing/routes/fiction/scripts/chapter_interface_check.py:main": "Command wrapper that reads one JSON file, calls this script's validate function and prints its report.",
    "skills/logic-writing/routes/fiction/scripts/longform_closure_check.py:main": "Command wrapper that reads one JSON file, calls this script's validate function and prints its report.",
    "skills/logic-writing/routes/fiction/scripts/novel_ledger_check.py:main": "Command wrapper that reads one JSON file, calls this script's validate function and prints its report.",
    "skills/logic-writing/routes/fiction/scripts/promise_payoff_check.py:main": "Command wrapper that reads one JSON file, calls this script's validate function and prints its report.",
    "skills/logic-writing/routes/fiction/scripts/scene_contract_check.py:main": "Command wrapper that reads one JSON file, calls this script's validate function and prints its report.",
    "skills/logic-writing/routes/fiction/scripts/story_contribution_check.py:main": "Command wrapper that reads one JSON file, calls this script's validate function and prints its report.",
    "skills/logic-writing/routes/fiction/scripts/story_ledger_check.py:main": "Command wrapper that reads one JSON file, calls this script's validate function and prints its report.",
    "skills/logic-writing/routes/fiction/scripts/storyline_project_mesh_check.py:main": "Developer command that runs the declared native fiction validators as subprocesses and prints one project report.",
    "skills/logic-writing/routes/fiction/scripts/storyline_route_check.py:main": "Command wrapper that reads one JSON file, calls this script's validate function and prints its report.",
    "skills/logic-writing/routes/fiction/scripts/turning_point_check.py:main": "Command wrapper that reads one JSON file, calls this script's validate function and prints its report.",
    "skills/logic-writing/routes/fiction/scripts/voice_style_continuity_check.py:main": "Command wrapper that reads one JSON file, calls this script's validate function and prints its report.",
    "skills/logic-writing/routes/fiction/scripts/storyline_route_check.py:compile_route_decision": "Compiles a storyline route decision record for the fiction regression cases; it decides no closure and the fiction regression replays it.",
}

ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "skills" / "logic-writing" / "routes" / "fiction"
CASES = {
    "planned_ledger_unit": "accepted",
    "unplanned_ledger_unit": "unit_not_in_plan",
    "ledger_repeats_plan_field": "retired_unit_field",
    "world_status_from_report": "pass",
    "handwritten_world_status": "worldguard_status_without_report",
    "complete_project": "passed",
    "emptied_ledger": "needs_repair",
}


@dataclass(frozen=True)
class Event:
    case: str


@dataclass(frozen=True)
class State:
    case: str = ""
    result: str = ""


class Check:
    """Intended behavior: every fiction case gets the result in CASES."""

    name = "Check"
    reads = ("case",)
    writes = ("case", "result")

    def result_for(self, case: str) -> str:
        return CASES[case]

    def apply(self, event: Event, state: State):
        result = self.result_for(event.case)
        return (FunctionResult(result, replace(state, case=event.case, result=result), label=f"{event.case}:{result}"),)


class AcceptsUnplannedUnit(Check):
    """Known-bad: a ledger unit outside the plan is accepted."""

    def result_for(self, case):
        return "accepted" if case == "unplanned_ledger_unit" else super().result_for(case)


class LedgerRepeatsPlanFields(Check):
    """Known-bad: a ledger row may restate a field the plan owns."""

    def result_for(self, case):
        return "accepted" if case == "ledger_repeats_plan_field" else super().result_for(case)


class HandwrittenWorldStatusPasses(Check):
    """Known-bad: a handwritten world status counts as a pass."""

    def result_for(self, case):
        return "pass" if case == "handwritten_world_status" else super().result_for(case)


class EmptyLedgerPasses(Check):
    """Known-bad: long-form closure passes after its ledger is emptied."""

    def result_for(self, case):
        return "passed" if case == "emptied_ledger" else super().result_for(case)


def _expects(cases: dict, message: str):
    def rule(state: State, trace) -> InvariantResult:
        if state.case in cases and state.result != cases[state.case]:
            return InvariantResult.fail(message)
        return InvariantResult.pass_()
    return rule


INVARIANTS = (
    Invariant("ledger_units_are_planned_units", "every ledger unit is a planned unit of the composition plan",
              _expects({"unplanned_ledger_unit": "unit_not_in_plan", "planned_ledger_unit": "accepted"},
                       "a ledger unit outside the plan was accepted")),
    Invariant("unit_fields_live_only_in_the_plan", "unit identity and order live only in the composition plan",
              _expects({"ledger_repeats_plan_field": "retired_unit_field"}, "a ledger row restated a plan-owned field")),
    Invariant("world_status_comes_from_native_reports", "a world status is read only from a saved WorldGuard report",
              _expects({"handwritten_world_status": "worldguard_status_without_report", "world_status_from_report": "pass"},
                       "a handwritten world status replaced the native report")),
    Invariant("emptied_ledger_fails_longform_closure", "long-form closure fails when a declared surface is empty",
              _expects({"emptied_ledger": "needs_repair", "complete_project": "passed"},
                       "long-form closure passed without its ledger")),
)
EVENTS = tuple(Event(case) for case in CASES)


def _explorer(step: Check) -> Explorer:
    return Explorer(workflow=Workflow((step,)), initial_states=(State(),), external_inputs=EVENTS,
                    invariants=INVARIANTS, max_sequence_length=1, progress_steps=0)


def build_explorer() -> Explorer:
    return _explorer(Check())


def broken_variants() -> dict:
    return {"unplanned_ledger_unit_accepted": _explorer(AcceptsUnplannedUnit()),
            "ledger_repeats_plan_fields": _explorer(LedgerRepeatsPlanFields()),
            "handwritten_world_status_passes": _explorer(HandwrittenWorldStatusPasses()),
            "empty_ledger_passes": _explorer(EmptyLedgerPasses())}


class _RealFiction:
    """Runs the real fiction checks on a copy of the shipped long-form project."""

    def reset(self, state: State) -> None:
        for path in (ROOT / "skills" / "logic-writing" / "scripts", ROUTE / "scripts"):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        import longform_closure_check
        import novel_ledger_check
        import story_ledger_check
        self.longform, self.novel, self.story = longform_closure_check, novel_ledger_check, story_ledger_check
        self.folder = Path(tempfile.mkdtemp(prefix="lw-fiction-model-"))
        self.project = self.folder / "project"
        shutil.copytree(ROUTE / "examples" / "longform_novel_project", self.project)
        shutil.copyfile(ROOT / "tests" / "fixtures" / "trials" / "trialB" / "wg-v2.json", self.folder / "wg-v2.json")
        self.state = state

    def _run(self, case: str) -> str:
        ledger_path = self.project / "novel-ledger.json"
        if case in {"planned_ledger_unit", "unplanned_ledger_unit", "ledger_repeats_plan_field"}:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            if case == "unplanned_ledger_unit":
                ledger["story_units"][0]["planned_unit_id"] = "unknown-book"
            elif case == "ledger_repeats_plan_field":
                ledger["story_units"][0]["contribution"] = "Restated from the plan."
            codes = {row["code"] for row in self.novel.validate_ledger(ledger, str(ledger_path))["issues"]}
            if any(code.startswith("unit_not_in_plan:") for code in codes):
                return "unit_not_in_plan"
            return "retired_unit_field" if "retired_unit_field" in codes else "accepted"
        if case == "world_status_from_report":
            return self.story.read_worldguard_status({"worldguard_report": "wg-v2.json"}, str(self.folder / "ledger.json"))
        if case == "handwritten_world_status":
            report = self.story.validate_ledger({"worldguard_claims": [{"worldguard_status": "pass"}]},
                                                str(self.folder / "ledger.json"))
            codes = {row["code"] for row in report["issues"]}
            return "worldguard_status_without_report" if "worldguard_status_without_report" in codes else "pass"
        source = self.project / "project-mesh.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        saved = ledger_path.read_bytes()
        try:
            if case == "emptied_ledger":
                ledger_path.write_text("{}", encoding="utf-8")
            return "passed" if self.longform.validate(payload, str(source))["passed"] else "needs_repair"
        finally:
            ledger_path.write_bytes(saved)

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
    """Replay one trace per fiction case against the real fiction checks."""
    last = None
    for trace in select_covering_traces(build_explorer().explore().traces):
        adapter = _RealFiction()
        try:
            last = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                rules=(projected_state_matches(), projected_output_matches()))
        finally:
            adapter.close()
        if not last.ok:
            return last
    return last
