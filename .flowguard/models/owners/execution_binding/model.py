"""Finite writer/judge binding model.

Runtime anchors: reader_execution.validate_execution_record and
validate_judgment_receipt.validate_judgment_receipt. Real capture files and altered
bytes are exercised by tests/contract/test_local_execution_backend.py; this is
an abstract state model, not proof that an external model ran.
"""
from dataclasses import dataclass, replace
from flowguard import FlowGuardCheckPlan, FunctionResult, Invariant, InvariantResult, Workflow, Scenario, ScenarioExpectation, OracleCheckResult
from flowguard.explorer import Explorer


@dataclass(frozen=True)
class State:
    input_current: bool = False
    artifact_current: bool = False
    capture_verified: bool = False
    independent: bool = False
    output_current: bool = False
    passed: bool = False


class Bind:
    name = "Bind"
    reads = ("input_current", "artifact_current", "capture_verified", "independent", "output_current")
    writes = reads + ("passed",)
    require_capture = True
    require_independence = True
    require_output = True

    def apply(self, event, state):
        if event == "bind_current":
            state = replace(state, input_current=True, artifact_current=True, capture_verified=False, independent=False, output_current=False, passed=False)
        elif event == "verify_capture":
            state = replace(state, capture_verified=True)
        elif event == "independent_context":
            state = replace(state, independent=True)
        elif event == "bind_output":
            state = replace(state, output_current=True)
        elif event == "edit_artifact":
            state = replace(state, artifact_current=False, capture_verified=False, output_current=False, passed=False)
        elif event == "judge":
            state = replace(state, passed=state.input_current and state.artifact_current
                            and (state.capture_verified or not self.require_capture)
                            and (state.independent or not self.require_independence)
                            and (state.output_current or not self.require_output))
        return (FunctionResult(event, state, label=event),)


class MissingCapture(Bind):
    require_capture = False


class SharedWriterContext(Bind):
    require_independence = False


class CallerSubstitutedOutput(Bind):
    require_output = False


def current_execution_only(state, trace):
    if state.passed and not (state.input_current and state.artifact_current and state.capture_verified and state.independent and state.output_current):
        return InvariantResult.fail("passed judge lacks current inputs, verified capture or independent context/output")
    return InvariantResult.pass_()


EVENTS = ("bind_current", "verify_capture", "independent_context", "bind_output", "edit_artifact", "judge")
INVARIANTS = (Invariant("current_execution_only", "Final judgment requires current bytes, real capture and separate writer/judge contexts", current_execution_only),)


READY = State(input_current=True, artifact_current=True, capture_verified=True, independent=True, output_current=True)


def build_plan(**_):
    workflow = Workflow((Bind(),))
    happy = ("bind_current", "verify_capture", "independent_context", "bind_output", "judge")
    def ends(expected):
        return lambda run: OracleCheckResult(bool(run.final_states) and all(state.passed is expected for state in run.final_states), "final pass/currentness state")
    scenarios = (
        Scenario(name="current_capture_closes", description="Verified current JSON and independent capture can pass",
                 initial_state=State(), external_input_sequence=happy, workflow=workflow, invariants=INVARIANTS,
                 expected=ScenarioExpectation(custom_checks=(ends(True),))),
        Scenario(name="artifact_edit_stales_capture", description="An edit invalidates captured judgment output",
                 initial_state=State(), external_input_sequence=happy + ("edit_artifact",), workflow=workflow,
                 invariants=INVARIANTS, expected=ScenarioExpectation(custom_checks=(ends(False),))),
    )
    # Short exhaustive boundary transitions plus exact complete lifecycles;
    # no long Cartesian replay is needed to observe these local invariants.
    return FlowGuardCheckPlan(workflow=workflow,
        initial_states=(State(), replace(READY, capture_verified=False), replace(READY, independent=False),
                        replace(READY, output_current=False), READY),
        external_inputs=EVENTS, invariants=INVARIANTS, max_sequence_length=2, scenarios=scenarios)


def broken_variants():
    variants = (("missing_capture", MissingCapture(), replace(READY, capture_verified=False)),
                ("shared_writer_context", SharedWriterContext(), replace(READY, independent=False)),
                ("caller_substituted_output", CallerSubstitutedOutput(), replace(READY, output_current=False)))
    return {name: Explorer(workflow=Workflow((step,)), initial_states=(state,), external_inputs=("judge",),
                           invariants=INVARIANTS, max_sequence_length=1, progress_steps=0)
            for name, step, state in variants}
