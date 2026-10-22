"""Executable model: current-text quality determines closure; broad claims need an independent read.

Each final owner writes one artifact. Review builds current-byte evidence and
an explicitly classified ReaderJudgment. Current passing self-review can close
as passed but never allows a broad claim. Repair remains needs_repair, and a
material edit stales every earlier review and rejects closure.

Conformance replays model traces on the real reader-chain scripts in a temporary
folder; declared judge_kind does not prove who actually wrote the judgment.
"""

from __future__ import annotations

import copy
import shutil
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from flowguard import (FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace,
                       select_covering_traces)
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer

MODEL_ID = "reader_artifact_model"
PARENT = "reader-artifact"
COMPONENTS = ["reader-artifact", "investigation", "academic", "fiction", "travel"]
IMPLEMENTED_BY = {
    "BuildReaderBrief": "skills/logic-writing/scripts/reader_pipeline.py:build_reader_brief",
    "BuildArtifactMap": "skills/logic-writing/scripts/reader_pipeline.py:build_artifact_map",
    "ReaderAudit": "skills/logic-writing/scripts/reader_pipeline.py:build_reader_audit",
    "RouteReview": "skills/logic-writing/scripts/reader_pipeline.py:_route_review_from_current",
    "ReaderJudgment": "skills/logic-writing/scripts/reader_pipeline.py:_reader_judgment_from_current",
    "DeriveClosure": "skills/logic-writing/scripts/derive_closure.py:derive_closure",
}
TESTED_BY = {
    "closure_requires_current_artifact": [
        "tests/unit/test_freshness_closure.py:test_complete_current_chain_closes",
        "tests/e2e/test_reader_v2_benchmark.py:test_each_route_exposes_repair_and_stale_edit",
    ],
    "independent_reader_required": [
        "tests/unit/test_reader.py:test_judge_must_be_independent",
        "tests/unit/test_freshness_closure.py:test_self_review_closes_without_a_broad_claim",
        "tests/adversarial/test_boundaries.py:test_same_agent_cannot_self_judge",
    ],
    "needs_repair_never_passes": [
        "tests/unit/test_freshness_closure.py:test_quality_failure_needs_repair",
        "tests/e2e/test_routes.py:test_route_quality_repair_cannot_be_overwritten_by_shared_kernel",
    ],
    "closure_belongs_to_the_final_owner": [
        "tests/e2e/test_routes.py:test_each_final_owner_delivers_one_complete_current_artifact",
    ],
}

ROOT = Path(__file__).resolve().parents[2]
OWNERS = ("investigation", "academic-writing", "fiction-writing", "travel-guide")


@dataclass(frozen=True)
class Event:
    kind: str                       # review | self_review | edit | close
    quality: str = ""               # review: pass | repair


@dataclass(frozen=True)
class State:
    owner: str                      # the final owner that wrote the artifact
    reviewed: bool = False          # a map, audit, route review and judgment exist
    current: bool = False           # that review was built from the current bytes
    quality: str = ""               # pass | repair, from the review
    independent: bool = False       # judge_kind declares independent_context
    closure: str = ""               # "" | passed | needs_repair | rejected
    closure_owner: str = ""
    broad_claim: bool = False


class Step:
    """Intended behavior of reviewing, editing and closing one written artifact."""

    name = "Step"
    reads = ("owner", "reviewed", "current", "quality", "independent")
    writes = ("reviewed", "current", "quality", "independent", "closure", "closure_owner", "broad_claim")

    def closure_result(self, state: State) -> str:
        if not (state.reviewed and state.current):
            return "rejected"
        return "passed" if state.quality == "pass" else "needs_repair"

    def broad_claim_for(self, state: State, result: str) -> bool:
        return result == "passed" and state.independent

    def closure_owner_for(self, state: State) -> str:
        return state.owner

    def apply(self, event: Event, state: State):
        if event.kind in {"review", "self_review"}:
            reviewed = replace(state, reviewed=True, current=True, quality=event.quality,
                               independent=event.kind == "review", closure="", closure_owner="", broad_claim=False)
            return (FunctionResult("reviewed", reviewed, label=f"{event.kind}_{event.quality}"),)
        if event.kind == "edit":
            # a material edit stales the map, audit, review, judgment and closure
            return (FunctionResult("edited", replace(state, current=False, closure="", closure_owner="", broad_claim=False), label="edit"),)
        result = self.closure_result(state)
        return (FunctionResult(result, replace(state, closure=result, closure_owner=self.closure_owner_for(state),
                                              broad_claim=self.broad_claim_for(state, result)),
                               label=f"close_{result}"),)


class CloseIgnoresEdits(Step):
    """Known-bad: closure trusts a review made before the last edit."""

    def closure_result(self, state: State) -> str:
        if not state.reviewed:
            return "rejected"
        return "passed" if state.quality == "pass" else "needs_repair"


class CloseAcceptsSelfReview(Step):
    """Known-bad: a passing self-review licenses an unjustified broad claim."""

    def broad_claim_for(self, state: State, result: str) -> bool:
        return result == "passed"


class RepairReportedAsPass(Step):
    """Known-bad: a current repair judgment is reported as passed."""

    def closure_result(self, state: State) -> str:
        return "passed" if state.reviewed and state.current else "rejected"


class CloseForSiblingOwner(Step):
    """Known-bad: a sibling route closes the artifact owned by another route."""

    def closure_owner_for(self, state: State) -> str:
        return OWNERS[(OWNERS.index(state.owner) + 1) % len(OWNERS)]


def _closure_requires_current_artifact(state: State, trace) -> InvariantResult:
    if state.closure == "passed" and not (state.reviewed and state.current):
        return InvariantResult.fail("closure passed without a review of the current bytes")
    return InvariantResult.pass_()


def _independent_reader_required(state: State, trace) -> InvariantResult:
    if state.broad_claim and not state.independent:
        return InvariantResult.fail("a self-review allowed a broad claim")
    return InvariantResult.pass_()


def _needs_repair_never_passes(state: State, trace) -> InvariantResult:
    if state.closure == "passed" and state.quality != "pass":
        return InvariantResult.fail("closure passed while the review asks for repair")
    return InvariantResult.pass_()


def _closure_belongs_to_the_final_owner(state: State, trace) -> InvariantResult:
    if state.closure and state.closure_owner != state.owner:
        return InvariantResult.fail("closure was issued for a different owner than the one that wrote the artifact")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant("closure_requires_current_artifact", "closure passes only on a review of the current bytes",
              _closure_requires_current_artifact),
    Invariant("independent_reader_required", "a broad claim requires an independent reader context",
              _independent_reader_required),
    Invariant("needs_repair_never_passes", "a review that asks for repair never closes as passed",
              _needs_repair_never_passes),
    Invariant("closure_belongs_to_the_final_owner", "only the final owner that wrote the artifact closes it",
              _closure_belongs_to_the_final_owner),
)
EVENTS = (Event("review", "pass"), Event("review", "repair"), Event("self_review", "pass"), Event("edit"), Event("close"))


def _explorer(step: Step) -> Explorer:
    return Explorer(workflow=Workflow((step,)), initial_states=tuple(State(owner) for owner in OWNERS),
                    external_inputs=EVENTS, invariants=INVARIANTS, max_sequence_length=3, progress_steps=0)


def build_explorer() -> Explorer:
    return _explorer(Step())


def broken_variants() -> dict:
    return {"close_ignores_edits": _explorer(CloseIgnoresEdits()),
            "close_accepts_self_review": _explorer(CloseAcceptsSelfReview()),
            "repair_reported_as_pass": _explorer(RepairReportedAsPass()),
            "closure_for_sibling_owner": _explorer(CloseForSiblingOwner())}


class _RealReaderChain:
    """Drives the real reader chain in a temporary folder through the tests' protocol builders."""

    def reset(self, initial_state: State) -> None:
        for path in (ROOT, ROOT / "skills" / "logic-writing" / "scripts"):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        from _common import ValidationError, fingerprint
        from derive_closure import derive_closure
        from tests.v2_support import closure_input, complete_chain
        self.validation_error, self.fingerprint = ValidationError, fingerprint
        self.derive_closure, self.closure_input, self.complete_chain = derive_closure, closure_input, complete_chain
        self.root = Path(tempfile.mkdtemp(prefix="lw-reader-model-"))
        self.count = 0
        self.chain: dict | None = None
        self.state = initial_state

    def close(self) -> None:
        shutil.rmtree(getattr(self, "root", ""), ignore_errors=True)

    def _workdir(self) -> Path:
        self.count += 1
        return self.root / f"step-{self.count}"

    def apply_step(self, step) -> ReplayObservation:
        event = step.function_input
        state = self.state
        if event.kind in {"review", "self_review"}:
            # the actual text with a fresh ReaderBrief, ArtifactMap, audit, route review and ReaderJudgment
            chain = self.complete_chain(self._workdir(), state.owner, pass_quality=event.quality == "pass")
            if event.kind == "self_review":
                judgment = copy.deepcopy(chain["judgment"])
                judgment["judge_kind"] = "self_review"
                judgment["judge_id"] = judgment["producer_id"]
                judgment.pop("judgment_fingerprint")
                judgment["judgment_fingerprint"] = self.fingerprint(judgment)
                chain["judgment"] = judgment
            self.chain = chain
            judgment = chain["judgment"]
            state = replace(state, owner=chain["route_decision"]["final_owner"], reviewed=True, current=True,
                            quality="pass" if judgment["status"] == "passed" else "repair",
                            independent=judgment["judge_kind"] == "independent_context",
                            closure="", closure_owner="", broad_claim=False)
            output = "reviewed"
        elif event.kind == "edit":
            if self.chain is not None:
                path = Path(self.chain["artifact_path"])
                path.write_text(path.read_text(encoding="utf-8") + "\n\nA materially new paragraph.", encoding="utf-8")
            state = replace(state, current=False, closure="", closure_owner="", broad_claim=False)
            output = "edited"
        else:
            output, closure_owner, broad_claim = "rejected", state.owner, False
            if self.chain is not None:
                try:
                    closure = self.derive_closure(self.closure_input(self.chain))["closure"]
                    output, closure_owner, broad_claim = closure["status"], closure["final_owner"], closure["broad_claim_allowed"]
                except self.validation_error:
                    output = "rejected"
            state = replace(state, closure=output, closure_owner=closure_owner, broad_claim=broad_claim)
        self.state = state
        return ReplayObservation(function_name=step.function_name, observed_output=output, observed_state=state)

    def observe_state(self) -> State:
        return self.state

    def observe_output(self):
        return None


def conformance():
    """Replay traces covering every modeled transition against the real reader chain."""
    last = None
    for trace in select_covering_traces(build_explorer().explore().traces):
        adapter = _RealReaderChain()
        try:
            last = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                rules=(projected_state_matches(), projected_output_matches()))
        finally:
            adapter.close()
        if not last.ok:
            return last
    return last
