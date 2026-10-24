"""Finite quote, unit-identity and current-byte binding contracts, with native replay."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import copy
import sys
import tempfile

from flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace
from flowguard.conformance import projected_state_matches, projected_output_matches
from flowguard.explorer import Explorer

MODEL_ID = "shared_writing_binding"
PARENT = "reader-binding"
COMPONENTS = ["reader-binding"]
IMPLEMENTED_BY = {
    "ValidateBinding": "skills/logic-writing/scripts/reader_binding.py:validate_shared_writing",
    "ResolveQuote": "skills/logic-writing/scripts/reader_binding.py:_resolve_quote",
    "QuoteUnits": "skills/logic-writing/scripts/reader_binding.py:_quote_binding_units",
}
TESTED_BY = {
    "quote_is_unique_and_at_least_12_chars": [
        "tests/unit/test_shared_writing.py:test_current_plan_to_byte_binding_passes",
        "tests/unit/test_shared_writing.py:test_required_plan_unit_must_bind_actual_span",
        "tests/unit/test_shared_writing.py:test_missing_quote_fails_the_binding",
        "tests/unit/test_shared_writing.py:test_ambiguous_quote_asks_for_a_longer_one",
        "tests/unit/test_shared_writing.py:test_quote_and_unit_id_must_agree",
        "tests/unit/test_shared_writing.py:test_library_rechecks_the_quote_on_a_completed_contract",
    ],
    "vanished_unit_is_named_before_fingerprints": [
        "tests/unit/test_shared_writing.py:test_binding_to_a_vanished_unit_names_the_unit_before_any_fill",
    ],
    "stale_artifact_is_rejected": [
        "tests/unit/test_shared_writing.py:test_material_byte_change_stales_artifact_map",
    ],
}
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Request:
    kind: str


@dataclass(frozen=True)
class State:
    kind: str = ""
    accepted: bool = False
    named_before_identity: bool = False


class Bind:
    name = "ValidateBinding"
    reads = ()
    writes = ("kind", "accepted", "named_before_identity")

    def __init__(self, mutation=""):
        self.mutation = mutation

    def apply(self, request, state):
        accepted = request.kind == "valid"
        named = request.kind == "vanished"
        if self.mutation == "accept_short_quote" and request.kind == "short":
            accepted = True
        if self.mutation == "accept_ambiguous_quote" and request.kind == "ambiguous":
            accepted = True
        # Trusting an unverified identity bundle skips both byte freshness and
        # the vanished-unit diagnostic that must precede filling its identity.
        if self.mutation == "accept_stale_artifact" and request.kind in {"stale", "vanished"}:
            accepted, named = True, False
        current = State(request.kind, accepted, named)
        return (FunctionResult("accepted" if accepted else "rejected", current,
                               label="accepted" if accepted else "rejected"),)


def quote_is_unique_and_at_least_12_chars(state, trace):
    ok = state.kind not in {"short", "ambiguous", "missing"} or not state.accepted
    return InvariantResult.pass_() if ok else InvariantResult.fail("an invalid quotation was accepted")


def vanished_unit_is_named_before_fingerprints(state, trace):
    ok = state.kind != "vanished" or (not state.accepted and state.named_before_identity)
    return InvariantResult.pass_() if ok else InvariantResult.fail("a vanished unit was hidden by identity handling")


def stale_artifact_is_rejected(state, trace):
    return (InvariantResult.fail("a stale artifact was accepted")
            if state.kind == "stale" and state.accepted else InvariantResult.pass_())


INVARIANTS = (
    Invariant("quote_is_unique_and_at_least_12_chars", "quotations must be unique current passages of at least twelve characters", quote_is_unique_and_at_least_12_chars),
    Invariant("vanished_unit_is_named_before_fingerprints", "a vanished artifact unit is named before filling identity fingerprints", vanished_unit_is_named_before_fingerprints),
    Invariant("stale_artifact_is_rejected", "a material byte change invalidates the earlier binding", stale_artifact_is_rejected),
)

REQUESTS = tuple(Request(kind) for kind in ("valid", "short", "ambiguous", "missing", "vanished", "stale"))


def _explorer(mutation=""):
    return Explorer(workflow=Workflow((Bind(mutation),), name=MODEL_ID), initial_states=(State(),),
                    external_inputs=REQUESTS, invariants=INVARIANTS,
                    max_sequence_length=1, required_labels=("accepted", "rejected"))


def build_explorer():
    return _explorer()


def broken_variants():
    return {name: _explorer(name) for name in ("accept_short_quote", "accept_ambiguous_quote", "accept_stale_artifact")}


class Native:
    def __init__(self, root):
        self.root = root
        self.index = 0

    def reset(self, initial_state):
        self.state = initial_state

    def apply_step(self, step):
        from _common import ValidationError
        from reader_binding import validate_shared_writing, _resolve_quote, _quote_binding_units
        from reader_fill import fill_check_fingerprints
        from artifact_map import build_artifact_map
        from tests.v2_support import make_reader_chain
        kind = step.function_input.kind
        folder = self.root / str(self.index)
        self.index += 1
        folder.mkdir()
        chain = make_reader_chain(folder, "fiction-writing", language="en")
        amap = chain["artifact_map"]
        units = {row["artifact_unit_id"]: row for row in amap["units"]}
        binding = copy.deepcopy(chain["shared_writing"]["unit_bindings"][0])
        paragraph = units[binding["artifact_unit_ids"][0]]
        quote = paragraph["text"]
        accepted, named, reason = False, False, ""
        try:
            if kind == "vanished":
                contract = copy.deepcopy(chain["shared_writing"])
                contract.pop("contract_fingerprint", None)
                contract.pop("reader_brief_fingerprint", None)
                contract["unit_bindings"][0]["artifact_unit_ids"] = ["artifact:paragraph:9999"]
                fill_check_fingerprints({"artifact_map": amap, "reader_brief": chain["reader_brief"], "contract": contract})
            elif kind == "stale":
                chain["artifact_path"].write_text("The current artifact is materially different.", encoding="utf-8")
                validate_shared_writing(chain["shared_writing"], artifact_map=amap, reader_brief=chain["reader_brief"])
            elif kind == "missing":
                _resolve_quote(units, "This quotation does not occur in the artifact.")
            elif kind == "short":
                binding["anchor_excerpts"] = [quote[:5]]
                _quote_binding_units(binding, units)
            elif kind == "ambiguous":
                chain["artifact_path"].write_text(chain["artifact_path"].read_text()+"\n\n"+quote+"\n", encoding="utf-8")
                duplicate = build_artifact_map(chain["artifact_path"], map_id="map:ambiguous", language="en")
                binding["anchor_excerpts"] = [quote]
                binding.pop("artifact_unit_ids", None)
                _quote_binding_units(binding, {row["artifact_unit_id"]: row for row in duplicate["units"]})
            else:
                contract = copy.deepcopy(chain["shared_writing"])
                current_binding = contract["unit_bindings"][0]
                current_binding["anchor_excerpts"] = [units[identifier]["text"] for identifier in current_binding.pop("artifact_unit_ids")]
                current_binding.pop("artifact_spans")
                contract.pop("contract_fingerprint", None)
                request = fill_check_fingerprints({"artifact_map": amap, "reader_brief": chain["reader_brief"], "contract": contract})
                validate_shared_writing(request["contract"], artifact_map=amap, reader_brief=chain["reader_brief"])
            accepted = True
        except ValidationError as exc:
            reason = f"{type(exc).__name__}: {exc}"
            named = kind == "vanished" and "artifact:paragraph:9999" in str(exc) and "fingerprint" not in str(exc)
        self.state = State(kind, accepted, named)
        return ReplayObservation(function_name=step.function_name,
                                 observed_output="accepted" if accepted else "rejected", observed_state=self.state, reason=reason)

    def observe_state(self):
        return self.state

    def observe_output(self):
        return None


def conformance():
    """Replay all six finite requests against real binding and identity readers."""
    original = list(sys.path)
    try:
        sys.path[:0] = [str(ROOT / "skills/logic-writing/scripts"), str(ROOT)]
        with tempfile.TemporaryDirectory(prefix="lw-binding-model-") as folder:
            adapter = Native(Path(folder))
            result = None
            for trace in build_explorer().explore().traces:
                result = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                      rules=(projected_state_matches(), projected_output_matches()))
                if not result.ok:
                    return result
            return result
    finally:
        sys.path[:] = original
