"""Canonical schemas reject invalid records with one typed error and preserve valid bytes."""
from __future__ import annotations
from dataclasses import dataclass, replace
from pathlib import Path
import copy, importlib.util, io, shutil, sys, tempfile
from contextlib import redirect_stdout
ROOT = Path(__file__).resolve().parents[2]

@dataclass(frozen=True)
class Event:
    valid: bool = True

@dataclass(frozen=True)
class State:
    valid: bool = True
    rejected: bool = False
    error_details: bool = True
    unchanged: bool = True

class Step:

    def rejected(self, event):
        return not event.valid

    def expected(self, event, state):
        result = State(event.valid, self.rejected(event), True, True)
        return ('rejected' if result.rejected else 'valid', result)

class InvalidPasses(Step):

    def rejected(self, event):
        return False

def _schema(state):
    return False if state.rejected == state.valid or not state.error_details or (not state.unchanged) else True
EVENTS = (Event(True), Event(False))

class Native:

    def reset(self, state):
        self.state = state
        self.folder = Path(tempfile.mkdtemp(prefix='lw-schema-contract-'))

    def observe(self, event):
        from schema_validation import assert_schema_valid, SchemaValidationError
        from tests.v2_support import complete_chain
        valid = event.valid
        record = complete_chain(self.folder / 'chain')['route_decision'] if valid else {}
        before = copy.deepcopy(record)
        rejected = False
        details = True
        try:
            assert_schema_valid('route-decision.schema.json', record)
        except SchemaValidationError as exc:
            rejected = True
            details = exc.schema_name == 'route-decision.schema.json' and bool(exc.issues)
        self.state = State(valid, rejected, details, record == before)
        return ('rejected' if rejected else 'valid', self.state)

    def close(self):
        shutil.rmtree(self.folder, ignore_errors=True)
RULES = {'schema_violation_raises_one_error_type': _schema}
INITIAL_CASES = (State(),)
INPUT_CASES = EVENTS
CALCULATE = Step().expected
BAD_EXPECTATIONS = {'invalid_record_passes_schema': InvalidPasses().expected}
