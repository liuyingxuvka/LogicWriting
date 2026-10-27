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

from flowguard import (FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace,
                       select_covering_traces)
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer

MODEL_ID = 'provider_preflight_model'
PARENT = 'providers'
COMPONENTS = ['providers']
IMPLEMENTED_BY = {'ProviderPreflight': 'skills/logic-writing/scripts/provider_preflight.py:preflight'}
TESTED_BY = {'researchguard_status_is_primary': ['tests/unit/test_researchguard_provider_topology.py:test_researchguard_status_uses_one_console'], 'members_use_one_console': ['tests/unit/test_researchguard_provider_topology.py:test_each_member_uses_one_researchguard_console', 'tests/unit/test_researchguard_provider_topology.py:test_researchguard_status_uses_one_console', 'tests/unit/test_researchguard_provider_topology.py:test_console_on_path_is_used_when_researchguard_is_in_another_python'], 'no_alternate_provider_path': ['tests/unit/test_researchguard_provider_topology.py:test_member_provider_root_is_rejected_before_console_execution', 'tests/unit/test_researchguard_provider_topology.py:test_scope_out_provider_runs_no_console'], 'path_console_is_used': ['tests/unit/test_researchguard_provider_topology.py:test_console_on_path_is_used_when_researchguard_is_in_another_python'], 'path_console_meets_minimum': ['tests/unit/test_researchguard_provider_topology.py:test_too_old_console_on_path_blocks_with_the_install_message', 'tests/unit/test_researchguard_provider_topology.py:test_missing_console_blocks_without_old_module_import']}
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "logic-writing" / "scripts"
MEMBERS = ("sourceguard", "logicguard", "traceguard", "researchguard")
MEMBER_COMMANDS = {"sourceguard": "source", "logicguard": "logic", "traceguard": "trace", "researchguard": "status"}
SCOPE_OUT = ("experimentguard",)
PATH_CONSOLES = ("current", "old", "absent")
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
    name = "Step"
    reads = ()
    writes = ('provider', 'provider_root', 'provider_status', 'console', 'member_command', 'path_console', 'console_source', 'install_hint')
    def member_command(self, event: Event) -> str:
            return MEMBER_COMMANDS.get(event.provider, "")
    def provider_result(self, event: Event) -> tuple[str, str]:
            if event.provider in SCOPE_OUT:
                return "blocked", ""
            return "blocked", "researchguard"
    def path_result(self, event: Event) -> tuple[str, str, bool]:
            """Status, console source and install hint when ResearchGuard is reachable only through PATH."""
            if event.path_console == "current":
                return "current_pass", "path", False
            if event.path_console == "old":
                return "blocked", "path", True
            return "provider_unavailable", "", True
    def apply(self, event: Event, state: State):
        if event.path_console:
            (status, source, hint), console = (self.path_result(event), 'researchguard')
        else:
            (status, console), source, hint = (self.provider_result(event), '', False)
        new = replace(state, provider=event.provider, provider_root=event.provider_root, provider_status=status, console=console, member_command=self.member_command(event), path_console=event.path_console, console_source=source, install_hint=hint)
        return (FunctionResult(status, new, label=f'preflight_{status}'),)
class StatusUsesLogic(Step):
    """Known-bad: the question-status provider is sent to a semantic member."""

    def member_command(self, event: Event) -> str:
        return "logic" if event.provider == "researchguard" else super().member_command(event)

class ProviderRootAccepted(Step):
    """Known-bad: a provider-root override becomes a second way to run a member."""

    def provider_result(self, event: Event) -> tuple[str, str]:
        if event.provider in SCOPE_OUT:
            return "blocked", ""
        return ("current_pass", "provider-root") if event.provider_root else ("blocked", "researchguard")

class PathConsoleIgnored(Step):
    """Known-bad (before LW-42): ResearchGuard installed in another Python is never found on PATH."""

    def path_result(self, event: Event) -> tuple[str, str, bool]:
        return "provider_unavailable", "", True

class OldPathConsoleAccepted(Step):
    """Known-bad: the version of a console found on PATH is not checked against the minimum."""

    def path_result(self, event: Event) -> tuple[str, str, bool]:
        return ("current_pass", "path", False) if event.path_console == "old" else super().path_result(event)

def _researchguard_status_is_primary(state: State, trace) -> InvariantResult:
    if state.provider == "researchguard" and state.member_command != "status":
        return InvariantResult.fail("ResearchGuard must use its native status command")
    return InvariantResult.pass_()

def _members_use_one_console(state: State, trace) -> InvariantResult:
    if state.provider in MEMBERS and state.console != "researchguard":
        return InvariantResult.fail("a ResearchGuard member was routed to a console other than researchguard")
    return InvariantResult.pass_()

def _no_alternate_provider_path(state: State, trace) -> InvariantResult:
    if (state.provider_root or state.provider in SCOPE_OUT) and state.provider_status != "blocked":
        return InvariantResult.fail("a provider-root override or an out-of-scope provider was allowed to run")
    return InvariantResult.pass_()

def _path_console_is_used(state: State, trace) -> InvariantResult:
    if state.path_console == "current" and (state.provider_status != "current_pass" or state.console_source != "path"):
        return InvariantResult.fail("a researchguard console on PATH that meets the minimum was not used")
    return InvariantResult.pass_()

def _path_console_meets_minimum(state: State, trace) -> InvariantResult:
    if state.path_console in {"old", "absent"} and (state.provider_status == "current_pass" or not state.install_hint):
        return InvariantResult.fail("a missing or too-old researchguard console passed or gave no install command")
    return InvariantResult.pass_()

INVARIANTS = (
Invariant("researchguard_status_is_primary", "ResearchGuard question status uses its own primary console command",
              _researchguard_status_is_primary),
Invariant("members_use_one_console", "ResearchGuard status and three semantic members use one console",
              _members_use_one_console),
Invariant("no_alternate_provider_path", "no provider-root override and no out-of-scope provider runs",
              _no_alternate_provider_path),
Invariant("path_console_is_used", "ResearchGuard installed in another Python is used through PATH",
              _path_console_is_used),
Invariant("path_console_meets_minimum", "a missing or too-old console on PATH blocks and names the install command",
              _path_console_meets_minimum),
)
EVENTS = tuple(Event("handoff",provider=member,provider_root=True) for member in MEMBERS) + tuple(Event("handoff",provider=provider) for provider in SCOPE_OUT) + tuple(Event("handoff",provider=member,path_console=case) for member in MEMBERS for case in PATH_CONSOLES)
def _explorer(step: Step) -> Explorer:
    return Explorer(workflow=Workflow((step,)), initial_states=(State(),), external_inputs=EVENTS,
                    invariants=INVARIANTS, max_sequence_length=2, progress_steps=0)
def build_explorer() -> Explorer:
    return _explorer(Step())
def broken_variants():
    return {'researchguard_status_uses_logic': _explorer(StatusUsesLogic()), 'provider_root_accepted': _explorer(ProviderRootAccepted()), 'path_console_ignored': _explorer(PathConsoleIgnored()), 'old_path_console_accepted': _explorer(OldPathConsoleAccepted())}
FAKE_CONSOLE = """import sys
args = sys.argv[1:]
if args == ["--version"]:
    print("researchguard {version}")
elif len(args) == 2 and args[0] in ("source", "logic", "trace", "status") and args[1] == "--help":
    print("usage: researchguard " + args[0])
else:
    sys.exit(2)
"""
class _PathConsoles:
    """Runs the real preflight command where only a fake `researchguard` is on PATH (each case once per replay)."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="lw-path-console-"))
        self.results: dict[tuple[str, str], dict] = {}

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _bin(self, case: str) -> Path:
        from _common import RESEARCHGUARD_MIN_VERSION
        major, minor, patch = RESEARCHGUARD_MIN_VERSION
        below = (major, minor, patch - 1) if patch else (major, minor - 1, 99) if minor else (major - 1, 99, 99)
        folder = self.root / case
        folder.mkdir(exist_ok=True)
        if case != "absent":
            fake = folder / "fake_researchguard.py"
            version = ".".join(map(str, RESEARCHGUARD_MIN_VERSION if case == "current" else below))
            fake.write_text(FAKE_CONSOLE.format(version=version), encoding="utf-8")
            if os.name == "nt":
                (folder / "researchguard.cmd").write_text(f'@"{sys.executable}" -S "{fake}" %*\r\n', encoding="utf-8")
            else:
                launcher = folder / "researchguard"
                launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" -S "{fake}" "$@"\n', encoding="utf-8")
                launcher.chmod(0o755)
        return folder

    def preflight(self, provider: str, case: str) -> dict:
        if (provider, case) not in self.results:
            completed = subprocess.run(
                [sys.executable, "-B", "-E", "-S", str(SCRIPTS / "provider_preflight.py"), provider],
                env={**os.environ, "PATH": str(self._bin(case))}, capture_output=True, text=True, timeout=120,
            )
            self.results[(provider, case)] = json.loads(completed.stdout)
        return self.results[(provider, case)]
class _RealRouting:
    def __init__(self, consoles: _PathConsoles) -> None:
            self.consoles = consoles
    def reset(self, initial_state: State) -> None:
            for path in (ROOT, ROOT / "skills" / "logic-writing" / "scripts"):
                if str(path) not in sys.path:
                    sys.path.insert(0, str(path))
            import provider_preflight
            self.preflight = provider_preflight.preflight
            self.root = Path(tempfile.mkdtemp(prefix="lw-route-model-"))
            self.state = initial_state
    def apply_step(self, step):
        event, state = step.function_input, self.state
        if event.path_console:
            result = self.consoles.preflight(event.provider, event.path_console)
        else:
            result = self.preflight(event.provider, provider_root=str(self.root) if event.provider_root else None)
        evidence, output = (result['evidence'], result['status'])
        state = replace(state, provider=event.provider, provider_root=event.provider_root, provider_status=output, console=str(evidence.get('provider_console_id', '')), member_command=str(evidence.get('member_command', '')), path_console=event.path_console, console_source=str(evidence.get('console_source', '')), install_hint=bool(evidence.get('message')))
        self.state = state
        return ReplayObservation(function_name=step.function_name, observed_output=output, observed_state=state)
    def observe_state(self) -> State:
            return self.state
    def observe_output(self):
            return None
    def close(self) -> None:
            shutil.rmtree(getattr(self, "root", ""), ignore_errors=True)
def conformance():
    last = None
    consoles = _PathConsoles()
    try:
        for trace in select_covering_traces(build_explorer().explore().traces):
            adapter = _RealRouting(consoles)
            try:
                last = replay_trace(trace=trace,adapter=adapter,invariants=INVARIANTS,rules=(projected_state_matches(),projected_output_matches()))
            finally:adapter.close()
            if not last.ok:return last
    finally:consoles.close()
    return last
NOT_MODELED = {'skills/logic-writing/scripts/provider_preflight.py:main': 'Command wrapper: reads the provider name from the command line, calls preflight (anchored as ProviderPreflight) and prints its JSON result.'}
