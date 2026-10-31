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

    def _anchor_authority(self, case):
        """Read the public H3 brief input and its declared outside-research risk."""
        import json
        from run_chain import run_chain

        folder = self._workdir()
        route = 'fiction' if case == 'no_folder' else 'investigation'
        shutil.copytree(ROOT / 'skills/logic-writing/assets/examples' / route, folder)
        path = folder / 'brief-request.json'
        request = json.loads(path.read_text())
        reason = 'This anchor is an outside opinion; it is not a result of the research folder.'
        if case != 'research':
            anchor = {'anchor_id': 'anc-invented', 'source_id': 'src-blog',
                      'locator': 'a blog post, 2025', 'relation': 'support',
                      'observed_summary': 'Free-threading is production ready.',
                      'boundary': "One author's opinion."}
            if case in ('outside', 'blank_reason'):
                anchor['outside_research'] = reason if case == 'outside' else '  '
            boundaries = request['content_boundaries']
            boundaries['evidence_anchors'].append(anchor)
            if route == 'investigation':
                next(row for row in boundaries['content_units']
                     if row['content_unit_id'] == 'cu-recommend')['evidence_anchor_ids'].append('anc-invented')
        path.write_text(json.dumps(request))
        result = run_chain(folder, until='closure' if case in ('research', 'outside') else 'brief')
        if result['exit_code']:
            return result['first_failure']['code']
        if case == 'outside':
            closure = result['results']['closure']['closure']
            risk = {'defect_id': 'outside_research:anc-invented',
                    'owner': 'investigation', 'reason': reason}
            return 'passed+risk' if closure['status'] == 'passed' and risk in closure['residual_risk'] else 'missing-risk'
        return 'passed'

    def _request_metadata(self, request):
        request['request'] = ('Is free-threaded Python ready to be the default build? '
                              'Tell me its official status as of Python 3.14 and whether we should plan a migration now.')
        for unit in request['content_boundaries']['content_units']:
            unit['source'] = 'research'
            if unit['content_unit_id'] == 'cu-status-314':
                unit.update(source='request', quote='official status as of Python 3.14')
            elif unit['content_unit_id'] == 'cu-recommend':
                unit['source'] = 'ai'

    def _request(self, case):
        import json
        from run_chain import run_chain
        folder = self._workdir()
        shutil.copytree(ROOT / 'skills/logic-writing/assets/examples/investigation', folder)
        path = folder / 'brief-request.json'
        request = json.loads(path.read_text())
        self._request_metadata(request)
        raw = ' \n' + request['request'] + '\n '
        request['request'] = raw
        unit = next(row for row in request['content_boundaries']['content_units'] if row['content_unit_id'] == 'cu-status-314')
        if case == 'missing_request':
            request.pop('request')
        elif case == 'missing_source':
            unit.pop('source')
        elif case == 'paraphrase':
            unit['quote'] = 'is it the default in 3.14'
        elif case == 'optional':
            unit['required'] = False
            unit.pop('source')
            unit.pop('quote')
        elif case == 'optional_case_changed':
            unit.update(required=False, quote='Official status as of Python 3.14')
        elif case == 'spacing_changed':
            unit['quote'] = '\tofficial status as of Python 3.14'
        path.write_text(json.dumps(request))
        result = run_chain(folder, until='brief')
        if result['exit_code']:
            return result['first_failure']['code']
        brief = result['results']['brief']['reader_brief']
        quoted = next(row for row in brief['content_boundaries']['content_units'] if row['content_unit_id'] == 'cu-status-314')
        return 'verbatim' if (brief.get('request') == raw and quoted.get('quote') == unit.get('quote')) else 'request_changed'

    def _readback(self, case: str, input_name="shared-writing-result.json") -> str:
        """Audit the investigation example (or its known-bad leak text) and read the plan back."""
        from _common import load_request
        from show_plan import plan_view, render_plan
        from tests.v2_support import run_example_steps

        folder = self._workdir()
        example = ROOT / "skills/logic-writing/assets/examples/investigation"
        shutil.copytree(example, folder)
        writer_closure = writer_console = True
        if case == 'writer':
            import io, json
            from contextlib import redirect_stdout
            from run_chain import run_chain, main as run_main
            path = folder / 'brief-request.json'
            request = json.loads(path.read_text())
            self._request_metadata(request)
            writer = next(row for row in request['content_boundaries']['content_units'] if row['content_unit_id'] == 'cu-recommend')
            writer['required'] = False
            path.write_text(json.dumps(request))
            writer_line = 'added by the writer: cu-recommend: ' + writer['safe_meaning']
            if input_name != 'brief-request.json':
                if input_name == 'closure-input.json':
                    previous = sys.argv
                    output = io.StringIO()
                    try:
                        sys.argv = ['run_chain.py', str(folder)]
                        with redirect_stdout(output):
                            code = run_main()
                    finally:
                        sys.argv = previous
                    if code != 0:
                        return 'writer_input_blocked'
                    lines = output.getvalue().splitlines()
                    writer_console = len(lines) > 1 and lines[1] == writer_line and lines.count(writer_line) == 1
                    closure = json.loads((folder / 'closure.json').read_text())['closure']
                else:
                    result = run_chain(folder)
                    if result['exit_code']:
                        return 'writer_input_blocked:' + result['first_failure']['code']
                    closure = result['results']['closure']['closure']
                writer_closure = closure.get('added_by_writer') == ['cu-recommend']
        if case == "leak":
            shutil.copyfile(example / "known-bad/leak.md", folder / "piece.md")
        if case == "anchors":
            import json

            path = folder / "brief-request.json"
            request = json.loads(path.read_text())
            meaning = "Teams should move production services to the free-threaded build this year."
            request["content_boundaries"]["content_units"].append({
                "content_unit_id": "cu-migrate", "safe_meaning": meaning,
                "required": input_name == "brief-request.json",
                "evidence_anchor_ids": [], "alternative_ids": [], "limitation_ids": [],
                "model_row_ids": [],
            })
            if any('source' in row for row in request['content_boundaries']['content_units'][:-1]):
                request['content_boundaries']['content_units'][-1]['source'] = 'ai'
            planned = next(row for row in request["composition_plan"]["planned_units"]
                           if row["planned_unit_id"] == "u-recommend")
            planned["content_unit_ids"].append("cu-migrate")
            path.write_text(json.dumps(request))
            shared_path = folder / "shared-writing.json"
            shared = json.loads(shared_path.read_text())
            binding = next(row for row in shared["contract"]["unit_bindings"]
                           if row["planned_unit_id"] == "u-recommend")
            binding["content_unit_ids"].append("cu-migrate")
            shared_path.write_text(json.dumps(shared))
            piece = folder / "piece.md"
            piece.write_text(piece.read_text().rstrip("\n") + " " + meaning + "\n")
        if case == "ahead":
            import json

            request = json.loads((folder / "brief-request.json").read_text())
            rows = request["composition_plan"]["planned_units"]
            unit = copy.deepcopy(rows[-1])
            unit.update(
                planned_unit_id="u-libs",
                order=max(row["order"] for row in rows) + 1,
                title="Libraries",
                content_unit_ids=[],
                limitation_ids=[],
            )
            rows.append(unit)
            (folder / "brief-request.json").write_text(json.dumps(request))
            run_example_steps(folder, until="map")
            from _common import cli_validate
            from validate_shared_writing import validate_shared_writing

            previous = sys.argv
            try:
                sys.argv = [
                    "validate_shared_writing.py",
                    "--input",
                    str(folder / "shared-writing.json"),
                    "--output",
                    str(folder / "shared-writing-result.json"),
                ]
                binding_code = cli_validate(validate_shared_writing, "Bind the current text")
            finally:
                sys.argv = previous
            if binding_code == 0:
                raise AssertionError("ahead fixture unexpectedly bound every required unit")
        elif case != 'writer' and not (case == "anchors" and input_name == "brief-request.json"):
            run_example_steps(folder)
        import io, json
        from contextlib import redirect_stdout
        from show_plan import main

        previous = sys.argv
        output = io.StringIO()
        try:
            sys.argv = ["show_plan.py", "--input", str(folder / input_name), "--json"]
            with redirect_stdout(output):
                code = main()
        finally:
            sys.argv = previous
        if code not in (0, None):
            return "hidden"
        view = json.loads(output.getvalue())
        if case == 'writer':
            lines = render_plan(view).splitlines()
            return 'writer_shown' if (len(lines) > 1 and lines[1] == writer_line
                                      and lines.count(writer_line) == 1 and writer_closure and writer_console) else 'writer_hidden'
        if case == "anchors":
            lines = [line.strip() for line in render_plan(view).splitlines()]
            supported = next(row["safe_meaning"]
                             for row in request["content_boundaries"]["content_units"]
                             if row["content_unit_id"] == "cu-recommend")
            return "anchors_shown" if (
                f"says: {meaning} [no anchor]" in lines
                and f"says: {supported} [anc-314-supported (support), anc-314-phase3-undecided (limit)]" in lines
                and not any(line.startswith("anchors:") for line in lines)
            ) else "anchors_hidden"
        if case == "ahead":
            row = next((row for row in view["planned_units"] if row["planned_unit_id"] == "u-libs"), {})
            return (
                "ahead_shown"
                if row.get("new")
                and not row.get("bound")
                and "shared_writing: blocked" in view["summary"]
                else "hidden"
            )

        if case == "clean":
            return "clean" if all(unit["bound"] for unit in view["planned_units"]) else "unbound"
        shown = any(
            row.get("code") == "workflow_leak"
            for unit in view["planned_units"]
            for row in unit.get("findings", [])
        )
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
        from run_chain import run_chain
        run_chain(folder, until='audit')
        audit = json.loads((folder / "audit.json").read_text(encoding="utf-8"))["reader_audit"]
        if case == 'swapped' and (audit['status'] == 'passed' or audit['quality_dimensions']['plan_order'] != 'repair'):
            raise AssertionError('native order audit did not mark the swapped sections for repair')
        codes = {row["code"] for row in audit["findings"]}
        return "plan_order_mismatch" if "plan_order_mismatch" in codes else audit["status"]

    def _evidence(self, case):
        """Probe the public S1/S2 inputs and finite declared-response/scope controls."""
        import json
        from _common import load_request
        from run_chain import run_chain

        if case.endswith('_closure'):
            from reader_fill import fill_check_fingerprints, fill_closure_fingerprints
            from reader_checks import build_reader_audit_from_current

            # Tamper a current brief, preserving identities and recomputing actual
            # bindings/audit references so stale metadata cannot stand in for this gate.
            request = copy.deepcopy(self.closure_input(self.complete_chain(self._workdir())))
            brief = request['reader_brief']
            boundaries = brief['content_boundaries']
            unit = boundaries['content_units'][0]
            if case == 'missing_closure':
                unit['evidence_anchor_ids'] = []
            else:
                unit['safe_meaning'] = 'Free-threading will become the default build in the next Python release, so plan the migration for it.'
                unit['alternative_ids'] = []
                boundaries['alternatives'].append({
                    'alternative_id': 'alt-default-soon',
                    'safe_meaning': 'Free-threading will become the default in the next release.',
                    'status': 'unsupported', 'content_unit_ids': [unit['content_unit_id']],
                })
            brief.pop('brief_fingerprint')
            brief['brief_fingerprint'] = self.fingerprint(brief)
            shared = request['shared_writing']
            shared.pop('reader_brief_fingerprint', None)
            shared.pop('contract_fingerprint', None)
            fill_check_fingerprints(request)
            audit = request['deterministic_audit']
            request['deterministic_audit'] = build_reader_audit_from_current(
                audit_id=audit['audit_id'], amap=request['artifact_map'], brief=brief,
                contract=shared, audited_at=audit.get('audited_at'))
            for field in ('reader_brief_fingerprint', 'shared_writing_contract_fingerprint',
                          'deterministic_audit_fingerprint', 'judgment_fingerprint'):
                request['judgment'].pop(field, None)
            fill_closure_fingerprints(request)
            try:
                return self.derive_closure(request)['closure']['status']
            except self.validation_error as exc:
                return str(exc).split(':', 1)[0]

        folder = self._workdir()
        route = 'fiction' if case in ('nonresearch', 'research_folder') else 'academic' if case == 'academic_missing' else 'investigation'
        shutil.copytree(ROOT / 'skills/logic-writing/assets/examples' / route, folder)
        path = folder / 'brief-request.json'
        request = json.loads(path.read_text())
        boundaries = request['content_boundaries']
        if case == 'research_folder':
            example = ROOT / 'skills/logic-writing/assets/examples/investigation'
            request.update(research_folder=str(example / 'research'),
                           research_status=str(example / 'research-status.json'))
        elif case == 'academic_missing':
            boundaries['content_units'][0]['evidence_anchor_ids'] = []
        elif case not in ('context', 'nonresearch'):
            responses = {
                'restatement': 'Free-threading will become the default build in the next Python release, so plan the migration for it.',
                'qualified_answer': 'It is not established that free-threading will become the default in the next release.',
                'quoted_answer': 'The claim "Free-threading will become the default in the next release." is unsupported.',
                'rebutted_answer': 'We reject the claim that free-threading will become the default in the next release.',
            }
            meaning = responses.get(case, 'Teams should move production services to the free-threaded build this year.')
            identity = 'cu-default-next' if case in responses else 'cu-migrate'
            anchors = ['anc-314-supported'] if case in responses else []
            if case == 'counter_only':
                counter = dict(boundaries['evidence_anchors'][0], anchor_id='anc-counter', relation='counter',
                               outside_research='Synthetic counter-only probe, not a result of the research folder.')
                boundaries['evidence_anchors'].append(counter)
                anchors = ['anc-counter']
            unit = dict(content_unit_id=identity, safe_meaning=meaning, required=case != 'optional',
                        evidence_anchor_ids=anchors, alternative_ids=[], limitation_ids=[], model_row_ids=[])
            if any('source' in row for row in boundaries['content_units']):
                unit['source'] = 'ai'
            if case in ('qualified_answer', 'quoted_answer', 'rebutted_answer'):
                unit['alternative_ids'] = ['alt-default-soon']
            if case == 'reason':
                unit['unsupported_reason'] = 'The evidence does not support this recommendation; keep the gap visible.'
            boundaries['content_units'].append(unit)
            next(row for row in request['composition_plan']['planned_units']
                 if row['planned_unit_id'] == 'u-recommend')['content_unit_ids'].append(identity)
            shared_path = folder / 'shared-writing.json'
            shared = json.loads(shared_path.read_text())
            next(row for row in shared['contract']['unit_bindings']
                 if row['planned_unit_id'] == 'u-recommend')['content_unit_ids'].append(identity)
            shared_path.write_text(json.dumps(shared))
            piece = folder / 'piece.md'
            piece.write_text(piece.read_text().rstrip('\n') + ' ' + meaning + '\n')
        path.write_text(json.dumps(request))
        result = run_chain(folder, until='closure' if case == 'reason' else 'brief')
        if result['exit_code']:
            return result['first_failure']['code']
        if case == 'reason':
            closure = result['results']['closure']['closure']
            risk = any(row.get('defect_id') == 'unsupported:cu-migrate'
                       and row.get('reason') == unit['unsupported_reason']
                       for row in closure['residual_risk'])
            return 'passed+risk' if closure['status'] == 'passed' and risk else 'missing-risk'
        return 'passed'

    def apply_step(self, step) -> ReplayObservation:
        event = step.function_input
        state = self.state
        if event.kind == 'request':
            result = self._request(event.quality)
            state = replace(state, request_case=event.quality, request_result=result)
            self.state = state
            return ReplayObservation(function_name=step.function_name, observed_output=result, observed_state=state)
        if event.kind == 'anchor_authority':
            result = self._anchor_authority(event.quality)
            state = replace(state, authority_case=event.quality, authority_result=result)
            self.state = state
            return ReplayObservation(function_name=step.function_name,
                                     observed_output=result, observed_state=state)
        if event.kind == 'evidence':
            result = self._evidence(event.quality)
            state = replace(state, evidence_case=event.quality, evidence_result=result)
            self.state = state
            return ReplayObservation(function_name=step.function_name,
                                     observed_output=result, observed_state=state)
        if event.kind == "chain":
            import json
            from run_chain import run_chain

            folder = self._workdir()
            example = ROOT / "skills/logic-writing/assets/examples/investigation"
            shutil.copytree(example, folder)
            if event.quality == "repair":
                shutil.copyfile(example / "known-bad/leak.md", folder / "piece.md")
            result = run_chain(folder, until="audit")
            audit = json.loads((folder / "audit.json").read_text())["reader_audit"]
            native = "passed" if audit["status"] == "passed" else "failed"
            state = replace(state, chain_native_status=native, chain_reported_status=result["status"])
            self.state = state
            return ReplayObservation(
                function_name=step.function_name, observed_output="command", observed_state=state
            )
        if event.kind == "readback":
            fields = (
                {"readback_input": getattr(event, "input", "")}
                if hasattr(state, "readback_input")
                else {}
            )
            state = replace(
                state,
                readback_case=event.quality,
                readback=self._readback(
                    event.quality, getattr(event, "input", "") or "shared-writing-result.json"
                ),
                **fields
            )
            self.state = state
            return ReplayObservation(
                function_name=step.function_name, observed_output="read", observed_state=state
            )
        if event.kind == "order":
            state = replace(state, order_case=event.quality, order_audit=self._order(event.quality))
            self.state = state
            return ReplayObservation(
                function_name=step.function_name, observed_output="audited", observed_state=state
            )
        if event.kind == "import":
            relation = self._import(event.quality)
            fields = (
                {"report_fields_match": getattr(self, "import_fields_match", True)}
                if hasattr(state, "report_fields_match")
                else {}
            )
            state = replace(state, import_case=event.quality, relation=relation, **fields)
            self.state = state
            return ReplayObservation(
                function_name=step.function_name, observed_output="imported", observed_state=state
            )
        if event.kind in {"review", "self_review"}:
            # the actual text with a fresh ReaderBrief, ArtifactMap, audit, route review and ReaderJudgment
            chain = self.complete_chain(
                self._workdir(), state.owner, pass_quality=event.quality == "pass"
            )
            if event.kind == "self_review":
                judgment = copy.deepcopy(chain["judgment"])
                judgment["judge_kind"] = "self_review"
                judgment["judge_id"] = judgment["producer_id"]
                judgment.pop("judgment_fingerprint")
                judgment["judgment_fingerprint"] = self.fingerprint(judgment)
                chain["judgment"] = judgment
            self.chain = chain
            judgment = chain["judgment"]
            state = replace(
                state,
                owner=chain["route_decision"]["final_owner"],
                reviewed=True,
                current=True,
                quality="pass" if judgment["status"] == "passed" else "repair",
                independent=judgment["judge_kind"] == "independent_context",
                closure="",
                closure_owner="",
                broad_claim=False,
            )
            output = "reviewed"
        elif event.kind == "edit":
            if self.chain is not None:
                path = Path(self.chain["artifact_path"])
                path.write_text(
                    path.read_text(encoding="utf-8") + "\n\nA materially new paragraph.",
                    encoding="utf-8",
                )
            state = replace(state, current=False, closure="", closure_owner="", broad_claim=False)
            output = "edited"
        else:
            output, closure_owner, broad_claim = "rejected", state.owner, False
            if self.chain is not None:
                try:
                    closure = self.derive_closure(self.closure_input(self.chain))["closure"]
                    output, closure_owner, broad_claim = (
                        closure["status"],
                        closure["final_owner"],
                        closure["broad_claim_allowed"],
                    )
                except self.validation_error:
                    output = "rejected"
            state = replace(state, closure=output, closure_owner=closure_owner, broad_claim=broad_claim)
        self.state = state
        return ReplayObservation(
            function_name=step.function_name, observed_output=output, observed_state=state
        )

    def observe_state(self) -> State:
        return self.state

    def observe_output(self):
        return None
