"""Known-bad edits of the user's piece: deterministic, never new words, never the original, never hidden.

The generator makes small edits of the current text (delete, truncate, or insert
a phrase the plan or glossary already has) and runs each one through the real
reader chain. A variant no check catches is a `toothless:` residual risk of
closure, never a silent pass. The functional fixture builds a complete reader chain: it
generates the variants, compares their words with the original and the allowed
phrases, re-reads the original bytes, and compares closure's toothless risks
with the variants the chain did not catch.
"""
from __future__ import annotations
import re
import shutil
import sys
import tempfile
import json
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
INTERNAL_TERM = 'SourceGuard'
CASES = {'generate': 'existing_words_only', 'reread_original': 'unchanged', 'close': 'uncaught_listed', 'relations': 'relation_variants_caught', 'evidence': 'evidence_variants_honest', 'evidence_uncaught': 'evidence_risks_listed', 'evidence_scope': 'evidence_scope_preserved'}

@dataclass(frozen=True)
class Event:
    case: str

@dataclass(frozen=True)
class State:
    case: str = ''
    result: str = ''

class Generator:
    """Intended behavior of generating, checking and reporting known-bad edits."""

    def result_for(self, case: str) -> str:
        return CASES[case]

    def expected(self, event: Event, state: State):
        result = self.result_for(event.case)
        return (result, replace(state, case=event.case, result=result))

class HidesUncaughtVariant(Generator):
    """Known-bad: an uncaught variant is dropped instead of becoming a toothless risk."""

    def result_for(self, case):
        return 'uncaught_hidden' if case == 'close' else super().result_for(case)

class WritesNewWords(Generator):
    """Known-bad: a variant inserts words the piece, plan and glossary do not have."""

    def result_for(self, case):
        return 'new_words' if case == 'generate' else super().result_for(case)

class EditsTheOriginal(Generator):
    """Known-bad: checking a variant writes it over the user's piece."""

    def result_for(self, case):
        return 'edited' if case == 'reread_original' else super().result_for(case)

class SwappedUnitsNotGenerated(Generator):
    """Known-bad: the generator only edits words, never the plan's order or world references."""

    def result_for(self, case):
        return 'relation_variants_missing' if case == 'relations' else super().result_for(case)

def plan_relation_variants_are_caught(state: State):
    if state.case == 'relations' and state.result != 'relation_variants_caught':
        return False
    return True

def every_variant_is_caught_or_toothless(state: State):
    if state.case == 'close' and state.result != 'uncaught_listed':
        return False
    return True

def variants_only_delete_or_insert_plan_phrases(state: State):
    if state.case == 'generate' and state.result != 'existing_words_only':
        return False
    return True

def original_text_is_never_changed(state: State):
    if state.case == 'reread_original' and state.result != 'unchanged':
        return False
    return True

def evidence_variants_are_caught_or_toothless(state):
    if state.case.startswith('evidence') and state.result != CASES[state.case]:
        return False
    return True

class UnsupportedVariantNeverGenerated(Generator):

    def result_for(self, case):
        return 'evidence_missing' if case == 'evidence' else super().result_for(case)
EVENTS = tuple((Event(case) for case in CASES))

def _words(text: str) -> set[str]:
    return set(re.findall('\\w+', text))

class _RealGenerator:
    """Builds one complete investigation chain and runs the real generator and closure on it."""

    def reset(self, state: State) -> None:
        for path in (ROOT, ROOT / 'skills' / 'logic-writing' / 'scripts'):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        from known_bad import check_known_bad, text_variants
        from derive_closure import derive_closure
        from tests.v2_support import closure_input, complete_chain
        self.check, self.variants, self.derive = (check_known_bad, text_variants, derive_closure)
        self.folder = Path(tempfile.mkdtemp(prefix='lw-known-bad-contract-'))
        self.request = closure_input(complete_chain(self.folder, 'investigation'))
        self.state = state

    def _relations(self) -> str:
        """Run the fiction example's chain to its review, then generate and check its variants."""
        import subprocess
        from _common import load_request
        skill = ROOT / 'skills' / 'logic-writing'
        folder = self.folder / 'fiction'
        shutil.copytree(skill / 'assets/examples/fiction', folder)
        from run_chain import run_chain
        from derive_closure import CLOSURE_INPUT_FILES
        result = run_chain(folder, until='review')
        if result['exit_code'] != 0:
            raise AssertionError(result['first_failure'])
        variants = self.check(load_request(folder / 'closure-input.json', defaults=CLOSURE_INPUT_FILES))['variants']
        kinds = {row['kind']: row['caught'] for row in variants}
        wanted = {'swap', 'noworld'}
        return 'relation_variants_caught' if wanted <= kinds.keys() and all((kinds[kind] for kind in wanted)) else 'relation_variants_missing'

    def _evidence_request(self, scope=False, nonresearch=False):
        from _common import load_request
        from reader_fill import fill_closure_fingerprints
        from run_chain import run_chain
        from derive_closure import CLOSURE_INPUT_FILES
        route = 'fiction' if nonresearch else 'investigation'
        folder = self.folder / ('evidence-' + route)
        shutil.copytree(ROOT / 'skills/logic-writing/assets/examples' / route, folder)
        path = folder / 'brief-request.json'
        request = json.loads(path.read_text())
        boundaries = request['content_boundaries']
        guard = 'oc-unsupported-default-soon'
        boundaries['prohibited_overclaims'] = [row for row in boundaries['prohibited_overclaims'] if row['overclaim_id'] != guard]
        review_path = folder / 'route-review.json'
        review = json.loads(review_path.read_text())
        review['review']['overclaim_checks'] = [row for row in review['review'].get('overclaim_checks', []) if row['overclaim_id'] != guard]
        review_path.write_text(json.dumps(review))
        if scope and (not nonresearch):
            next((row for row in boundaries['content_units'] if row['content_unit_id'] == 'cu-recommend'))['required'] = False
            next((row for row in boundaries['content_units'] if row['content_unit_id'] == 'cu-perf'))['unsupported_reason'] = 'Synthetic scope control: retain this evidence gap.'
        if nonresearch:
            unit = boundaries['content_units'][0]
            boundaries['evidence_anchors'].append(dict(anchor_id='anc-knownbad-fixture', source_id='synthetic-story', locator='fixture:' + unit['content_unit_id'], relation='context', observed_summary=unit['safe_meaning'], boundary='Synthetic scope control, not a research result.'))
            unit['evidence_anchor_ids'] = ['anc-knownbad-fixture']
        path.write_text(json.dumps(request))
        from run_chain import _stamp_review
        result = _stamp_review(folder)
        if result['exit_code']:
            raise AssertionError(result['first_failure'])
        return fill_closure_fingerprints(load_request(folder / 'closure-input.json', defaults=CLOSURE_INPUT_FILES))

    def _evidence(self, case):
        request = self._evidence_request(scope=case == 'evidence_scope')
        before = deepcopy(request)
        path = Path(request['artifact_map']['artifact_path'])
        original = path.read_bytes()
        text = original.decode('utf-8')
        boundaries = request['reader_brief']['content_boundaries']
        texts = self.variants(text, reader_brief=request['reader_brief'], artifact_map=request['artifact_map'], shared_writing=request['shared_writing'], route_review=request['route_review'])
        result = self.check(request)
        reports = result['variants']
        unsupported = [row for row in boundaries['alternatives'] if row['status'] == 'unsupported']
        anchored = {row['content_unit_id']: row for row in boundaries['content_units'] if row['required'] and row['evidence_anchor_ids']}
        stripped = [row for row in reports if row['kind'] == 'noanchor']
        if {row['unit'] for row in stripped} != set(anchored) or len(stripped) != len(anchored):
            return 'evidence_missing'
        for alternative in unsupported:
            identity = alternative['alternative_id']
            inserted = next((row for row in texts if row['kind'] == 'unsupported' and row['unit'] == identity), None)
            reported = next((row for row in reports if row['kind'] == 'unsupported' and row['unit'] == identity), None)
            if inserted is None or reported is None or inserted['text'] == text or (inserted['text'].replace(' ' + alternative['safe_meaning'], '', 1) != text):
                return 'evidence_missing'
        for row in stripped:
            reason = anchored[row['unit']].get('unsupported_reason', '').strip()
            if reason:
                if row['caught']:
                    return 'legal_gap_was_blocked'
            elif not row['caught'] or row.get('step') != 'brief' or row.get('code') != 'content_unit_unsupported':
                return 'anchor_strip_not_checked'
        if request != before or path.read_bytes() != original:
            return 'original_changed'
        if case == 'evidence':
            return 'evidence_variants_honest'
        closure = self.derive(request)['closure']
        expected_risks = {f"toothless:{row['kind']}:{row.get('unit') or row['name']}" for row in reports if not row['caught']}
        listed = {row['defect_id'] for row in closure['residual_risk'] if row['defect_id'].startswith('toothless:')}
        if closure['status'] != 'passed' or listed != expected_risks or 'toothless:unsupported:alt-default-soon' not in listed:
            return 'evidence_risks_hidden'
        if case == 'evidence_uncaught':
            return 'evidence_risks_listed'
        if 'toothless:noanchor:cu-perf' not in listed or any((row['unit'] == 'cu-recommend' for row in stripped)):
            return 'scope_changed'
        fiction = self._evidence_request(nonresearch=True)
        if any((row['kind'] == 'noanchor' for row in self.check(fiction)['variants'])):
            return 'nonresearch_gate_added'
        return 'evidence_scope_preserved'

    def _run(self, case: str) -> str:
        if case.startswith('evidence'):
            return self._evidence(case)
        if case == 'relations':
            return self._relations()
        request = self.request
        path = Path(request['artifact_map']['artifact_path'])
        text = path.read_text(encoding='utf-8')
        if case == 'generate':
            boundaries = request['reader_brief']['content_boundaries']
            allowed = _words(INTERNAL_TERM) | {word for row in boundaries.get('prohibited_overclaims', []) for word in _words(row['forbidden_meaning'])}
            cases = self.variants(text, reader_brief=request['reader_brief'], artifact_map=request['artifact_map'], shared_writing=request['shared_writing'], route_review=request['route_review'])
            new = set().union(*(_words(row['text']) - _words(text) for row in cases))
            return 'existing_words_only' if new <= allowed else 'new_words'
        if case == 'reread_original':
            before = path.read_bytes()
            self.check(request)
            return 'unchanged' if path.read_bytes() == before else 'edited'
        uncaught = {f"toothless:{row['kind']}:{row.get('unit') or row['name']}" for row in self.check(request)['variants'] if not row['caught']}
        closure = self.derive(request)['closure']
        listed = {row['defect_id'] for row in closure['residual_risk'] if row['defect_id'].startswith('toothless:')}
        return 'uncaught_listed' if listed == uncaught else 'uncaught_hidden'

    def observe(self, event):
        case = event.case
        result = self._run(case)
        self.state = replace(self.state, case=case, result=result)
        return (result, self.state)

    def close(self) -> None:
        shutil.rmtree(getattr(self, 'folder', ''), ignore_errors=True)
RULES = {'plan_relation_variants_are_caught': plan_relation_variants_are_caught, 'every_variant_is_caught_or_toothless': every_variant_is_caught_or_toothless, 'variants_only_delete_or_insert_plan_phrases': variants_only_delete_or_insert_plan_phrases, 'original_text_is_never_changed': original_text_is_never_changed, 'evidence_variants_are_caught_or_toothless': evidence_variants_are_caught_or_toothless}
INITIAL_CASES = (State(),)
INPUT_CASES = EVENTS
CALCULATE = Generator().expected
BAD_EXPECTATIONS = {'uncaught_variant_hidden': HidesUncaughtVariant().expected, 'variant_writes_new_words': WritesNewWords().expected, 'variant_edits_the_original': EditsTheOriginal().expected, 'swapped_units_not_generated': SwappedUnitsNotGenerated().expected, 'unsupported_variant_never_generated': UnsupportedVariantNeverGenerated().expected}
