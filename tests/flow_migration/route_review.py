"""Each route wrapper reviews for its native owner and preserves repair results."""
from __future__ import annotations
from dataclasses import dataclass, replace
from pathlib import Path
import copy, importlib.util, io, shutil, sys, tempfile
from contextlib import redirect_stdout
ROOT = Path(__file__).resolve().parents[2]
ROUTES = {'academic-writing': 'academic', 'fiction-writing': 'fiction', 'investigation': 'investigation', 'travel-guide': 'travel'}

@dataclass(frozen=True)
class Event:
    owner: str
    passed: bool = True
    sibling: bool = False

@dataclass(frozen=True)
class State:
    sibling: bool = False
    rejected: bool = False
    passed: bool = True
    status: str = ''

class Step:

    def rejected(self, event):
        return event.sibling

    def status(self, event):
        return 'current_pass' if event.passed else 'partial'

    def expected(self, event, state):
        rejected = self.rejected(event)
        status = 'rejected' if rejected else self.status(event)
        return (status, State(event.sibling, rejected, event.passed, status))

class WrongOwner(Step):

    def rejected(self, event):
        return False

class RepairPasses(Step):

    def status(self, event):
        return 'current_pass'

def _own(state):
    return False if state.sibling and (not state.rejected) else True

def _partial(state):
    return False if not state.rejected and state.status and (state.status != ('current_pass' if state.passed else 'partial')) else True
EVENTS = tuple((Event(owner, passed, sibling) for owner in ROUTES for passed in (True, False) for sibling in (False, True)))

class Native:

    def reset(self, state):
        self.state = state
        self.folder = Path(tempfile.mkdtemp(prefix='lw-route-review-'))

    def observe(self, event):
        from tests.v2_support import complete_chain
        from _common import ValidationError
        import importlib
        chain = complete_chain(self.folder / 'chain', event.owner, pass_quality=event.passed)
        route = ROUTES[event.owner]
        path = str(ROOT / f'skills/logic-writing/routes/{route}/scripts')
        if path not in sys.path:
            sys.path.insert(0, path)
        function = getattr(importlib.import_module(f'validate_{route}_artifact'), f'validate_{route}_artifact')
        brief = copy.deepcopy(chain['reader_brief'])
        if event.sibling:
            sibling = next((owner for owner in ROUTES if owner != event.owner))
            brief = complete_chain(self.folder / 'sibling', sibling)['reader_brief']
        request = {'review': chain['route_review'], 'route_composition': chain['route_composition'], 'artifact_map': chain['artifact_map'], 'reader_brief': brief, 'shared_writing': chain['shared_writing']}
        try:
            result = function(request)
            status = result['status']
            rejected = False
        except ValidationError as exc:
            if 'sibling' not in str(exc):
                raise
            status = 'rejected'
            rejected = True
        self.state = State(event.sibling, rejected, event.passed, status)
        return (status, self.state)

    def close(self):
        shutil.rmtree(self.folder, ignore_errors=True)
RULES = {'route_command_reviews_for_its_own_owner': _own, 'failed_review_is_partial': _partial}
INITIAL_CASES = (State(),)
INPUT_CASES = EVENTS
CALCULATE = Step().expected
BAD_EXPECTATIONS = {'route_command_uses_another_owner': WrongOwner().expected, 'failed_review_reported_current': RepairPasses().expected}
