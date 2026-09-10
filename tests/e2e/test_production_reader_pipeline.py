"""Synthetic process-boundary protocol tests, not prose-quality evidence.

The real reader projection/validation chain runs; native console and planner
captures are deterministic test doubles. No writer, judge, installed provider,
or real recursive research qualification is executed by these tests.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from _common import ValidationError, fingerprint, fingerprint_without
from build_source_unit_manifest import fingerprint_bytes
import production_reader_pipeline as pipeline
from tests.contract.test_researchguard_handoff import _plan as native_plan_fixture
from tests.v2_support import make_reader_chain


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    def make(owner="investigation", native_status="research_handoff_ready", mutation=None):
        chain = make_reader_chain(tmp_path / ("fixture-" + owner), owner=owner)
        request = {"schema_version": "2.0", "request_id": "request:unseen-topic",
                   "reader_intent": chain["intent"], "terminal_deliverable": chain["route_decision"]["terminal_deliverable"]}
        request["request_fingerprint"] = fingerprint(request)
        boundaries = chain["reader_brief"]["content_boundaries"]
        calls = []
        plan = native_plan_fixture(status=native_status)
        receipt = {"receipt_version": "researchguard.logic.depth.v3", "status": "pass", "model_id": plan["model_id"],
                   "model_fingerprint": plan["model_fingerprint"], "unresolved_gaps": [], "untested_high_impact_node_ids": [],
                   "claim_boundary": "Synthetic protocol fixture only."}
        monkeypatch.setattr(pipeline.InstalledResearchGuardProvider, "_console", lambda self: ("synthetic-console", {"provider_id": "researchguard", "version": "0.5.1", "test_mode": "protocol_only"}))

        def fake_run(self, console, args, output, *, cwd):
            calls.append(args[1] if args[0] == "guard-contract" else args[0])
            assert console == "synthetic-console"
            if args[0] == "guard-contract":
                if args[1] == "freeze":
                    assert not (cwd / "model.json").exists()
                    pipeline._write(cwd / "guard-contract.json", {"synthetic": "frozen contract"})
                else:
                    assert (cwd / "model.json").is_file()
                value = {"synthetic": args[1]}
            elif args[0] == "depth":
                assert args[2:5] == ["--target-root", str(cwd), "--guard-contract"]
                value = copy.deepcopy(receipt)
            else:
                assert args[0] == "synthesize"
                selection = json.loads(Path(args[3]).read_text(encoding="utf-8"))
                assert Path(selection["native_depth_receipt_ref"]).is_file()
                assert selection["model_fingerprint"] == receipt["model_fingerprint"]
                value = copy.deepcopy(plan)
            pipeline._write(output, value)
            return value

        monkeypatch.setattr(pipeline.InstalledResearchGuardProvider, "_run", fake_run)

        def planner(*, stage, inputs, evidence_root):
            calls.append(stage)
            assert "case_id" not in inputs and "rubric" not in inputs
            if stage == "research":
                payload = {"guard_declaration": {"candidate_relative_path": "model.json"}, "candidate_model": {"synthetic": "model"}, "support_files": {},
                           "selection_request": {"schema": "researchguard.logic.synthesis-request.v1"}, "budget": 20}
            else:
                assert calls[:5] == ["research", "freeze", "bind", "depth", "synthesize"]
                assert inputs["native_plan"] == plan
                payload = {"composition_plan": copy.deepcopy(chain["plan"]), "route_composition": copy.deepcopy(chain["route_composition"]),
                           "native_handoff_mapping": [{"native_unit_id": "unit:root", "planned_unit_ids": ["unit:answer"],
                                                       "disposition": "body", "reason": "Consume the bounded native conclusion."}]}
            if mutation:
                mutation(stage, payload, inputs, evidence_root)
            raw = evidence_root / f"raw-{stage}.json"
            pipeline._write(raw, payload)
            capture_dir = evidence_root / f"planner-{stage}-capture"
            capture_dir.mkdir()
            capture = capture_dir / "output.txt"
            capture.write_text(f"synthetic planner capture for {stage}\n", encoding="utf-8")
            events = capture_dir / "events.jsonl"
            context_id = f"synthetic-context:{stage}"
            events.write_text(
                "\n".join(
                    json.dumps(event, sort_keys=True)
                    for event in (
                        {"type": "thread.started", "thread_id": context_id},
                        {"type": "turn.started"},
                        {"item": {"type": "agent_message", "text": "synthetic planner result"}},
                        {"type": "turn.completed"},
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            return {"payload": payload, "execution_record": {
                    "schema_version": "logic-writing.planner-execution-record.v1",
                    "run_id": f"planner:{stage}:synthetic",
                    "context_id": context_id,
                    "input_fingerprint": fingerprint(inputs),
                    "raw_output_locator": str(raw),
                    "raw_output_fingerprint": fingerprint_bytes(raw.read_bytes()),
                    "backend_id": "synthetic-planner",
                    "backend_capture_locator": str(capture),
                    "backend_capture_fingerprint": fingerprint_bytes(capture.read_bytes()),
                    "terminal_status": "completed",
                    "claim_scope": "protocol_only"}}

        return {"request": request, "boundaries": boundaries, "planner": planner, "calls": calls, "receipt": receipt, "plan": plan}

    return make


def execute(case, path, *, provider=None):
    return pipeline.prepare_production_reader_input(case["request"], native_provider=provider or pipeline.InstalledResearchGuardProvider(),
             planner_backend=case["planner"], frozen_content_boundaries=case["boundaries"], evidence_root=path)


def test_native_limitation_is_promoted_into_current_reader_boundary(scenario):
    case = scenario()
    enriched, promoted = pipeline._merge_native_limitations(
        case["boundaries"],
        {
            "selected_items": [{
                "node_id": "L1",
                "node_type": "Limitation",
                "text": "材料没有提供受限视角人物获知结局的方式。",
            }],
        },
    )
    assert [row["limitation_id"] for row in promoted] == ["limitation:native:L1"]
    assert enriched["limitations"][-1]["affected_content_unit_ids"] == ["content:answer"]
    assert case["boundaries"].get("limitations") == []


@pytest.mark.parametrize("owner", ["investigation", "academic-writing", "fiction-writing", "travel-guide"])
def test_unseen_request_runs_native_then_composition_and_exact_writer_projection(scenario, tmp_path, owner):
    case = scenario(owner)
    result = execute(case, tmp_path / "run")
    assert result["status"] == "ready_for_writer"
    assert case["calls"] == ["research", "freeze", "bind", "depth", "synthesize", "compose"]
    brief = json.loads(Path(result["refs"]["reader_brief"]["locator"]).read_text(encoding="utf-8"))
    assert result["writer_input"] == brief["writer_input"]
    assert result["writer_input_fingerprint"] == brief["writer_input_fingerprint"] == fingerprint(result["writer_input"])
    assert result["writer_input"]["native_handoff"]["native_result_fingerprint"] == fingerprint(case["plan"])
    spine = json.loads(Path(result["refs"]["reader_spine"]["locator"]).read_text(encoding="utf-8"))
    assert result["reader_spine"] == spine
    assert result["reader_spine_fingerprint"] == fingerprint(spine)
    assert result["reader_spine_schema"] == pipeline.READER_SPINE_SCHEMA
    assert all(Path(ref["locator"]).is_file() for ref in result["refs"].values())
    assert "prose quality" in result["claim_boundary"]


def test_case_label_is_not_a_production_input(scenario, tmp_path):
    case = scenario()
    case["request"]["case_id"] = "I01"
    case["request"]["request_fingerprint"] = fingerprint_without(case["request"], "request_fingerprint")
    with pytest.raises((ValidationError, ValueError)):
        execute(case, tmp_path / "run")
    assert not case["calls"]


def test_arbitrary_provider_cannot_supply_caller_authored_pass(scenario, tmp_path):
    case = scenario()
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="native_provider_invalid"):
        execute(case, tmp_path / "run", provider=object())
    assert not case["calls"]


def test_important_unresolved_descendant_blocks_before_compose(scenario, tmp_path):
    case = scenario()
    case["receipt"]["unresolved_gaps"] = ["important-grandchild:missing-evidence"]
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="native_depth_blocked"):
        execute(case, tmp_path / "run")
    assert case["calls"] == ["research", "freeze", "bind", "depth"]
    assert not (tmp_path / "run" / "production-reader-input.json").exists()


def test_native_blocked_plan_cannot_become_writer_ready(scenario, tmp_path):
    case = scenario(native_status="blocked_support_gap")
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="native_synthesis_blocked"):
        execute(case, tmp_path / "run")
    assert "compose" not in case["calls"]


def test_native_plan_and_receipt_must_bind_same_model(scenario, tmp_path):
    case = scenario()
    case["plan"]["model_id"] = "foreign:model"
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="native_plan_receipt_mismatch"):
        execute(case, tmp_path / "run")


def test_caller_receipt_cannot_replace_native_execution(scenario, tmp_path):
    def mutate(stage, payload, inputs, root):
        if stage == "research":
            payload["selection_request"]["native_depth_receipt_ref"] = "forged-pass.json"
    case = scenario(mutation=mutate)
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="caller-supplied depth receipt"):
        execute(case, tmp_path / "run")
    assert case["calls"] == ["research"]


def test_native_input_cannot_escape_private_evidence(scenario, tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    def mutate(stage, payload, inputs, root):
        if stage == "research":
            payload["guard_declaration"]["candidate_relative_path"] = str(outside)
    case = scenario(mutation=mutate)
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="native_input_path_invalid"):
        execute(case, tmp_path / "run")


@pytest.mark.parametrize("mutation_kind", ["remove_receipt", "change_receipt", "change_model"])
def test_native_artifacts_reopened_after_composition(scenario, tmp_path, mutation_kind):
    def mutate(stage, payload, inputs, root):
        if stage == "compose":
            path = root / ("target/model.json" if mutation_kind == "change_model" else "native-depth-receipt.json")
            if mutation_kind == "remove_receipt":
                path.unlink()
            else:
                path.write_text('{"forged":true}', encoding="utf-8")
    case = scenario(mutation=mutate)
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="native_input_path_invalid|production_input_stale"):
        execute(case, tmp_path / "run")


def test_partial_native_mapping_fails_existing_contract(scenario, tmp_path):
    def mutate(stage, payload, inputs, root):
        if stage == "compose":
            payload["native_handoff_mapping"] = []
    case = scenario(mutation=mutate)
    with pytest.raises(ValidationError, match="mapping"):
        execute(case, tmp_path / "run")


def test_stale_composition_plan_fails_before_writer_projection(scenario, tmp_path):
    def mutate(stage, payload, inputs, root):
        if stage == "compose":
            payload["composition_plan"]["central_throughline"] = "Changed after the planner fingerprint was frozen."
    case = scenario(mutation=mutate)
    with pytest.raises(ValidationError):
        execute(case, tmp_path / "run")
    assert not (tmp_path / "run" / "production-reader-input.json").exists()


def test_unavailable_installed_console_fails_without_an_alternate_lookup(monkeypatch):
    monkeypatch.setattr(pipeline.provider_preflight, "preflight", lambda member: {"status": "provider_unavailable"})
    monkeypatch.setattr(pipeline.provider_preflight, "_researchguard_distribution", lambda: pytest.fail("no lookup after failed preflight"))
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="native_provider_unavailable"):
        pipeline.InstalledResearchGuardProvider()._console()


def test_wrong_installed_package_version_is_not_accepted(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(pipeline.provider_preflight, "preflight", lambda member: {"status": "current_pass"})
    monkeypatch.setattr(pipeline.provider_preflight, "_researchguard_distribution", lambda: SimpleNamespace(version="0.4.11"))
    monkeypatch.setattr(pipeline.provider_preflight, "_researchguard_console", lambda distribution: "synthetic-console")
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="native_provider_identity_mismatch"):
        pipeline.InstalledResearchGuardProvider()._console()


def test_planner_raw_capture_must_match_returned_payload(scenario, tmp_path):
    case = scenario()
    original = case["planner"]
    def wrong_capture(**kwargs):
        result = original(**kwargs)
        result["payload"]["budget"] = 999
        return result
    case["planner"] = wrong_capture
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="planner_payload_mismatch"):
        execute(case, tmp_path / "run")


def test_planner_rejects_quality_metadata_inside_frozen_boundaries(scenario, tmp_path):
    case = scenario()
    case["boundaries"]["content_units"][0]["rubric"] = "hidden judge criterion"
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="planner_input_forbidden_field"):
        execute(case, tmp_path / "run")
    assert not case["calls"]


def test_planner_cannot_mutate_the_frozen_input_snapshot(scenario, tmp_path):
    case = scenario()
    original = case["planner"]

    def mutating_planner(**kwargs):
        kwargs["inputs"]["content_boundaries"]["content_units"][0]["safe_meaning"] = "forged"
        return original(**kwargs)

    case["planner"] = mutating_planner
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="planner_input_mutated"):
        execute(case, tmp_path / "run")
    assert case["calls"] == ["research"]


def test_planner_requires_backend_capture_lineage(scenario, tmp_path):
    case = scenario()
    original = case["planner"]

    def incomplete_record(**kwargs):
        result = original(**kwargs)
        result["execution_record"].pop("backend_capture_locator")
        return result

    case["planner"] = incomplete_record
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="planner_lineage_incomplete"):
        execute(case, tmp_path / "run")


def test_planner_tool_event_is_blocked_by_execution_lineage(scenario, tmp_path):
    case = scenario()
    original = case["planner"]

    def tool_using_planner(**kwargs):
        result = original(**kwargs)
        capture = Path(result["execution_record"]["backend_capture_locator"])
        capture.with_name("events.jsonl").write_text(
            json.dumps({"item": {"type": "command_execution", "command": "dir"}}) + "\n",
            encoding="utf-8",
        )
        return result

    case["planner"] = tool_using_planner
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="planner_tools_forbidden"):
        execute(case, tmp_path / "run")


def test_previous_evidence_root_is_never_overwritten(scenario, tmp_path):
    case = scenario()
    root = tmp_path / "run"
    root.mkdir()
    (root / "old-receipt.json").write_text("{}", encoding="utf-8")
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="evidence_root_not_empty"):
        execute(case, root)
    assert not case["calls"]
