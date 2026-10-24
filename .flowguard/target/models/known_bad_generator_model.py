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
TESTED_BY = {
    "every_variant_is_caught_or_toothless": [
        "tests/unit/test_known_bad.py:test_uncaught_variant_is_a_toothless_risk"],
    "variants_only_delete_or_insert_plan_phrases": [
        "tests/unit/test_known_bad.py:test_variants_use_only_existing_words_and_keep_the_original"],
    "original_text_is_never_changed": [
        "tests/unit/test_known_bad.py:test_variants_use_only_existing_words_and_keep_the_original"],
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


INVARIANTS = (
    Invariant("every_variant_is_caught_or_toothless", "each variant is caught or listed as a toothless risk",
              every_variant_is_caught_or_toothless),
    Invariant("variants_only_delete_or_insert_plan_phrases", "variants only delete, truncate or insert plan phrases",
              variants_only_delete_or_insert_plan_phrases),
    Invariant("original_text_is_never_changed", "the original piece is never changed", original_text_is_never_changed),
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
            "variant_edits_the_original": _explorer(EditsTheOriginal())}


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

    def _run(self, case: str) -> str:
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
