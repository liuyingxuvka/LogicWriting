"""The plan readback shows every planned unit with its bound text and findings the same way from every chain file, also while the plan is ahead of the text."""
from __future__ import annotations
from dataclasses import dataclass, replace
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow, replay_trace, select_covering_traces
from flowguard.conformance import projected_state_matches, projected_output_matches
from flowguard.explorer import Explorer
from _reader_chain_fixture import _RealReaderChain, NativeReport
MODEL_ID = 'plan_readback_model'
PARENT = 'reader-commands'
IMPLEMENTED_BY = {
    "ShowPlan": "skills/logic-writing/scripts/show_plan.py:main",
    "PlanView": "skills/logic-writing/scripts/show_plan.py:plan_view",
}
# RunChain: the readback fixture runs the chain through tests/v2_support.run_example_steps; the lint does not follow that branch, AnchorWatch shows it runs.
USES = {
    'CliValidate': 'skills/logic-writing/scripts/_common.py:cli_validate',
    'ValidateSharedWriting': 'skills/logic-writing/scripts/validate_shared_writing.py:validate_shared_writing',
    'RunChain': 'skills/logic-writing/scripts/run_chain.py:run_chain',
}
TESTED_BY = {
    "readback_shows_the_plan_ahead_of_the_text": [
        "tests/e2e/test_worked_examples.py:test_show_plan_reads_back_while_the_plan_is_ahead"
    ],
    "readback_shows_failing_units": [
        "tests/e2e/test_worked_examples.py:test_show_plan_shows_findings_on_the_failing_unit"
    ],
    "readback_is_the_same_from_every_chain_file": [
        "tests/e2e/test_worked_examples.py:test_show_plan_reads_back_the_same_from_every_chain_file"
    ],
}
@dataclass(frozen=True)
class Event:
    kind: str                       # review | self_review | edit | close | import | order | readback
    quality: str = ""               # review: pass | repair; import: a key of IMPORT_RELATIONS; order: in_order | swapped; readback: clean | leak

    input: str = ""

@dataclass(frozen=True)
class State:
    readback_case: str=''
    readback: str=''
    readback_input: str=''

class Step:
    name='Step'
    reads=()
    writes=('readback_case', 'readback', 'readback_input')
    def readback_for(self, case: str) -> str:
        return "ahead_shown" if case=="ahead" else "shown" if case == "leak" else "clean"
    def apply(self, event, state):
        result = self.readback_for(event.quality)
        return (
            FunctionResult(
                "read",
                replace(
                    state, readback_case=event.quality, readback=result, readback_input=event.input
                ),
                label="readback" + "_" + event.quality + "_" + event.input,
            ),
        )

class ReadbackHidesFindings(Step):
    """Known-bad: the plan readback shows the plan and text but not the checks' findings."""

    def readback_for(self, case: str) -> str:
        return "hidden" if case == "leak" else "clean"

def _readback_shows_failing_units(state: State, trace) -> InvariantResult:
    if state.readback_case == "leak" and state.readback != "shown":
        return InvariantResult.fail("a unit failing its audit reads back without the finding")
    return InvariantResult.pass_()

def readback_shows_the_plan_ahead_of_the_text(state,trace):
    if state.readback_case=='ahead' and state.readback!='ahead_shown':
        return InvariantResult.fail('blocked binding hides the plan ahead of the current text')
    return InvariantResult.pass_()

class BlockedChainHidesThePlan(Step):
    def readback_for(self,case):return 'hidden' if case=='ahead' else super().readback_for(case)

def readback_is_the_same_from_every_chain_file(state, trace):
    if state.readback_input and state.readback != Step().readback_for(state.readback_case):
        return InvariantResult.fail(
            "a chain file reads back other bindings than the binding result"
        )
    return InvariantResult.pass_()


class PlanFileReadsBackNoBinding(Step):
    def apply(self, event, state):
        results = super().apply(event, state)
        if event.input in ("reader-brief.json", "closure-input.json"):
            return tuple(
                replace(row, new_state=replace(row.new_state, readback="unbound")) for row in results
            )
        return results


INVARIANTS = (
    Invariant(
        "readback_is_the_same_from_every_chain_file",
        "every chain file reads back the same bound units and findings as the binding result",
        readback_is_the_same_from_every_chain_file,
    ),
    Invariant(
        "readback_shows_the_plan_ahead_of_the_text",
        "planned new units remain readable while binding is blocked",
        readback_shows_the_plan_ahead_of_the_text,
    ),
    Invariant(
        "readback_shows_failing_units",
        "each failure on a unit is visible under that unit in the readback",
        _readback_shows_failing_units,
    ),
)
CASES = ('clean', 'leak', 'ahead')
INPUT_FILES = (
    "reader-brief.json",
    "closure-input.json",
    "shared-writing.json",
    "shared-writing-result.json",
)
EVENTS = tuple(Event("readback", case, name) for case in CASES for name in INPUT_FILES)
def _explorer(step):return Explorer(workflow=Workflow((step,)),initial_states=(State(),),external_inputs=EVENTS,invariants=INVARIANTS,max_sequence_length=1,progress_steps=0)
def build_explorer():return _explorer(Step())
def broken_variants():
    return {
        "plan_file_reads_back_no_binding": _explorer(PlanFileReadsBackNoBinding()),
        "blocked_chain_hides_the_plan": _explorer(BlockedChainHidesThePlan()),
        "readback_hides_findings": _explorer(ReadbackHidesFindings()),
    }
def conformance():
    count = 0
    first_failure = None
    for trace in build_explorer().explore().traces:
        if len(trace.steps) != 1:
            continue
        adapter = _RealReaderChain()
        try:
            report = replay_trace(
                trace=trace,
                adapter=adapter,
                invariants=INVARIANTS,
                rules=(projected_state_matches(), projected_output_matches()),
            )
        finally:
            adapter.close()
        # A failing early readback must not hide the remaining cases' native bindings.
        if not report.ok and first_failure is None:
            first_failure = report
        count += 1
    return first_failure if first_failure is not None else NativeReport(count, [])
