"""Preflight the one canonical installed native provider path."""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'skills' / 'logic-writing' / 'scripts'
MEMBERS = ('sourceguard', 'logicguard', 'traceguard', 'researchguard')
MEMBER_COMMANDS = {'sourceguard': 'source', 'logicguard': 'logic', 'traceguard': 'trace', 'researchguard': 'status'}
SCOPE_OUT = ('experimentguard',)
PATH_CONSOLES = ('current', 'old', 'absent')

@dataclass(frozen=True)
class Event:
    kind: str
    provider: str = ''
    provider_root: bool = False
    path_console: str = ''

@dataclass(frozen=True)
class State:
    provider: str = ''
    provider_root: bool = False
    provider_status: str = ''
    console: str = ''
    member_command: str = ''
    path_console: str = ''
    console_source: str = ''
    install_hint: bool = False

class Step:

    def member_command(self, event: Event) -> str:
        return MEMBER_COMMANDS.get(event.provider, '')

    def provider_result(self, event: Event) -> tuple[str, str]:
        if event.provider in SCOPE_OUT:
            return ('blocked', '')
        return ('blocked', 'researchguard')

    def path_result(self, event: Event) -> tuple[str, str, bool]:
        """Status, console source and install hint when ResearchGuard is reachable only through PATH."""
        if event.path_console == 'current':
            return ('current_pass', 'path', False)
        if event.path_console == 'old':
            return ('blocked', 'path', True)
        return ('provider_unavailable', '', True)

    def expected(self, event: Event, state: State):
        if event.path_console:
            (status, source, hint), console = (self.path_result(event), 'researchguard')
        else:
            (status, console), source, hint = (self.provider_result(event), '', False)
        new = replace(state, provider=event.provider, provider_root=event.provider_root, provider_status=status, console=console, member_command=self.member_command(event), path_console=event.path_console, console_source=source, install_hint=hint)
        return (status, new)

class StatusUsesLogic(Step):
    """Known-bad: the question-status provider is sent to a semantic member."""

    def member_command(self, event: Event) -> str:
        return 'logic' if event.provider == 'researchguard' else super().member_command(event)

class ProviderRootAccepted(Step):
    """Known-bad: a provider-root override becomes a second way to run a member."""

    def provider_result(self, event: Event) -> tuple[str, str]:
        if event.provider in SCOPE_OUT:
            return ('blocked', '')
        return ('current_pass', 'provider-root') if event.provider_root else ('blocked', 'researchguard')

class PathConsoleIgnored(Step):
    """Known-bad (before LW-42): ResearchGuard installed in another Python is never found on PATH."""

    def path_result(self, event: Event) -> tuple[str, str, bool]:
        return ('provider_unavailable', '', True)

class OldPathConsoleAccepted(Step):
    """Known-bad: the version of a console found on PATH is not checked against the minimum."""

    def path_result(self, event: Event) -> tuple[str, str, bool]:
        return ('current_pass', 'path', False) if event.path_console == 'old' else super().path_result(event)

def _researchguard_status_is_primary(state: State):
    if state.provider == 'researchguard' and state.member_command != 'status':
        return False
    return True

def _members_use_one_console(state: State):
    if state.provider in MEMBERS and state.console != 'researchguard':
        return False
    return True

def _no_alternate_provider_path(state: State):
    if (state.provider_root or state.provider in SCOPE_OUT) and state.provider_status != 'blocked':
        return False
    return True

def _path_console_is_used(state: State):
    if state.path_console == 'current' and (state.provider_status != 'current_pass' or state.console_source != 'path'):
        return False
    return True

def _path_console_meets_minimum(state: State):
    if state.path_console in {'old', 'absent'} and (state.provider_status == 'current_pass' or not state.install_hint):
        return False
    return True
EVENTS = tuple((Event('handoff', provider=member, provider_root=True) for member in MEMBERS)) + tuple((Event('handoff', provider=provider) for provider in SCOPE_OUT)) + tuple((Event('handoff', provider=member, path_console=case) for member in MEMBERS for case in PATH_CONSOLES))
FAKE_CONSOLE = 'import sys\nargs = sys.argv[1:]\nif args == ["--version"]:\n    print("researchguard {version}")\nelif len(args) == 2 and args[0] in ("source", "logic", "trace", "status") and args[1] == "--help":\n    print("usage: researchguard " + args[0])\nelse:\n    sys.exit(2)\n'

class _PathConsoles:
    """Runs the real preflight command where only a fake `researchguard` is on PATH (each case once per fixture)."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix='lw-path-console-'))
        self.results: dict[tuple[str, str], dict] = {}

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _bin(self, case: str) -> Path:
        from _common import RESEARCHGUARD_MIN_VERSION
        major, minor, patch = RESEARCHGUARD_MIN_VERSION
        below = (major, minor, patch - 1) if patch else (major, minor - 1, 99) if minor else (major - 1, 99, 99)
        folder = self.root / case
        folder.mkdir(exist_ok=True)
        if case != 'absent':
            fake = folder / 'fake_researchguard.py'
            version = '.'.join(map(str, RESEARCHGUARD_MIN_VERSION if case == 'current' else below))
            fake.write_text(FAKE_CONSOLE.format(version=version), encoding='utf-8')
            if os.name == 'nt':
                (folder / 'researchguard.cmd').write_text(f'@"{sys.executable}" -S "{fake}" %*\r\n', encoding='utf-8')
            else:
                launcher = folder / 'researchguard'
                launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" -S "{fake}" "$@"\n', encoding='utf-8')
                launcher.chmod(493)
        return folder

    def preflight(self, provider: str, case: str) -> dict:
        if (provider, case) not in self.results:
            completed = subprocess.run([sys.executable, '-B', '-E', '-S', str(SCRIPTS / 'provider_preflight.py'), provider], env={**os.environ, 'PATH': str(self._bin(case))}, capture_output=True, text=True, timeout=120)
            self.results[provider, case] = json.loads(completed.stdout)
        return self.results[provider, case]

class _RealRouting:

    def __init__(self, consoles: _PathConsoles) -> None:
        self.consoles = consoles

    def reset(self, initial_state: State) -> None:
        for path in (ROOT, ROOT / 'skills' / 'logic-writing' / 'scripts'):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        import provider_preflight
        self.preflight = provider_preflight.preflight
        self.root = Path(tempfile.mkdtemp(prefix='lw-route-contract-'))
        self.state = initial_state

    def observe(self, event):
        event, state = (event, self.state)
        if event.path_console:
            result = self.consoles.preflight(event.provider, event.path_console)
        else:
            result = self.preflight(event.provider, provider_root=str(self.root) if event.provider_root else None)
        evidence, output = (result['evidence'], result['status'])
        state = replace(state, provider=event.provider, provider_root=event.provider_root, provider_status=output, console=str(evidence.get('provider_console_id', '')), member_command=str(evidence.get('member_command', '')), path_console=event.path_console, console_source=str(evidence.get('console_source', '')), install_hint=bool(evidence.get('message')))
        self.state = state
        return (output, state)

    def close(self) -> None:
        shutil.rmtree(getattr(self, 'root', ''), ignore_errors=True)
RULES = {'researchguard_status_is_primary': _researchguard_status_is_primary, 'members_use_one_console': _members_use_one_console, 'no_alternate_provider_path': _no_alternate_provider_path, 'path_console_is_used': _path_console_is_used, 'path_console_meets_minimum': _path_console_meets_minimum}
INITIAL_CASES = (State(),)
INPUT_CASES = EVENTS
CALCULATE = Step().expected
BAD_EXPECTATIONS = {'researchguard_status_uses_logic': StatusUsesLogic().expected, 'provider_root_accepted': ProviderRootAccepted().expected, 'path_console_ignored': PathConsoleIgnored().expected, 'old_path_console_accepted': OldPathConsoleAccepted().expected}
