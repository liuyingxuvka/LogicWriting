from __future__ import annotations
from dataclasses import dataclass, replace
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow, replay_trace, select_covering_traces
from flowguard.conformance import projected_state_matches, projected_output_matches
from flowguard.explorer import Explorer
from _reader_chain_fixture import _RealReaderChain, NativeReport
MODEL_ID = 'reader_artifact_model'
PARENT = 'reader-artifact'
COMPONENTS = ['reader-plan', 'reader-binding', 'reader-checks', 'reader-closure']
IMPLEMENTED_BY = {'BuildReaderBrief': 'skills/logic-writing/scripts/reader_plan.py:build_reader_brief', 'BuildArtifactMap': 'skills/logic-writing/scripts/artifact_map.py:build_artifact_map', 'RouteReview': 'skills/logic-writing/scripts/reader_checks.py:route_review_from_current', 'ReaderJudgment': 'skills/logic-writing/scripts/reader_checks.py:reader_judgment_from_current', 'DeriveClosure': 'skills/logic-writing/scripts/derive_closure.py:derive_closure'}
USES = {'ReaderAudit': 'skills/logic-writing/scripts/reader_checks.py:build_reader_audit'}
TESTED_BY = {'closure_requires_current_artifact': ['tests/unit/test_freshness_closure.py:test_complete_current_chain_closes', 'tests/e2e/test_reader_v2_benchmark.py:test_each_route_exposes_repair_and_stale_edit', 'tests/unit/test_academic.py:test_academic_closure_binds_revision_and_actual_artifact_chain'], 'independent_reader_required': ['tests/unit/test_reader.py:test_judge_must_be_independent', 'tests/unit/test_freshness_closure.py:test_self_review_closes_without_a_broad_claim', 'tests/adversarial/test_boundaries.py:test_same_agent_cannot_self_judge'], 'needs_repair_never_passes': ['tests/unit/test_freshness_closure.py:test_quality_failure_needs_repair', 'tests/e2e/test_routes.py:test_route_quality_repair_cannot_be_overwritten_by_shared_kernel', 'tests/unit/test_academic.py:test_academic_route_review_failure_blocks_final_claim'], 'closure_belongs_to_the_final_owner': ['tests/e2e/test_routes.py:test_each_final_owner_delivers_one_complete_current_artifact']}
NOT_MODELED = {'skills/logic-writing/scripts/reader_checks.py:validate_route_artifact_review': 'Public review entry of the four route commands: it validates the map, route and binding, then returns route_review_from_current, which this model replays as RouteReview.', 'skills/logic-writing/routes/academic/scripts/validate_academic_artifact.py:validate_academic_artifact': '40-line command wrapper that fills fingerprints and delegates to reader_checks.validate_route_artifact_review.', 'skills/logic-writing/routes/fiction/scripts/validate_fiction_artifact.py:validate_fiction_artifact': '40-line command wrapper that fills fingerprints and delegates to reader_checks.validate_route_artifact_review.', 'skills/logic-writing/routes/investigation/scripts/validate_investigation_artifact.py:validate_investigation_artifact': '40-line command wrapper that fills fingerprints and delegates to reader_checks.validate_route_artifact_review.', 'skills/logic-writing/routes/travel/scripts/validate_travel_artifact.py:validate_travel_artifact': '40-line command wrapper that fills fingerprints and delegates to reader_checks.validate_route_artifact_review.', 'skills/logic-writing/routes/fiction/scripts/run_native_regression.py:main': 'Fiction regression driver that runs the native fiction validators on their example cases; covered by scripts/run_fiction_regression.py in CI.', 'skills/logic-writing/routes/fiction/scripts/run_route_regression.py:main': 'Fiction regression driver that runs the route cases and compares their expected codes; covered by scripts/run_fiction_regression.py in CI.', 'skills/logic-writing/routes/travel/scripts/validate_failure_cases.py:main': 'Travel regression command that applies each failure case to the base trip and compares its expected issue codes.', 'skills/logic-writing/routes/travel/scripts/validate_positive_cases.py:main': 'Travel regression command that applies each positive case to the base trip and expects no issue.', 'skills/logic-writing/routes/travel/scripts/validate_travel_plan.py:main': 'Command wrapper that prints the issues of travel_contract.review_plan for one plan file.', 'skills/logic-writing/routes/travel/scripts/validate_travel_text_outputs.py:main': 'Travel text regression command for saved guide texts; tests/unit/test_travel.py runs it on a good and a bullet-only guide.', 'scripts/check_privacy.py:main': 'Release maintenance command covered by tests/contract/test_privacy_scan.py.', 'scripts/check_public_docs.py:main': 'Release maintenance command covered by tests/contract/test_release_wrappers.py.', 'scripts/run_fiction_regression.py:main': 'Release maintenance command that runs the fiction regressions in CI; covered by tests/unit/test_fiction.py.', 'scripts/run_travel_regression.py:main': 'Release maintenance command that runs the travel regressions in CI.', 'scripts/validate_skill.py:main': 'Release maintenance command covered by tests/contract/test_install_skill.py.', 'skills/logic-writing/scripts/build_source_unit_manifest.py:main': 'Command that writes the source-unit manifest of an existing text for a revision; validate_revision_provenance checks its result.', 'scripts/install_skill.py:main': 'Transactional skill copying and predecessor retirement are tested by installer/byte-contract tests; this is a release maintenance command rather than a writing-quality transition.', 'skills/logic-writing/routes/fiction/scripts/run_longform_regression.py:main': 'The finite regression driver executes native domain validators; its subprocess/output wrapper is tested by the fiction regression contract, while the domain validators own writing semantics.', 'skills/logic-writing/routes/fiction/scripts/run_story_model_mesh_regression.py:main': 'Finite developer regression orchestration writes only requested report files and is covered by native fiction regression checks, not a separate writing-state machine.'}
HANDOFF = {'plan_order_model': {'order_audit': ('order_audit', {'passed': 'passed', 'plan_order_mismatch': 'repair'})}}
OWNERS = ('investigation', 'fiction-writing')
@dataclass(frozen=True)
class Event:
    kind: str                       # review | self_review | edit | close | import | order | readback
    quality: str = ""               # review: pass | repair; import: a key of IMPORT_RELATIONS; order: in_order | swapped; readback: clean | leak

@dataclass(frozen=True)
class State:
    owner: str
    reviewed: bool=False
    current: bool=False
    quality: str=''
    independent: bool=False
    order_audit: str=''
    closure: str=''
    closure_owner: str=''
    broad_claim: bool=False

class Step:
    """Intended behavior of reviewing, editing and closing one written artifact."""

    name = "Step"
    reads = ("owner", "reviewed", "current", "quality", "independent", "order_audit")
    writes = ("reviewed", "current", "quality", "independent", "closure", "closure_owner", "broad_claim", "order_audit")

    def closure_result(self, state: State) -> str:
        if not (state.reviewed and state.current):
            return "rejected"
        return "passed" if state.quality == "pass" and state.order_audit != "repair" else "needs_repair"

    def broad_claim_for(self, state: State, result: str) -> bool:
        return result == "passed" and state.independent

    def closure_owner_for(self, state: State) -> str:
        return state.owner

    def apply(self, event: Event, state: State):
        if event.kind == 'order':
            audit = {'passed': 'passed', 'plan_order_mismatch': 'repair'}[event.quality]
            return (FunctionResult(event.quality, replace(state, order_audit=audit, closure='', closure_owner='', broad_claim=False), label='order_'+event.quality),)
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


class OrderMismatchPasses(Step):
    def closure_result(self,state):
        if not (state.reviewed and state.current):return 'rejected'
        return 'passed' if state.quality=='pass' else 'needs_repair'

def _closure_requires_current_artifact(state: State, trace) -> InvariantResult:
    if state.closure == "passed" and not (state.reviewed and state.current):
        return InvariantResult.fail("closure passed without a review of the current bytes")
    return InvariantResult.pass_()

def _independent_reader_required(state: State, trace) -> InvariantResult:
    if state.broad_claim and not state.independent:
        return InvariantResult.fail("a self-review allowed a broad claim")
    return InvariantResult.pass_()

def _needs_repair_never_passes(state: State, trace) -> InvariantResult:
    if state.closure == "passed" and (state.quality != "pass" or state.order_audit == "repair"):
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
EVENTS = (Event('review','pass'),Event('review','repair'),Event('self_review','pass'),Event('edit'),Event('close'),Event('order','passed'),Event('order','plan_order_mismatch'))
def _explorer(step):
    return Explorer(workflow=Workflow((step,)),initial_states=tuple(State(owner) for owner in OWNERS),external_inputs=EVENTS,invariants=INVARIANTS,max_sequence_length=3,progress_steps=0)
def build_explorer():return _explorer(Step())
def broken_variants():
    return {'close_ignores_edits':_explorer(CloseIgnoresEdits()),'close_accepts_self_review':_explorer(CloseAcceptsSelfReview()),'repair_reported_as_pass':_explorer(RepairReportedAsPass()),'closure_for_sibling_owner':_explorer(CloseForSiblingOwner()),'order_mismatch_passes':_explorer(OrderMismatchPasses())}
def conformance():
    traces=build_explorer().explore().traces
    chain=[trace for trace in traces if all(step.function_input.kind!='order' for step in trace.steps)]
    checked=0
    for trace in select_covering_traces(chain):
        adapter=_RealReaderChain()
        try:report=replay_trace(trace=trace,adapter=adapter,invariants=INVARIANTS,rules=(projected_state_matches(),projected_output_matches()))
        finally:adapter.close()
        if not report.ok:return report
        checked+=1
    adapter=_RealReaderChain()
    try:
        adapter.reset(State(OWNERS[0]))
        chain=adapter.complete_chain(adapter._workdir(),pass_quality=True)
        audit=chain['deterministic_audit']
        actual=adapter.derive_closure(adapter.closure_input(chain))['closure']['status']
        received=next(iter(Step().apply(Event('order','passed'),State(OWNERS[0],reviewed=True,current=True,quality='pass',independent=True)))).new_state
        expected=next(iter(Step().apply(Event('close'),received))).output
        if audit['quality_dimensions']['plan_order']!='passed' or actual!=expected:return NativeReport(checked,['passed order receipt differs from native audit/closure'])
        received=next(iter(Step().apply(Event('order','plan_order_mismatch'),State(OWNERS[0],reviewed=True,current=True,quality='pass',independent=True)))).new_state
        if adapter._order('swapped')!='plan_order_mismatch' or next(iter(Step().apply(Event('close'),received))).output!='needs_repair':return NativeReport(checked,['repair order receipt differs from native audit'])
    finally:adapter.close()
    return NativeReport(checked+2,[])
