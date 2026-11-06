"""Installed skill byte checks detect a changed copy."""
from __future__ import annotations
from dataclasses import dataclass, replace
from pathlib import Path
import copy, importlib.util, io, shutil, sys, tempfile
from contextlib import redirect_stdout
ROOT = Path(__file__).resolve().parents[2]

@dataclass(frozen=True)
class Event:
    changed: bool = False

@dataclass(frozen=True)
class State:
    changed: bool = False
    installed: int = 0
    initial_check: int = 0
    checked: int = 0

class Step:

    def check(self, event):
        return int(event.changed)

    def expected(self, event, state):
        result = State(event.changed, 0, 0, self.check(event))
        return (result.checked, result)

class ChangedCopyIgnored(Step):

    def check(self, event):
        return 0

def _check(state):
    return False if state.installed != 0 or state.initial_check != 0 or state.checked != int(state.changed) else True
EVENTS = (Event(False), Event(True))

class Native:

    def reset(self, state):
        self.state = state
        self.folder = Path(tempfile.mkdtemp(prefix='lw-install-contract-'))

    def observe(self, event):
        spec = importlib.util.spec_from_file_location('lw_native_installer', ROOT / 'scripts/install_skill.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        previous = sys.argv

        def invoke(check=False):
            sys.argv = ['install_skill.py', '--target', str(self.folder)] + (['--check'] if check else [])
            with redirect_stdout(io.StringIO()):
                return module.main()
        try:
            installed = invoke()
            initial = invoke(True)
            if event.changed:
                path = self.folder / 'logic-writing/SKILL.md'
                data = path.read_bytes()
                path.write_bytes(bytes([data[0] ^ 1]) + data[1:])
            checked = invoke(True)
        finally:
            sys.argv = previous
        self.state = State(event.changed, installed, initial, checked)
        return (checked, self.state)

    def close(self):
        shutil.rmtree(self.folder, ignore_errors=True)
RULES = {'check_fails_on_a_changed_copy': _check}
INITIAL_CASES = (State(),)
INPUT_CASES = EVENTS
CALCULATE = Step().expected
BAD_EXPECTATIONS = {'check_ignores_a_changed_copy': ChangedCopyIgnored().expected}
