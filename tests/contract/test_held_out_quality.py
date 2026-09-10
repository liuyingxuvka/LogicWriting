from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
SKILL_SCRIPTS = ROOT / "skills" / "logic-writing" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"logic_writing_{name}_held_out", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_skill(name: str):
    path = SKILL_SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"logic_writing_skill_{name}_held_out", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_planner_edge_aliases_are_canonicalised_before_native_depth():
    benchmark = _load("run_writing_quality_benchmark")
    nodes = {
        node_id: {"type": node_type, "text": node_id}
        for node_id, node_type in {
            "C0": "Claim", "E1": "Evidence", "W1": "Warrant",
            "A1": "Assumption", "L1": "Limitation", "R1": "Rebuttal",
        }.items()
    }
    result = benchmark._normalise_candidate_model(
        {
            "model": {},
            "nodes": nodes,
            "edges": [
                {"from": "E1", "to": "C0", "relation": "supports"},
                {"source": "W1", "target": "C0", "type": "supports"},
            ],
        },
        "edge-alias-test",
    )
    assert result["edges"] == [
        {"source": "E1", "target": "C0", "type": "supports"},
        {"source": "W1", "target": "C0", "type": "supports"},
    ]


def test_planner_node_role_aliases_are_canonicalised_and_conflicts_fail():
    benchmark = _load("run_writing_quality_benchmark")
    node_roles = {
        "C0": ("role", "Claim"),
        "E1": ("kind", "Evidence"),
        "W1": ("type", "Warrant"),
        "A1": ("role", "Assumption"),
        "L1": ("kind", "Limitation"),
        "R1": ("type", "Rebuttal"),
    }
    candidate = {
        "model": {},
        "nodes": [
            {"id": node_id, field: value, "text": node_id}
            for node_id, (field, value) in node_roles.items()
        ],
        "edges": [
            {"from": "E1", "to": "C0", "relation": "support"},
        ],
    }
    result = benchmark._normalise_candidate_model(candidate, "node-alias-test")
    assert {node_id: row["type"] for node_id, row in result["nodes"].items()} == {
        "C0": "Claim", "E1": "Evidence", "W1": "Warrant",
        "A1": "Assumption", "L1": "Limitation", "R1": "Rebuttal",
    }
    assert all("role" not in row and "kind" not in row for row in result["nodes"].values())
    assert result["edges"] == [{"source": "E1", "target": "C0", "type": "supports"}]

    conflicting = json.loads(json.dumps(candidate))
    conflicting["nodes"][0]["kind"] = "Evidence"
    with pytest.raises(ValueError, match="conflicting type aliases"):
        benchmark._normalise_candidate_model(conflicting, "node-alias-conflict")


def test_planner_alias_normalisation_rejects_unknown_roles_relations_and_endpoints():
    benchmark = _load("run_writing_quality_benchmark")
    nodes = {
        node_id: {"type": node_type, "text": node_id}
        for node_id, node_type in {
            "C0": "Claim", "E1": "Evidence", "W1": "Warrant",
            "A1": "Assumption", "L1": "Limitation", "R1": "Rebuttal",
        }.items()
    }
    base = {"model": {}, "nodes": nodes, "edges": [{"source": "E1", "target": "C0", "type": "supports"}]}
    unknown_role = json.loads(json.dumps(base))
    unknown_role["nodes"]["E1"]["role"] = "Observation"
    with pytest.raises(ValueError, match="unknown role/type"):
        benchmark._normalise_candidate_model(unknown_role, "unknown-role")

    unknown_relation = json.loads(json.dumps(base))
    unknown_relation["edges"][0]["relation"] = "illustrates"
    with pytest.raises(ValueError, match="unknown relation"):
        benchmark._normalise_candidate_model(unknown_relation, "unknown-relation")

    unknown_endpoint = json.loads(json.dumps(base))
    unknown_endpoint["edges"][0]["from"] = "E9"
    unknown_endpoint["edges"][0].pop("source")
    with pytest.raises(ValueError, match="unknown node"):
        benchmark._normalise_candidate_model(unknown_endpoint, "unknown-endpoint")


def test_research_and_compose_planner_payloads_fail_closed_on_missing_or_extra_fields():
    benchmark = _load("run_writing_quality_benchmark")
    compose_inputs = {
        "writing_request": {
            "reader_intent": {"intent_fingerprint": "sha256:" + "a" * 64, "extent": {"target": 1}},
        },
        "route_decision": {"final_owner": "investigation"},
        "content_boundaries": {"evidence_anchors": []},
        "native_plan": {"units": []},
    }
    valid_compose = {
        "central_question": "问题",
        "central_throughline": "主线",
        "opening_job": "开篇",
        "conclusion_job": "结尾",
    }
    with pytest.raises(ValueError, match="missing="):
        benchmark._normalise_compose_payload({key: value for key, value in valid_compose.items() if key != "opening_job"}, compose_inputs)
    with pytest.raises(ValueError, match="extra="):
        benchmark._normalise_compose_payload(dict(valid_compose, extra="不应出现"), compose_inputs)
    with pytest.raises(ValueError, match="non-empty string"):
        benchmark._normalise_compose_payload(dict(valid_compose, conclusion_job="  "), compose_inputs)

    candidate = {
        "model": {},
        "nodes": {
            node_id: {"type": node_type, "text": node_id}
            for node_id, node_type in {
                "C0": "Claim", "E1": "Evidence", "W1": "Warrant",
                "A1": "Assumption", "L1": "Limitation", "R1": "Rebuttal",
            }.items()
        },
        "edges": [{"source": "E1", "target": "C0", "type": "supports"}],
    }
    request = {
        "reader_intent": {"purpose": "fallback purpose"},
        "terminal_deliverable": {"kind": "report"},
    }
    with pytest.raises(ValueError, match="target_goal"):
        benchmark._normalise_research_payload({"candidate_model": candidate}, token="missing-goal", request=request)


def test_compose_compiler_projects_route_reader_spine_and_preserves_explicit_structure():
    benchmark = _load("run_writing_quality_benchmark")
    from reader_pipeline import validate_composition_plan, validate_route_composition

    cases, _, _, _, _ = benchmark._load_held_out_inputs(ROOT / "tests" / "fixtures" / "writing_quality")
    by_id = {case["case_id"]: case for case in cases}
    for case_id, expected_count in (("H-I", 5), ("H-A", 2), ("H-F", 4), ("H-T", 4)):
        request, boundaries, token = benchmark._production_request_and_boundaries(by_id[case_id])
        decision = {"final_owner": by_id[case_id]["route"]}
        payload = benchmark._normalise_compose_payload(
            {
                "central_question": "当前材料能支持什么判断？",
                "central_throughline": "结论必须沿着观察、边界和行动推进。",
                "opening_job": "先让读者知道问题。",
                "conclusion_job": "最后给出边界和下一步。",
            },
            {
                "writing_request": request,
                "route_decision": decision,
                "content_boundaries": boundaries,
                "native_plan": {"units": [{"unit_id": "u0"}]},
            },
        )
        plan = payload["composition_plan"]
        units = plan["planned_units"]
        assert len(units) == expected_count
        assert units[0]["planned_unit_id"] == "unit:answer"
        assert all(unit["source_outline_ids"] == ["outline:answer"] for unit in units)
        assert all(
            unit["downstream_unit_ids"] == ([units[index + 1]["planned_unit_id"]] if index + 1 < len(units) else [])
            for index, unit in enumerate(units)
        )
        assert payload["native_handoff_mapping"][0]["planned_unit_ids"] == [unit["planned_unit_id"] for unit in units]
        validate_composition_plan(
            plan,
            reader_intent=request["reader_intent"],
            content_unit_ids=[row["content_unit_id"] for row in boundaries["content_units"]],
            limitation_ids=[row["limitation_id"] for row in boundaries["limitations"]],
        )
        validate_route_composition(
            payload["route_composition"],
            owner=by_id[case_id]["route"],
            reader_intent_fingerprint=request["reader_intent"]["intent_fingerprint"],
            composition_plan_fingerprint=plan["plan_fingerprint"],
            composition_plan=plan,
            content_boundaries=boundaries,
        )

    generic_intent = {
        "purpose": "给出完整、自然、有证据边界的成品",
        "language": "zh-CN",
        "extent": {"target": 240},
        "structure": {"requested_outline": [{"outline_id": "outline:answer"}]},
    }
    assert benchmark._requested_composition_unit_count(generic_intent, "investigation") == 1


def test_restricted_fiction_ending_without_knowledge_path_is_blocked_before_writer():
    benchmark = _load("run_writing_quality_benchmark")
    request = {
        "reader_intent": {
            "purpose": "按给定信息写受限视角场景，结尾保留搭档失去工作的代价。",
            "language": "zh-CN",
            "extent": {"target": 300},
            "structure": {"requested_outline": [{"outline_id": "outline:answer"}]},
            "list_policy": "prose_default",
            "artifact_mode": "create_new",
            "forbidden_content": [],
            "intent_fingerprint": "sha256:" + "a" * 64,
        },
        "terminal_deliverable": {"kind": "short_story"},
    }
    boundaries = {
        "limitations": [{
            "limitation_id": "limitation:native:L1",
            "safe_meaning": "材料未提供陈舟获知搭档失去工作的方式；不能靠作者解释补足。",
        }],
        "content_units": [{"content_unit_id": "content:materials"}],
        "evidence_anchors": [],
    }
    with pytest.raises(ValueError, match="composition_blocked:user_decision:fiction_viewpoint_outcome_gap"):
        benchmark._normalise_compose_payload(
            {
                "central_question": "如何在受限视角下完成场景？",
                "central_throughline": "保留代价但不越过可知范围。",
                "opening_job": "建立压力。",
                "conclusion_job": "保留代价。",
            },
            {
                "writing_request": request,
                "route_decision": {"final_owner": "fiction-writing"},
                "content_boundaries": boundaries,
                "native_plan": {"units": [{"unit_id": "u0"}]},
            },
        )


def test_native_limitation_gets_a_visible_composition_placement():
    benchmark = _load("run_writing_quality_benchmark")
    request = {
        "reader_intent": {
            "purpose": "根据证据写一篇有边界的调查报告。",
            "language": "zh-CN",
            "extent": {"target": 300},
            "structure": {"requested_outline": [{"outline_id": "outline:answer"}]},
            "list_policy": "prose_default",
            "artifact_mode": "create_new",
            "forbidden_content": [],
            "intent_fingerprint": "sha256:" + "b" * 64,
        },
        "terminal_deliverable": {"kind": "research_report"},
    }
    boundaries = {
        "limitations": [{
            "limitation_id": "limitation:native:L1",
            "safe_meaning": "材料只覆盖当前样本范围。",
            "materiality": "changes_scope",
        }],
        "content_units": [{"content_unit_id": "content:materials"}],
        "evidence_anchors": [],
    }
    payload = benchmark._normalise_compose_payload(
        {
            "central_question": "当前证据能支持什么？",
            "central_throughline": "只在样本范围内解释。",
            "opening_job": "先回答问题。",
            "conclusion_job": "收束边界。",
        },
        {
            "writing_request": request,
            "route_decision": {"final_owner": "investigation"},
            "content_boundaries": boundaries,
            "native_plan": {"units": [{"unit_id": "u0"}]},
        },
    )
    last = payload["composition_plan"]["planned_units"][-1]["planned_unit_id"]
    assert payload["composition_plan"]["planned_units"][-1]["limitation_ids"] == ["limitation:native:L1"]
    assert payload["composition_plan"]["limitation_dispositions"][0]["destination_unit_ids"] == [last]


def _valid_single(benchmark, *, artifact_fingerprint: str = "sha256:" + "a" * 64) -> dict:
    return {
        "schema_version": "logic-writing.local-single-judgment.v1",
        "artifact_fingerprint": artifact_fingerprint,
        "reverse_outline": [
            {"unit": "paragraph-1", "excerpt": "具体原文摘录", "function": "回答任务", "forward_link": "交给下一段"}
        ],
        "obligation_results": [
            {"obligation_id": "O1", "status": "passed", "unit": "paragraph-1", "excerpt": "具体原文摘录", "reason": "可回指"}
        ],
        "scores": {dimension: 4 for dimension in benchmark.DIMENSIONS},
        "defects": [],
        "required_repairs": [],
    }


def test_held_out_manifest_is_four_fixed_cases_without_prompt_oracle_leak():
    benchmark = _load("run_writing_quality_benchmark")
    cases, rubric, input_fp, source_fp, files = benchmark._load_held_out_inputs(ROOT / "tests" / "fixtures" / "writing_quality")
    assert [case["case_id"] for case in cases] == list(benchmark.HELD_OUT_CASE_IDS)
    assert all("oracle" in case for case in cases)
    assert all("oracle" not in json.dumps(case["model_input"], ensure_ascii=False) for case in cases)
    assert "X" not in rubric and "preference" not in rubric
    assert input_fp.startswith("sha256:")
    assert source_fp.startswith("sha256:")
    assert files == {"held-out-manifest.json": input_fp}


def test_held_out_public_request_redacts_oracle_and_rubric_metadata():
    benchmark = _load("run_writing_quality_benchmark")
    cases, *_ = benchmark._load_held_out_inputs(ROOT / "tests" / "fixtures" / "writing_quality")
    public = benchmark._public_held_out_case_request(cases[0])
    assert set(public) == {"case_id", "route", "language", "task", "constraints", "materials"}
    assert "oracle" not in json.dumps(public, ensure_ascii=False)
    assert "rubric" not in json.dumps(public, ensure_ascii=False)
    assert public["materials"] == cases[0]["model_input"]["materials"]


def test_held_out_plan_has_four_writers_eight_judges_and_separate_planners():
    benchmark = _load("run_writing_quality_benchmark")
    cases, *_ = benchmark._load_held_out_inputs(ROOT / "tests" / "fixtures" / "writing_quality")
    plan = {"benchmark_id": "logic-writing-held-out-4x1x2"}
    ledger = benchmark._build_planned_ledger(
        cases,
        plan,
        repeats_count=1,
        versions=(benchmark.HELD_OUT_VERSION,),
        mode="held_out",
    )
    assert len(ledger["jobs"]) == 12
    assert sum(item["role"] == "writer" for item in ledger["jobs"]) == 4
    judges = [item for item in ledger["jobs"] if item["role"] == "judge"]
    assert len(judges) == 8
    assert all(item["evaluation_mode"] == "single" for item in judges)


def test_single_judgment_rejects_pair_fields_and_missing_text_location():
    benchmark = _load("run_writing_quality_benchmark")
    payload = _valid_single(benchmark)
    assert benchmark._validate_single_judgment_payload(payload)["schema_version"] == "logic-writing.local-single-judgment.v1"
    pair_payload = dict(payload, preference="X")
    with pytest.raises(ValueError, match="pair-comparison"):
        benchmark._validate_single_judgment_payload(pair_payload)
    missing_location = json.loads(json.dumps(payload))
    missing_location["reverse_outline"][0].pop("excerpt")
    with pytest.raises(ValueError, match="text location"):
        benchmark._validate_single_judgment_payload(missing_location)


def test_single_judgment_accepts_repair_and_obligation_binding_on_defects():
    benchmark = _load("run_writing_quality_benchmark")
    payload = _valid_single(benchmark)
    payload["scores"]["structure_fidelity"] = 3
    payload["defects"] = [{
        "obligation_id": "O7",
        "severity": "repair",
        "unit": "paragraph-2",
        "excerpt": "原文中的问题句",
        "reason": "该句没有完成任务要求的失败分支。",
        "repair": "补足与前文条件相连的可执行退回安排。",
    }]
    payload["required_repairs"] = [{
        "unit": "paragraph-2",
        "repair": "补足与前文条件相连的可执行退回安排。",
    }]

    validated = benchmark._validate_single_judgment_payload(payload)

    assert validated["defects"][0]["obligation_id"] == "O7"
    assert validated["defects"][0]["repair"]


def test_single_judgment_allows_defect_repair_to_remain_optional():
    benchmark = _load("run_writing_quality_benchmark")
    payload = _valid_single(benchmark)
    payload["defects"] = [{
        "unit": "paragraph-1",
        "excerpt": "原文中的问题句",
        "reason": "该句存在缺陷。",
    }]
    payload["required_repairs"] = [{
        "unit": "paragraph-1",
        "repair": "补足该句缺少的逻辑连接。",
    }]

    validated = benchmark._validate_single_judgment_payload(payload)

    assert "repair" not in validated["defects"][0]
    assert validated["required_repairs"][0]["repair"]


def test_single_judgment_rejects_blank_optional_defect_repair():
    benchmark = _load("run_writing_quality_benchmark")
    payload = _valid_single(benchmark)
    payload["defects"] = [{
        "unit": "paragraph-1",
        "excerpt": "原文中的问题句",
        "reason": "该句存在缺陷。",
        "repair": "  ",
    }]

    with pytest.raises(ValueError, match="defect repair"):
        benchmark._validate_single_judgment_payload(payload)


def test_single_judge_prompt_declares_exact_repair_fields():
    benchmark = _load("run_writing_quality_benchmark")
    cases, rubric, *_ = benchmark._load_held_out_inputs(ROOT / "tests" / "fixtures" / "writing_quality")
    prompt = benchmark._single_judge_prompt(
        cases[0],
        rubric,
        {
            "artifact_text": "一段真实成稿。",
            "artifact_fingerprint": "sha256:" + "a" * 64,
        },
    )
    assert '"required_repairs":[{"unit":"paragraph-1","repair"' in prompt
    assert "只能包含 unit 和 repair 两个字段" in prompt
    assert "不要使用 action" in prompt


def test_held_out_quality_gate_requires_both_independent_reviews_and_core_scores():
    benchmark = _load("run_writing_quality_benchmark")
    valid = _valid_single(benchmark)
    assert benchmark._held_out_quality_passes([valid, valid], artifact_fingerprint=valid["artifact_fingerprint"])
    assert not benchmark._held_out_quality_passes([valid], artifact_fingerprint=valid["artifact_fingerprint"])
    low = json.loads(json.dumps(valid))
    low["scores"]["structure_fidelity"] = 3
    assert not benchmark._held_out_quality_passes([valid, low], artifact_fingerprint=valid["artifact_fingerprint"])
    wrong_hash = json.loads(json.dumps(valid))
    wrong_hash["artifact_fingerprint"] = "sha256:" + "b" * 64
    assert not benchmark._held_out_quality_passes([valid, wrong_hash], artifact_fingerprint=valid["artifact_fingerprint"])


def test_owner_selection_rejects_ambiguous_holdout_combinations():
    owner = _load("run_reader_acceptance_owner")
    assert owner.resolve_quality_selection(held_out_only=True, preflight_case=None, repeats=None)[0] == "held_out"
    assert owner.resolve_quality_selection(held_out_only=False, preflight_case="I01", repeats=1) == ("preflight", "I01", 1)
    with pytest.raises(ValueError, match="preflight"):
        owner.resolve_quality_selection(held_out_only=True, preflight_case="I01", repeats=None)
    with pytest.raises(ValueError, match="repeats"):
        owner.resolve_quality_selection(held_out_only=True, preflight_case=None, repeats=1)
    with pytest.raises(ValueError, match="preflight-case"):
        owner.resolve_quality_selection(held_out_only=False, preflight_case=None, repeats=1)


def test_producer_cli_help_exposes_holdout_and_preflight_controls():
    owner = _load("run_reader_acceptance_owner")
    # This is a source-level assertion for the public entrypoint; invoking the
    # producer itself would start the local model and is intentionally outside
    # this contract test.
    source = Path(owner.__file__).read_text(encoding="utf-8")
    assert "--held-out-only" in source
    assert "--preflight-case" in source
    assert "--repeats" in source


def test_quality_consumer_signature_exposes_held_out_root():
    consumer = _load("check_writing_quality_run")
    assert "held_out_run_root" in consumer.check.__annotations__ or "held_out_run_root" in Path(consumer.__file__).read_text(encoding="utf-8")


def test_single_reader_execution_record_binds_one_writer_context_without_pair_shaping():
    execution = _load_skill("reader_execution")
    artifact_fp = "sha256:" + "a" * 64
    request = {
        "request_id": "judge:H-I:1:1",
        "run_id": "judge:H-I:1:1",
        "parent_orchestrator_run_id": "orchestrator:test",
        "reader_intent_fingerprint": "sha256:" + "b" * 64,
        "writer_input_fingerprint": "sha256:" + "c" * 64,
        "artifact_fingerprint": artifact_fp,
        "rubric_fingerprint": "sha256:" + "d" * 64,
        "evaluation_mode": "single",
        "pair_inputs": [],
        "writer_context_ids": ["writer-context"],
        "settings": {},
    }
    result = {
        "run_id": request["run_id"],
        "context_id": "judge-context",
        "parent_orchestrator_run_id": request["parent_orchestrator_run_id"],
        "model_id": "gpt-6-astra",
        "started_at": "2026-09-09T00:00:00Z",
        "finished_at": "2026-09-09T00:01:00Z",
        "provider_completion_ref": "local:test",
        "terminal_status": "completed",
        "output": "{}",
        "independence_status": "verified",
        "writer_context_ids": ["writer-context"],
    }
    record = execution._record_from_result(request, result, role="judge", backend_id="local:test")
    assert record["evaluation_mode"] == "single"
    assert record["pair_inputs"] == []
    assert record["input_artifact_fingerprint"] == artifact_fp
    execution.validate_execution_record(record, lambda _record: {"writer_context_ids": ["writer-context"]})
