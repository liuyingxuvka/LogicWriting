"""Finite quote, unit-identity and current-byte binding contracts, with real production calls."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import copy
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[2]

@dataclass(frozen=True)
class Request:
    kind: str

@dataclass(frozen=True)
class State:
    kind: str = ''
    accepted: bool = False
    named_before_identity: bool = False

class Bind:

    def __init__(self, mutation=''):
        self.mutation = mutation

    def expected(self, request, state):
        accepted = request.kind == 'valid'
        named = request.kind == 'vanished'
        if self.mutation == 'accept_short_quote' and request.kind == 'short':
            accepted = True
        if self.mutation == 'accept_ambiguous_quote' and request.kind == 'ambiguous':
            accepted = True
        if self.mutation == 'accept_stale_artifact' and request.kind in {'stale', 'vanished'}:
            accepted, named = (True, False)
        current = State(request.kind, accepted, named)
        return ('accepted' if accepted else 'rejected', current)

def quote_is_unique_and_at_least_12_chars(state):
    ok = state.kind not in {'short', 'ambiguous', 'missing'} or not state.accepted
    return True if ok else False

def vanished_unit_is_named_before_fingerprints(state):
    ok = state.kind != 'vanished' or (not state.accepted and state.named_before_identity)
    return True if ok else False

def stale_artifact_is_rejected(state):
    return False if state.kind == 'stale' and state.accepted else True
REQUESTS = tuple((Request(kind) for kind in ('valid', 'short', 'ambiguous', 'missing', 'vanished', 'stale')))

class Native:

    def __init__(self, root):
        self.root = root
        self.index = 0

    def reset(self, initial_state):
        self.state = initial_state

    def observe(self, event):
        from _common import ValidationError
        from reader_binding import validate_shared_writing, _resolve_quote, quote_binding_units
        from reader_fill import fill_check_fingerprints
        from artifact_map import build_artifact_map
        from tests.v2_support import make_reader_chain
        kind = event.kind
        folder = self.root / str(self.index)
        self.index += 1
        folder.mkdir()
        chain = make_reader_chain(folder, 'fiction-writing', language='en')
        amap = chain['artifact_map']
        units = {row['artifact_unit_id']: row for row in amap['units']}
        binding = copy.deepcopy(chain['shared_writing']['unit_bindings'][0])
        paragraph = units[binding['artifact_unit_ids'][0]]
        quote = paragraph['text']
        accepted, named, reason = (False, False, '')
        try:
            if kind == 'vanished':
                contract = copy.deepcopy(chain['shared_writing'])
                contract.pop('contract_fingerprint', None)
                contract.pop('reader_brief_fingerprint', None)
                contract['unit_bindings'][0]['artifact_unit_ids'] = ['artifact:paragraph:9999']
                fill_check_fingerprints({'artifact_map': amap, 'reader_brief': chain['reader_brief'], 'contract': contract})
            elif kind == 'stale':
                chain['artifact_path'].write_text('The current artifact is materially different.', encoding='utf-8')
                validate_shared_writing(chain['shared_writing'], artifact_map=amap, reader_brief=chain['reader_brief'])
            elif kind == 'missing':
                _resolve_quote(units, 'This quotation does not occur in the artifact.')
            elif kind == 'short':
                binding['anchor_excerpts'] = [quote[:5]]
                quote_binding_units(binding, units)
            elif kind == 'ambiguous':
                chain['artifact_path'].write_text(chain['artifact_path'].read_text() + '\n\n' + quote + '\n', encoding='utf-8')
                duplicate = build_artifact_map(chain['artifact_path'], map_id='map:ambiguous', language='en')
                binding['anchor_excerpts'] = [quote]
                binding.pop('artifact_unit_ids', None)
                quote_binding_units(binding, {row['artifact_unit_id']: row for row in duplicate['units']})
            else:
                contract = copy.deepcopy(chain['shared_writing'])
                current_binding = contract['unit_bindings'][0]
                current_binding['anchor_excerpts'] = [units[identifier]['text'] for identifier in current_binding.pop('artifact_unit_ids')]
                current_binding.pop('artifact_spans')
                contract.pop('contract_fingerprint', None)
                request = fill_check_fingerprints({'artifact_map': amap, 'reader_brief': chain['reader_brief'], 'contract': contract})
                validate_shared_writing(request['contract'], artifact_map=amap, reader_brief=chain['reader_brief'])
            accepted = True
        except ValidationError as exc:
            reason = f'{type(exc).__name__}: {exc}'
            named = kind == 'vanished' and 'artifact:paragraph:9999' in str(exc) and ('fingerprint' not in str(exc))
        self.state = State(kind, accepted, named)
        return ('accepted' if accepted else 'rejected', self.state)
RULES = {'quote_is_unique_and_at_least_12_chars': quote_is_unique_and_at_least_12_chars, 'vanished_unit_is_named_before_fingerprints': vanished_unit_is_named_before_fingerprints, 'stale_artifact_is_rejected': stale_artifact_is_rejected}
INITIAL_CASES = (State(),)
INPUT_CASES = REQUESTS
CALCULATE = Bind('').expected
BAD_EXPECTATIONS = {'accept_short_quote': Bind('accept_short_quote').expected, 'accept_ambiguous_quote': Bind('accept_ambiguous_quote').expected, 'accept_stale_artifact': Bind('accept_stale_artifact').expected}
