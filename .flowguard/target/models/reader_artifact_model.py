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
COMPONENTS = ['reader-plan', 'reader-binding', 'reader-checks', 'reader-closure', 'reader-inputs', 'fiction-model', 'travel-model', 'researchguard-handoff', 'world-references']
IMPLEMENTED_BY = {
    "BuildReaderBrief": "skills/logic-writing/scripts/reader_plan.py:build_reader_brief",
    "BuildArtifactMap": "skills/logic-writing/scripts/artifact_map.py:build_artifact_map",
    "ReaderAudit": "skills/logic-writing/scripts/reader_checks.py:build_reader_audit",
    "RouteReview": "skills/logic-writing/scripts/reader_checks.py:_route_review_from_current",
    "ReaderJudgment": "skills/logic-writing/scripts/reader_checks.py:_reader_judgment_from_current",
    "DeriveClosure": "skills/logic-writing/scripts/derive_closure.py:derive_closure",
    "ImportAnchors": "skills/logic-writing/scripts/reader_fill.py:fill_brief_fingerprints",
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
    "readback_shows_failing_units": [
        "tests/e2e/test_worked_examples.py:test_show_plan_shows_findings_on_the_failing_unit",
    ],
    "text_follows_plan_order": [
        "tests/unit/test_reader.py:test_audit_finds_text_out_of_plan_order",
    ],
    "imported_anchor_keeps_research_direction": [
        "tests/unit/test_researchguard_status.py:test_imported_anchor_takes_the_research_direction",
    ],
}

ROOT = Path(__file__).resolve().parents[2]
OWNERS = ("investigation", "academic-writing", "fiction-writing", "travel-guide")
AUX_EVENTS = {"import", "order", "readback"}  # events on their own state fields, independent of the review chain
# Import cases: the research direction of one anchor for the root claim, and the relation it gets.
IMPORT_RELATIONS = {"oppose": "counter", "limit": "limit", "support": "support", "none": "context",
                    "no_status": "context", "hand_conflict": "anchor_relation_conflict"}


@dataclass(frozen=True)
class Event:
    kind: str                       # review | self_review | edit | close | import | order | readback
    quality: str = ""               # review: pass | repair; import: a key of IMPORT_RELATIONS; order: in_order | swapped; readback: clean | leak


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
    import_case: str = ""           # the last imported anchor's research direction case
    relation: str = ""              # the relation that anchor got, or the build error code
    order_case: str = ""            # in_order | swapped: sibling sections in the text against the plan
    order_audit: str = ""           # passed | plan_order_mismatch
    readback_case: str = ""         # clean | leak: the text read back after its audit
    readback: str = ""              # clean | shown | hidden: whether a failing unit shows its audit finding


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

    def relation_for(self, case: str) -> str:
        return IMPORT_RELATIONS[case]

    def order_audit_for(self, case: str) -> str:
        return "plan_order_mismatch" if case == "swapped" else "passed"

    def readback_for(self, case: str) -> str:
        return "shown" if case == "leak" else "clean"

    def apply(self, event: Event, state: State):
        if event.kind == "readback":
            shown = self.readback_for(event.quality)
            return (FunctionResult("read", replace(state, readback_case=event.quality, readback=shown),
                                   label=f"readback_{event.quality}"),)
        if event.kind == "order":
            audit = self.order_audit_for(event.quality)
            return (FunctionResult("audited", replace(state, order_case=event.quality, order_audit=audit),
                                   label=f"order_{event.quality}"),)
        if event.kind == "import":
            relation = self.relation_for(event.quality)
            return (FunctionResult("imported", replace(state, import_case=event.quality, relation=relation),
                                   label=f"import_{event.quality}"),)
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


class ImportedCounterMarkedSupport(Step):
    """Known-bad: every imported anchor is written as support, whatever the research says."""

    def relation_for(self, case: str) -> str:
        return "support"


class SwappedSectionsPass(Step):
    """Known-bad: the audit never compares the text order with the plan order."""

    def order_audit_for(self, case: str) -> str:
        return "passed"


class ReadbackHidesFindings(Step):
    """Known-bad: the plan readback shows the plan and text but not the checks' findings."""

    def readback_for(self, case: str) -> str:
        return "hidden" if case == "leak" else "clean"


def _readback_shows_failing_units(state: State, trace) -> InvariantResult:
    if state.readback_case == "leak" and state.readback != "shown":
        return InvariantResult.fail("a unit failing its audit reads back without the finding")
    return InvariantResult.pass_()


def _text_follows_plan_order(state: State, trace) -> InvariantResult:
    if state.order_case == "swapped" and state.order_audit != "plan_order_mismatch":
        return InvariantResult.fail("sibling sections appear in the text out of plan order and the audit passed")
    return InvariantResult.pass_()


def _imported_anchor_keeps_research_direction(state: State, trace) -> InvariantResult:
    if state.import_case and state.relation != IMPORT_RELATIONS[state.import_case]:
        return InvariantResult.fail("an imported anchor lost its research direction")
    return InvariantResult.pass_()


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
    Invariant("readback_shows_failing_units", "each failure on a unit is visible under that unit in the readback",
              _readback_shows_failing_units),
    Invariant("text_follows_plan_order", "sibling planned units appear in the text in plan order",
              _text_follows_plan_order),
    Invariant("imported_anchor_keeps_research_direction", "an imported anchor takes its relation from the research direction",
              _imported_anchor_keeps_research_direction),
    Invariant("closure_requires_current_artifact", "closure passes only on a review of the current bytes",
              _closure_requires_current_artifact),
    Invariant("independent_reader_required", "a broad claim requires an independent reader context",
              _independent_reader_required),
    Invariant("needs_repair_never_passes", "a review that asks for repair never closes as passed",
              _needs_repair_never_passes),
    Invariant("closure_belongs_to_the_final_owner", "only the final owner that wrote the artifact closes it",
              _closure_belongs_to_the_final_owner),
)
EVENTS = (Event("review", "pass"), Event("review", "repair"), Event("self_review", "pass"), Event("edit"), Event("close"),
          *(Event("import", case) for case in IMPORT_RELATIONS), Event("order", "in_order"), Event("order", "swapped"),
          Event("readback", "clean"), Event("readback", "leak"))


def _explorer(step: Step) -> Explorer:
    return Explorer(workflow=Workflow((step,)), initial_states=tuple(State(owner) for owner in OWNERS),
                    external_inputs=EVENTS, invariants=INVARIANTS, max_sequence_length=3, progress_steps=0)


def build_explorer() -> Explorer:
    return _explorer(Step())


def broken_variants() -> dict:
    return {"close_ignores_edits": _explorer(CloseIgnoresEdits()),
            "close_accepts_self_review": _explorer(CloseAcceptsSelfReview()),
            "repair_reported_as_pass": _explorer(RepairReportedAsPass()),
            "closure_for_sibling_owner": _explorer(CloseForSiblingOwner()),
            "imported_counter_anchor_marked_support": _explorer(ImportedCounterMarkedSupport()),
            "swapped_sections_pass": _explorer(SwappedSectionsPass()),
            "readback_hides_findings": _explorer(ReadbackHidesFindings())}


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

    def _import(self, case: str) -> str:
        """Import one anchor from a small research folder whose saved report gives its direction."""
        import json
        from reader_fill import fill_brief_fingerprints
        folder = self.root / f"research-{self._workdir().name}"
        folder.mkdir()
        directions = {"oppose": [("trace", "oppose"), ("logic", "support")], "limit": [("logic", "limit")],
                      "support": [("trace", "support")], "none": []}
        anchors = list(directions)
        (folder / "research.yaml").write_text(
            "schema: researchguard.research.v1\nquestion: Does the root claim hold?\n"
            "hypotheses:\n- {id: h-root, text: The root claim holds.}\nmodels: {source: source.yaml}\n", encoding="utf-8")
        (folder / "source.yaml").write_text("sources:\n- {source_id: s1}\nanchors:\n" + "".join(
            f"- {{anchor_id: a-{name}, source_id: s1, locator: 'p. {index}', text: 'Passage {index}.'}}\n"
            for index, name in enumerate(anchors, 1)), encoding="utf-8")
        report = {"question": "Does the root claim hold?", "hypotheses": [{"id": "h-root", "text": "The root claim holds."}],
                  "models": {"source": {"path": "source.yaml", "status": "ok"}},
                  "verdict": {"search": "stop_sufficient", "root_claim": {"id": "h-root", "wording_license": "qualify", "reason": "r"},
                              "live_hypotheses": ["h-root"], "contested": False, "errors": 0},
                  "evidence": [{"anchor": f"a-{name}", "directions": [
                      {"route": route, "hypothesis": "h-root", "direction": direction, "node": None}
                      for route, direction in directions[name]]} for name in anchors]}
        (folder / "research-status.json").write_text(json.dumps(report), encoding="utf-8")
        name = {"no_status": "oppose", "hand_conflict": "oppose"}.get(case, case)
        handwritten = ([{"anchor_id": "a-oppose", "source_id": "s1", "locator": "p. 1", "relation": "support",
                         "observed_summary": "Passage 1.", "boundary": "Only this passage."}] if case == "hand_conflict" else [])
        request = {"research_folder": str(folder), "content_boundaries": {"evidence_anchors": handwritten}}
        if case != "no_status":
            request["research_status"] = str(folder / "research-status.json")
        try:
            fill_brief_fingerprints(request)
        except self.validation_error as exc:
            return str(exc).split(":", 1)[0]
        row = next(row for row in request["content_boundaries"]["evidence_anchors"] if row["anchor_id"] == f"a-{name}")
        return row["relation"]

    def _readback(self, case: str) -> str:
        """Audit the investigation example (or its known-bad leak text) and read the plan back."""
        from _common import load_request
        from show_plan import plan_view
        from tests.v2_support import run_example_steps
        folder = self._workdir()
        example = ROOT / "skills/logic-writing/assets/examples/investigation"
        shutil.copytree(example, folder)
        if case == "leak":
            shutil.copyfile(example / "known-bad/leak.md", folder / "piece.md")
        run_example_steps(folder)
        view = plan_view(load_request(folder / "audit-request.json"), input_path=folder / "audit-request.json")
        shown = any(row.get("code") == "workflow_leak" for unit in view["planned_units"] for row in unit.get("findings", []))
        return "shown" if shown else "clean" if case == "clean" else "hidden"

    def _order(self, case: str) -> str:
        """Run the investigation example to its audit, with two sibling sections swapped when asked."""
        import json
        from _common import dump_json, load_request
        from audit_reader_output import audit_reader_output
        from build_artifact_map import validate_request as build_map
        from build_reader_brief import validate_request as build_brief
        from select_route import validate_request as select
        from validate_shared_writing import validate_shared_writing
        folder = self._workdir()
        shutil.copytree(ROOT / "skills/logic-writing/assets/examples/investigation", folder)
        if case == "swapped":
            piece = folder / "piece.md"
            text = piece.read_text(encoding="utf-8")
            first, second = text.index("## What it costs"), text.index("## Will it become the default?")
            end = text.find("\n## ", second + 1)
            end = len(text) if end < 0 else end + 1
            piece.write_text(text[:first] + text[second:end] + text[first:second] + text[end:], encoding="utf-8")
        for function, request, output in ((select, "route-request.json", "route-decision.json"),
                                          (build_brief, "brief-request.json", "reader-brief.json"),
                                          (build_map, "map-request.json", "artifact-map.json"),
                                          (validate_shared_writing, "shared-writing.json", "shared-writing-result.json"),
                                          (audit_reader_output, "audit-request.json", "audit.json")):
            result = function(load_request(folder / request))
            dump_json(result, folder / output)
        audit = json.loads((folder / "audit.json").read_text(encoding="utf-8"))["reader_audit"]
        codes = {row["code"] for row in audit["findings"]}
        return "plan_order_mismatch" if "plan_order_mismatch" in codes else audit["status"]

    def apply_step(self, step) -> ReplayObservation:
        event = step.function_input
        state = self.state
        if event.kind == "readback":
            state = replace(state, readback_case=event.quality, readback=self._readback(event.quality))
            self.state = state
            return ReplayObservation(function_name=step.function_name, observed_output="read", observed_state=state)
        if event.kind == "order":
            state = replace(state, order_case=event.quality, order_audit=self._order(event.quality))
            self.state = state
            return ReplayObservation(function_name=step.function_name, observed_output="audited", observed_state=state)
        if event.kind == "import":
            state = replace(state, import_case=event.quality, relation=self._import(event.quality))
            self.state = state
            return ReplayObservation(function_name=step.function_name, observed_output="imported", observed_state=state)
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
    """Replay traces covering every modeled transition against the real reader chain.

    Import and order events touch only their own state fields, so each is replayed once
    from a fresh state; the chain events are covered on traces without them.
    """
    last = None
    traces = build_explorer().explore().traces
    chain = [trace for trace in traces if all(step.function_input.kind not in AUX_EVENTS for step in trace.steps)]
    aux = {}
    for trace in traces:
        if len(trace.steps) == 1 and trace.steps[0].function_input.kind in AUX_EVENTS and trace.steps[0].old_state.owner == OWNERS[0]:
            aux.setdefault(trace.steps[0].function_input, trace)
    for trace in (*select_covering_traces(chain), *aux.values()):
        adapter = _RealReaderChain()
        try:
            last = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                rules=(projected_state_matches(), projected_output_matches()))
        finally:
            adapter.close()
        if not last.ok:
            return last
    return last


NOT_MODELED = {
    "skills/logic-writing/scripts/reader_checks.py:validate_route_artifact_review": "Public review entry of the four route commands: it validates the map, route and binding, then returns _route_review_from_current, which this model replays as RouteReview.",
    "skills/logic-writing/routes/academic/scripts/validate_academic_artifact.py:validate_academic_artifact": "40-line command wrapper that fills fingerprints and delegates to reader_checks.validate_route_artifact_review.",
    "skills/logic-writing/routes/fiction/scripts/validate_fiction_artifact.py:validate_fiction_artifact": "40-line command wrapper that fills fingerprints and delegates to reader_checks.validate_route_artifact_review.",
    "skills/logic-writing/routes/investigation/scripts/validate_investigation_artifact.py:validate_investigation_artifact": "40-line command wrapper that fills fingerprints and delegates to reader_checks.validate_route_artifact_review.",
    "skills/logic-writing/routes/travel/scripts/validate_travel_artifact.py:validate_travel_artifact": "40-line command wrapper that fills fingerprints and delegates to reader_checks.validate_route_artifact_review.",
    "skills/logic-writing/routes/fiction/scripts/run_native_regression.py:main": "Fiction regression driver that runs the native fiction validators on their example cases; covered by scripts/run_fiction_regression.py in CI.",
    "skills/logic-writing/routes/fiction/scripts/run_route_regression.py:main": "Fiction regression driver that runs the route cases and compares their expected codes; covered by scripts/run_fiction_regression.py in CI.",
    "skills/logic-writing/routes/travel/scripts/validate_failure_cases.py:main": "Travel regression command that applies each failure case to the base trip and compares its expected issue codes.",
    "skills/logic-writing/routes/travel/scripts/validate_positive_cases.py:main": "Travel regression command that applies each positive case to the base trip and expects no issue.",
    "skills/logic-writing/routes/travel/scripts/validate_travel_plan.py:main": "Command wrapper that prints the issues of travel_contract.review_plan for one plan file.",
    "skills/logic-writing/routes/travel/scripts/validate_travel_text_outputs.py:main": "Travel text regression command for saved guide texts; tests/unit/test_travel.py runs it on a good and a bullet-only guide.",
    "scripts/check_privacy.py:main": "Release maintenance command covered by tests/contract/test_privacy_scan.py.",
    "scripts/check_public_docs.py:main": "Release maintenance command covered by tests/contract/test_release_wrappers.py.",
    "scripts/run_fiction_regression.py:main": "Release maintenance command that runs the fiction regressions in CI; covered by tests/unit/test_fiction.py.",
    "scripts/run_travel_regression.py:main": "Release maintenance command that runs the travel regressions in CI.",
    "scripts/validate_skill.py:main": "Release maintenance command covered by tests/contract/test_install_skill.py.",
    "skills/logic-writing/scripts/build_source_unit_manifest.py:main": "Command that writes the source-unit manifest of an existing text for a revision; validate_revision_provenance checks its result.",
    "skills/logic-writing/scripts/show_plan.py:main": "Read-only command that prints the plan view of the given chain file; tests/e2e/test_worked_examples.py runs it on every chain file.",
    "scripts/install_skill.py:main": "Transactional skill copying and predecessor retirement are tested by installer/byte-contract tests; this is a release maintenance command rather than a writing-quality transition.",
    "skills/logic-writing/routes/fiction/scripts/run_longform_regression.py:main": "The finite regression driver executes native domain validators; its subprocess/output wrapper is tested by the fiction regression contract, while the domain validators own writing semantics.",
    "skills/logic-writing/routes/fiction/scripts/run_story_model_mesh_regression.py:main": "Finite developer regression orchestration writes only requested report files and is covered by native fiction regression checks, not a separate writing-state machine.",
}
