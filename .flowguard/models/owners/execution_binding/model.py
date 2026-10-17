"""Finite writer/judge binding model.

Runtime anchors: reader_execution.validate_execution_record and
validate_judgment_receipt.validate_judgment_receipt. Real capture files and altered
bytes are exercised by tests/contract/test_local_execution_backend.py; this is
an abstract state model, not proof that an external model ran.
"""
from dataclasses import dataclass, replace
from flowguard import FlowGuardCheckPlan, FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer


@dataclass(frozen=True)
class State:
    input_current: bool = False
    artifact_current: bool = False
    capture_verified: bool = False
    independent: bool = False
    passed: bool = False


class Bind:
    name = "Bind"
    reads = ("input_current", "artifact_current", "capture_verified", "independent")
    writes = reads + ("passed",)
    require_capture = True
    require_independence = True

    def apply(self, event, state):
        if event == "bind_current":
            state = replace(state, input_current=True, artifact_current=True, capture_verified=False, independent=False, passed=False)
        elif event == "verify_capture":
            state = replace(state, capture_verified=True)
        elif event == "independent_context":
            state = replace(state, independent=True)
        elif event == "edit_artifact":
            state = replace(state, artifact_current=False, capture_verified=False, passed=False)
        elif event == "judge":
            state = replace(state, passed=state.input_current and state.artifact_current
                            and (state.capture_verified or not self.require_capture)
                            and (state.independent or not self.require_independence))
        return (FunctionResult(event, state, label=event),)


class MissingCapture(Bind):
    require_capture = False


class SharedWriterContext(Bind):
    require_independence = False


def current_execution_only(state, trace):
    if state.passed and not (state.input_current and state.artifact_current and state.capture_verified and state.independent):
        return InvariantResult.fail("passed judge lacks current inputs, verified capture or independent context")
    return InvariantResult.pass_()


EVENTS = ("bind_current", "verify_capture", "independent_context", "edit_artifact", "judge")
INVARIANTS = (Invariant("current_execution_only", "Final judgment requires current bytes, real capture and separate writer/judge contexts", current_execution_only),)


def build_plan(**_):
    return FlowGuardCheckPlan(workflow=Workflow((Bind(),)), initial_states=(State(),), external_inputs=EVENTS,
                              invariants=INVARIANTS, max_sequence_length=5)


def broken_variants():
    return {name: Explorer(workflow=Workflow((step,)), initial_states=(State(),), external_inputs=EVENTS,
                          invariants=INVARIANTS, max_sequence_length=4, progress_steps=0)
            for name, step in (("missing_capture", MissingCapture()), ("shared_writer_context", SharedWriterContext()))}
