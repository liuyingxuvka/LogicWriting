"""Known-bad edits of the user's piece: deterministic, never new words, never the original, never hidden.

The generator makes small edits of the current text (delete, truncate, or insert
a phrase the plan or glossary already has) and runs each one through the real
reader chain. A variant no check catches is a `toothless:` residual risk of
closure, never a silent pass. Conformance replays a complete reader chain: it
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

from flowguard import (FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace,
                       select_covering_traces)
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer

MODEL_ID = "known_bad_generator"
PARENT = "reader-closure"
COMPONENTS = ["reader-closure"]
IMPLEMENTED_BY = {
    "CheckKnownBad": "skills/logic-writing/scripts/known_bad.py:check_known_bad",
    "TextVariants": "skills/logic-writing/scripts/known_bad.py:text_variants",
}
USES = {
    'LoadRequest': 'skills/logic-writing/scripts/_common.py:load_request',
    'DeriveClosure': 'skills/logic-writing/scripts/derive_closure.py:derive_closure',
    'RunChain': 'skills/logic-writing/scripts/run_chain.py:run_chain',
}
TESTED_BY = {
    "evidence_variants_are_caught_or_toothless": [
        "tests/unit/test_known_bad.py:test_unsupported_alternative_variant_is_generated",
        "tests/unit/test_known_bad.py:test_uncaught_unsupported_variant_is_toothless",
        "tests/unit/test_known_bad.py:test_noanchor_variant_is_caught_by_the_brief"],
    "every_variant_is_caught_or_toothless": [
        "tests/unit/test_known_bad.py:test_uncaught_variant_is_a_toothless_risk"],
    "variants_only_delete_or_insert_plan_phrases": [
        "tests/unit/test_known_bad.py:test_variants_use_only_existing_words_and_keep_the_original"],
    "original_text_is_never_changed": [
        "tests/unit/test_known_bad.py:test_variants_use_only_existing_words_and_keep_the_original"],
    "plan_relation_variants_are_caught": [
        "tests/unit/test_reader.py:test_relation_variants_are_generated_and_caught"],
}
NOT_MODELED = {
    "skills/logic-writing/scripts/known_bad.py:main": "Command wrapper that prints check_known_bad results or writes the catalog; the catalog bytes are compared with the shipped known-bad folders.",
}

ROOT = Path(__file__).resolve().parents[2]
INTERNAL_TERM = "SourceGuard"
CASES = {
    "generate": "existing_words_only",
    "reread_original": "unchanged",
    "close": "uncaught_listed",
    "relations": "relation_variants_caught",
    "evidence": "evidence_variants_honest",
    "evidence_uncaught": "evidence_risks_listed",
    "evidence_scope": "evidence_scope_preserved",
}


@dataclass(frozen=True)
class Event:
    case: str


@dataclass(frozen=True)
class State:
    case: str = ""
    result: str = ""


class Generator:
    """Intended behavior of generating, checking and reporting known-bad edits."""

    name = "Generator"
    reads = ("case",)
    writes = ("case", "result")

    def result_for(self, case: str) -> str:
        return CASES[case]

    def apply(self, event: Event, state: State):
        result = self.result_for(event.case)
        return (FunctionResult(result, replace(state, case=event.case, result=result), label=f"{event.case}:{result}"),)


class HidesUncaughtVariant(Generator):
    """Known-bad: an uncaught variant is dropped instead of becoming a toothless risk."""

    def result_for(self, case):
        return "uncaught_hidden" if case == "close" else super().result_for(case)


class WritesNewWords(Generator):
    """Known-bad: a variant inserts words the piece, plan and glossary do not have."""

    def result_for(self, case):
        return "new_words" if case == "generate" else super().result_for(case)


class EditsTheOriginal(Generator):
    """Known-bad: checking a variant writes it over the user's piece."""

    def result_for(self, case):
        return "edited" if case == "reread_original" else super().result_for(case)


class SwappedUnitsNotGenerated(Generator):
    """Known-bad: the generator only edits words, never the plan's order or world references."""

    def result_for(self, case):
        return "relation_variants_missing" if case == "relations" else super().result_for(case)


def plan_relation_variants_are_caught(state: State, trace) -> InvariantResult:
    if state.case == "relations" and state.result != "relation_variants_caught":
        return InvariantResult.fail("swapped siblings or a removed world reference are not generated and caught")
    return InvariantResult.pass_()


def every_variant_is_caught_or_toothless(state: State, trace) -> InvariantResult:
    if state.case == "close" and state.result != "uncaught_listed":
        return InvariantResult.fail("an uncaught variant is missing from closure's toothless risks")
    return InvariantResult.pass_()


def variants_only_delete_or_insert_plan_phrases(state: State, trace) -> InvariantResult:
    if state.case == "generate" and state.result != "existing_words_only":
        return InvariantResult.fail("a variant wrote words that are not in the piece, plan or glossary")
    return InvariantResult.pass_()


def original_text_is_never_changed(state: State, trace) -> InvariantResult:
    if state.case == "reread_original" and state.result != "unchanged":
        return InvariantResult.fail("the user's piece changed while variants were checked")
    return InvariantResult.pass_()


def evidence_variants_are_caught_or_toothless(state, trace):
    if state.case.startswith('evidence') and state.result != CASES[state.case]:
        return InvariantResult.fail('plan-owned unsupported text and required-anchor strips are generated, really checked or honestly listed; optional/nonresearch/reason boundaries stay legal')
    return InvariantResult.pass_()


class UnsupportedVariantNeverGenerated(Generator):
    def result_for(self, case):
        return 'evidence_missing' if case == 'evidence' else super().result_for(case)


INVARIANTS = (
    Invariant("plan_relation_variants_are_caught", "variants that break plan order and world references are generated and caught",
              plan_relation_variants_are_caught),
    Invariant("every_variant_is_caught_or_toothless", "each variant is caught or listed as a toothless risk",
              every_variant_is_caught_or_toothless),
    Invariant("variants_only_delete_or_insert_plan_phrases", "variants only delete, truncate or insert plan phrases",
              variants_only_delete_or_insert_plan_phrases),
    Invariant("original_text_is_never_changed", "the original piece is never changed", original_text_is_never_changed),
    Invariant('evidence_variants_are_caught_or_toothless',
              'every unsupported alternative gets an insert variant and every anchored required unit a strip variant, each caught or reported toothless',
              evidence_variants_are_caught_or_toothless),
)
EVENTS = tuple(Event(case) for case in CASES)


def _explorer(step: Generator) -> Explorer:
    return Explorer(workflow=Workflow((step,)), initial_states=(State(),), external_inputs=EVENTS,
                    invariants=INVARIANTS, max_sequence_length=1, progress_steps=0)


def build_explorer() -> Explorer:
    return _explorer(Generator())


def broken_variants() -> dict:
    return {"uncaught_variant_hidden": _explorer(HidesUncaughtVariant()),
            "variant_writes_new_words": _explorer(WritesNewWords()),
            "variant_edits_the_original": _explorer(EditsTheOriginal()),
            "swapped_units_not_generated": _explorer(SwappedUnitsNotGenerated()),
            "unsupported_variant_never_generated": _explorer(UnsupportedVariantNeverGenerated())}


def _words(text: str) -> set[str]:
    return set(re.findall(r"\w+", text))


class _RealGenerator:
    """Builds one complete investigation chain and runs the real generator and closure on it."""

    def reset(self, state: State) -> None:
        for path in (ROOT, ROOT / "skills" / "logic-writing" / "scripts"):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        from known_bad import check_known_bad, text_variants
        from derive_closure import derive_closure
        from tests.v2_support import closure_input, complete_chain
        self.check, self.variants, self.derive = check_known_bad, text_variants, derive_closure
        self.folder = Path(tempfile.mkdtemp(prefix="lw-known-bad-model-"))
        self.request = closure_input(complete_chain(self.folder, "investigation"))
        self.state = state

    def _relations(self) -> str:
        """Run the fiction example's chain to its review, then generate and check its variants."""
        import subprocess
        from _common import load_request
        skill = ROOT / "skills" / "logic-writing"
        folder = self.folder / "fiction"
        shutil.copytree(skill / "assets/examples/fiction", folder)
        from run_chain import run_chain
        from derive_closure import CLOSURE_INPUT_FILES
        result = run_chain(folder, until='review')
        if result['exit_code'] != 0:
            raise AssertionError(result['first_failure'])
        variants = self.check(load_request(folder / "closure-input.json", defaults=CLOSURE_INPUT_FILES))["variants"]
        kinds = {row["kind"]: row["caught"] for row in variants}
        wanted = {"swap", "noworld"}
        return "relation_variants_caught" if wanted <= kinds.keys() and all(kinds[kind] for kind in wanted) else "relation_variants_missing"

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
        # Keep the R1 pre-hardening witness after the shipped example gains its one guard.
        guard = 'oc-unsupported-default-soon'
        boundaries['prohibited_overclaims'] = [row for row in boundaries['prohibited_overclaims'] if row['overclaim_id'] != guard]
        review_path = folder / 'route-review.json'
        review = json.loads(review_path.read_text())
        review['review']['overclaim_checks'] = [row for row in review['review'].get('overclaim_checks', []) if row['overclaim_id'] != guard]
        review_path.write_text(json.dumps(review))
        if scope and not nonresearch:
            next(row for row in boundaries['content_units'] if row['content_unit_id'] == 'cu-recommend')['required'] = False
            next(row for row in boundaries['content_units'] if row['content_unit_id'] == 'cu-perf')['unsupported_reason'] = 'Synthetic scope control: retain this evidence gap.'
        if nonresearch:
            unit = boundaries['content_units'][0]
            boundaries['evidence_anchors'].append(dict(anchor_id='anc-knownbad-fixture', source_id='synthetic-story',
                locator='fixture:' + unit['content_unit_id'], relation='context',
                observed_summary=unit['safe_meaning'], boundary='Synthetic scope control, not a research result.'))
            unit['evidence_anchor_ids'] = ['anc-knownbad-fixture']
        path.write_text(json.dumps(request))
        result = run_chain(folder, until='review')
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
        texts = self.variants(text, reader_brief=request['reader_brief'], artifact_map=request['artifact_map'],
                              shared_writing=request['shared_writing'], route_review=request['route_review'])
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
            if (inserted is None or reported is None or inserted['text'] == text
                    or inserted['text'].replace(' ' + alternative['safe_meaning'], '', 1) != text):
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
        if ('toothless:noanchor:cu-perf' not in listed
                or any(row['unit'] == 'cu-recommend' for row in stripped)):
            return 'scope_changed'
        fiction = self._evidence_request(nonresearch=True)
        if any(row['kind'] == 'noanchor' for row in self.check(fiction)['variants']):
            return 'nonresearch_gate_added'
        return 'evidence_scope_preserved'

    def _run(self, case: str) -> str:
        if case.startswith('evidence'):
            return self._evidence(case)
        if case == "relations":
            return self._relations()
        request = self.request
        path = Path(request["artifact_map"]["artifact_path"])
        text = path.read_text(encoding="utf-8")
        if case == "generate":
            boundaries = request["reader_brief"]["content_boundaries"]
            allowed = _words(INTERNAL_TERM) | {word for row in boundaries.get("prohibited_overclaims", [])
                                                 for word in _words(row["forbidden_meaning"])}
            cases = self.variants(text, reader_brief=request["reader_brief"], artifact_map=request["artifact_map"],
                                  shared_writing=request["shared_writing"], route_review=request["route_review"])
            new = set().union(*(_words(row["text"]) - _words(text) for row in cases))
            return "existing_words_only" if new <= allowed else "new_words"
        if case == "reread_original":
            before = path.read_bytes()
            self.check(request)
            return "unchanged" if path.read_bytes() == before else "edited"
        uncaught = {f"toothless:{row['kind']}:{row.get('unit') or row['name']}"
                    for row in self.check(request)["variants"] if not row["caught"]}
        closure = self.derive(request)["closure"]
        listed = {row["defect_id"] for row in closure["residual_risk"] if row["defect_id"].startswith("toothless:")}
        return "uncaught_listed" if listed == uncaught else "uncaught_hidden"

    def apply_step(self, step) -> ReplayObservation:
        case = step.function_input.case
        result = self._run(case)
        self.state = replace(self.state, case=case, result=result)
        return ReplayObservation(function_name=step.function_name, observed_output=result, observed_state=self.state)

    def observe_state(self) -> State:
        return self.state

    def observe_output(self):
        return None

    def close(self) -> None:
        shutil.rmtree(getattr(self, "folder", ""), ignore_errors=True)


def conformance():
    """Replay generate, re-read and close on one complete current chain."""
    last = None
    for trace in select_covering_traces(build_explorer().explore().traces):
        adapter = _RealGenerator()
        try:
            last = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                rules=(projected_state_matches(), projected_output_matches()))
        finally:
            adapter.close()
        if not last.ok:
            return last
    return last
