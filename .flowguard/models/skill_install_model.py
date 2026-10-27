"""Installed skill byte checks detect a changed copy."""
from __future__ import annotations
from dataclasses import dataclass, replace
from pathlib import Path
import copy, importlib.util, io, shutil, sys, tempfile
from contextlib import redirect_stdout
from flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace, select_covering_traces
from flowguard.conformance import projected_state_matches, projected_output_matches
from flowguard.explorer import Explorer
ROOT=Path(__file__).resolve().parents[2]
MODEL_ID='skill_install_model'
PARENT='release'
IMPLEMENTED_BY={'Install':'scripts/install_skill.py:main'}
TESTED_BY={'check_fails_on_a_changed_copy':['tests/contract/test_install_skill.py:test_check_fails_on_a_changed_copy_in_process']}
@dataclass(frozen=True)
class Event:
    changed:bool=False
@dataclass(frozen=True)
class State:
    changed:bool=False
    installed:int=0
    initial_check:int=0
    checked:int=0
class Step:
    name='Install'
    reads=()
    writes=('changed','installed','initial_check','checked')
    def check(self,event):return int(event.changed)
    def apply(self,event,state):
        result=State(event.changed,0,0,self.check(event))
        return (FunctionResult(result.checked,result,label='install_check'),)
class ChangedCopyIgnored(Step):
    def check(self,event):return 0
def _check(state,trace):
    return InvariantResult.fail('installed bytes did not control check exit') if state.installed!=0 or state.initial_check!=0 or state.checked!=int(state.changed) else InvariantResult.pass_()
INVARIANTS=(Invariant('check_fails_on_a_changed_copy','one changed installed byte fails check',_check),)
EVENTS=(Event(False),Event(True))
class Native:
    def reset(self,state):
        self.state=state;self.folder=Path(tempfile.mkdtemp(prefix='lw-install-model-'))
    def apply_step(self,step):
        spec=importlib.util.spec_from_file_location('lw_native_installer',ROOT/'scripts/install_skill.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        previous=sys.argv
        def invoke(check=False):
            sys.argv=['install_skill.py','--target',str(self.folder)]+(['--check'] if check else [])
            with redirect_stdout(io.StringIO()):return module.main()
        try:
            installed=invoke();initial=invoke(True)
            if step.function_input.changed:
                path=self.folder/'logic-writing/SKILL.md';data=path.read_bytes();path.write_bytes(bytes([data[0]^1])+data[1:])
            checked=invoke(True)
        finally:sys.argv=previous
        self.state=State(step.function_input.changed,installed,initial,checked)
        return ReplayObservation(function_name=step.function_name,observed_output=checked,observed_state=self.state)
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
def broken_variants():return {'check_ignores_a_changed_copy':_explorer(ChangedCopyIgnored())}

NOT_MODELED = {'scripts/check_privacy.py:main': 'Release maintenance command covered by tests/contract/test_privacy_scan.py.', 'scripts/check_public_docs.py:main': 'Release maintenance command covered by tests/contract/test_release_wrappers.py.', 'scripts/run_fiction_regression.py:main': 'Release maintenance command that runs the fiction regressions in CI; covered by tests/unit/test_fiction.py.', 'scripts/run_travel_regression.py:main': 'Release maintenance command that runs the travel regressions in CI.', 'scripts/validate_skill.py:main': 'Release maintenance command covered by tests/contract/test_install_skill.py.'}
