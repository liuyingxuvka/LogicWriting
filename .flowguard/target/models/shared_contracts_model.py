"""Canonical schemas reject invalid records with one typed error and preserve valid bytes."""
from __future__ import annotations
from dataclasses import dataclass, replace
from pathlib import Path
import copy, importlib.util, io, shutil, sys, tempfile
from contextlib import redirect_stdout
from flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace, select_covering_traces
from flowguard.conformance import projected_state_matches, projected_output_matches
from flowguard.explorer import Explorer
ROOT=Path(__file__).resolve().parents[2]
MODEL_ID='shared_contracts_model'
PARENT='shared-contracts'
IMPLEMENTED_BY={'Validate':'skills/logic-writing/scripts/schema_validation.py:assert_schema_valid'}
TESTED_BY={'schema_violation_raises_one_error_type':['tests/contract/test_schema_runtime_gate.py:test_assertion_raises_one_contract_error_vocabulary']}
@dataclass(frozen=True)
class Event:
    valid:bool=True
@dataclass(frozen=True)
class State:
    valid:bool=True
    rejected:bool=False
    error_details:bool=True
    unchanged:bool=True
class Step:
    name='Validate'
    reads=()
    writes=('valid','rejected','error_details','unchanged')
    def rejected(self,event):return not event.valid
    def apply(self,event,state):
        result=State(event.valid,self.rejected(event),True,True)
        return (FunctionResult('rejected' if result.rejected else 'valid',result,label='schema_check'),)
class InvalidPasses(Step):
    def rejected(self,event):return False
def _schema(state,trace):
    return InvariantResult.fail('schema violation lost its error or valid input changed') if state.rejected==state.valid or not state.error_details or not state.unchanged else InvariantResult.pass_()
INVARIANTS=(Invariant('schema_violation_raises_one_error_type','invalid records raise one detailed typed error; valid input is unchanged',_schema),)
EVENTS=(Event(True),Event(False))
class Native:
    def reset(self,state):
        self.state=state;self.folder=Path(tempfile.mkdtemp(prefix='lw-schema-model-'))
    def apply_step(self,step):
        from schema_validation import assert_schema_valid,SchemaValidationError
        from tests.v2_support import complete_chain
        valid=step.function_input.valid
        record=complete_chain(self.folder/'chain')['route_decision'] if valid else {}
        before=copy.deepcopy(record);rejected=False;details=True
        try:assert_schema_valid('route-decision.schema.json',record)
        except SchemaValidationError as exc:
            rejected=True;details=exc.schema_name=='route-decision.schema.json' and bool(exc.issues)
        self.state=State(valid,rejected,details,record==before)
        return ReplayObservation(function_name=step.function_name,observed_output='rejected' if rejected else 'valid',observed_state=self.state)
    def observe_state(self):return self.state
    def observe_output(self):return None
    def close(self):shutil.rmtree(self.folder,ignore_errors=True)

def _explorer(step):
    return Explorer(workflow=Workflow((step,)),initial_states=(State(),),external_inputs=EVENTS,invariants=INVARIANTS,max_sequence_length=1,progress_steps=0)
def build_explorer():return _explorer(Step())
def conformance():
    last=None
    for path in (ROOT,ROOT/'skills/logic-writing/scripts'):
        if str(path) not in sys.path:sys.path.insert(0,str(path))
    for trace in select_covering_traces(build_explorer().explore().traces):
        adapter=Native()
        try:last=replay_trace(trace=trace,adapter=adapter,invariants=INVARIANTS,rules=(projected_state_matches(),projected_output_matches()))
        finally:adapter.close()
        if not last.ok:return last
    return last
def broken_variants():return {'invalid_record_passes_schema':_explorer(InvalidPasses())}
