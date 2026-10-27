"""Fresh native reader-chain replay support; no model states or stored verdicts."""
from __future__ import annotations
import copy, shutil, sys, tempfile
from pathlib import Path
from dataclasses import dataclass, replace
from flowguard import ReplayObservation
ROOT = Path(__file__).resolve().parents[2]
@dataclass
class NativeReport:
    checked: int
    mismatches: list[str]
    @property
    def ok(self): return not self.mismatches
    def format_text(self, max_examples=None):
        rows=self.mismatches if max_examples is None else self.mismatches[:max_examples]
        return '\n'.join([f'conformance: {self.checked-len(self.mismatches)}/{self.checked} cases match native code',
                          *['  mismatch: '+str(row) for row in rows]])

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
        import hashlib
        for index,row in enumerate(report['evidence'],1):
            row.update(source='s1',locator=f'p. {index}',summary=f'Passage {index}.',boundary='Use only what the quoted passage says.')
        if case=='support':
            row=next(row for row in report['evidence'] if row['anchor']=='a-support')
            row.update(locator='report locator',summary='Report-normalized passage.',boundary='Report-owned scope.')
        report['input_digests']=[{'path':name,'sha256':hashlib.sha256((folder/name).read_bytes()).hexdigest()} for name in ('research.yaml','source.yaml')]
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
        expected=next(item for item in report['evidence'] if item['anchor']==f'a-{name}')
        self.import_fields_match=(row['locator']==expected['locator'] and row['observed_summary']==expected['summary'] and row['boundary']==expected['boundary'])
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
        import io, json
        from contextlib import redirect_stdout
        from show_plan import main
        previous = sys.argv
        output = io.StringIO()
        try:
            sys.argv = ['show_plan.py', '--input', str(folder / 'audit-request.json'), '--json']
            with redirect_stdout(output):
                code = main()
        finally:
            sys.argv = previous
        if code not in (0, None):
            raise AssertionError('native show_plan failed')
        view = json.loads(output.getvalue())
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
        if case == 'swapped' and (audit['status'] == 'passed' or audit['quality_dimensions']['plan_order'] != 'repair'):
            raise AssertionError('native order audit did not mark the swapped sections for repair')
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
            relation=self._import(event.quality)
            fields={'report_fields_match':getattr(self,'import_fields_match',True)} if hasattr(state,'report_fields_match') else {}
            state = replace(state, import_case=event.quality, relation=relation, **fields)
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
