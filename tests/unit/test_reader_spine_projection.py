"""Focused reader-spine projection and diagnostic checks.

These tests exercise the deterministic projection contract.  They do not run
an installed provider or treat synthetic reader text as quality-benchmark
evidence.
"""

from __future__ import annotations

import copy

import pytest

from _common import fingerprint, fingerprint_without
import production_reader_pipeline as pipeline
from reader_pipeline import build_reader_brief
from tests.v2_support import make_reader_chain, make_route_composition


def _brief_with_boundaries(chain: dict, boundaries: dict, plan: dict | None = None) -> dict:
    current_plan = copy.deepcopy(plan or chain["plan"])
    route = make_route_composition(chain["route_decision"]["final_owner"], chain["intent"], current_plan)
    return build_reader_brief(
        route_decision=chain["route_decision"],
        content_boundaries=boundaries,
        composition_plan=current_plan,
        route_composition=route,
        native_dependency_receipt_fingerprints=[fingerprint({"native": "current-pass"})],
        content_authority_fingerprints={
            str(row["content_unit_id"]): fingerprint({"content": row["content_unit_id"]})
            for row in boundaries["content_units"]
        },
        brief_id="brief:reader-spine-focused",
    )


def test_reader_spine_is_minimal_ordered_and_keeps_full_input_private(tmp_path):
    chain = make_reader_chain(tmp_path / "chain")
    brief = chain["reader_brief"]
    spine = pipeline.build_reader_spine(brief, composition_plan=chain["plan"])

    assert spine["schema_version"] == pipeline.READER_SPINE_SCHEMA
    assert spine["root_question"] == chain["plan"]["central_question"]
    assert spine["root_conclusion"] == chain["plan"]["central_throughline"]
    assert [row["planned_unit_id"] for row in spine["major_units"]] == ["unit:answer"]
    assert spine["editorial_dispositions"] == [{
        "content_unit_id": "content:answer",
        "planned_unit_ids": ["unit:answer"],
        "disposition": "support",
    }]
    assert "writer_input" not in spine
    assert "selected_content" not in spine
    assert "route_semantics" not in spine
    assert "gaps" not in spine
    assert "model_row_ids" not in str(spine)
    pipeline.validate_reader_spine(spine)
    prompt = pipeline.render_reader_spine_prompt(spine)
    assert '"selected_content"' not in prompt
    assert '"route_semantics"' not in prompt
    assert '"gaps"' not in prompt

    # The immutable card-level input is still available for the private
    # receipt, but it cannot be mistaken for a reader-spine source.
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="reader_spine_source_invalid"):
        pipeline.build_reader_spine(brief["writer_input"])
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="reader_spine_non_minimal"):
        pipeline.validate_reader_spine(brief["writer_input"])
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="reader_spine_non_minimal"):
        pipeline.render_reader_spine_prompt({**spine, "writer_input": brief["writer_input"]})


def test_reader_spine_projects_route_guidance_for_each_terminal_owner(tmp_path):
    expected_keys = {
        "investigation": {"mode", "profile", "bounded_answer", "evidence_strength", "alternatives", "recheck_conditions"},
        "academic-writing": {"mode", "profile", "research_question", "central_contribution", "hierarchy", "figure_table_jobs"},
        "fiction-writing": {"mode", "profile", "voice_contract", "movements", "unit_plans", "promises_and_reveals", "realization_boundaries"},
        "travel-guide": {"mode", "profile", "traveler_conditions", "pace_and_timing", "local_names", "reachable_fallbacks", "source_and_recheck_placement"},
    }
    for owner in expected_keys:
        chain = make_reader_chain(tmp_path / owner, owner)
        spine = pipeline.build_reader_spine(chain["reader_brief"], composition_plan=chain["plan"])
        guidance = spine["route_guidance"]
        assert set(guidance) == expected_keys[owner]
        assert guidance["mode"] == owner
        assert "route_semantics" not in str(guidance)
        assert "route_payloads" not in str(guidance)
        assert "source_refs" not in str(guidance)
        pipeline.validate_reader_spine(spine)


def test_reader_spine_keeps_selected_constraints_without_authority_metadata(tmp_path):
    chain = make_reader_chain(tmp_path / "constraints")
    boundaries = copy.deepcopy(chain["reader_brief"]["content_boundaries"])
    boundaries["citation_duties"] = [{
        "citation_id": "citation:one",
        "content_unit_ids": ["content:answer"],
        "source_id": "source:synthetic",
        "marker": "[1]",
        "placement": "same_sentence",
    }]
    boundaries["must_preserve_tokens"] = [{
        "token_id": "token:one",
        "token": "ReaderIntent",
        "reason": "产品名必须保持原样。",
        "content_unit_ids": ["content:answer"],
    }]
    boundaries["verbatim_obligations"] = [{
        "verbatim_id": "verbatim:one",
        "text": "必须保留的原文",
        "reason": "用户要求原文出现。",
        "content_unit_ids": ["content:answer"],
    }]
    boundaries["prohibited_overclaims"] = [{
        "overclaim_id": "overclaim:one",
        "affected_content_unit_ids": ["content:answer"],
        "forbidden_meaning": "不得把有限材料写成普遍规律。",
        "reason": "当前证据范围不足以支持普遍化。",
        "authority_refs": ["private:authority"],
    }]
    brief = _brief_with_boundaries(chain, boundaries)
    spine = pipeline.build_reader_spine(brief, composition_plan=chain["plan"])

    assert spine["reader_constraints"] == {
        "citation_rules": [{
            "citation_id": "citation:one",
            "content_unit_ids": ["content:answer"],
            "source_id": "source:synthetic",
            "marker": "[1]",
            "placement": "same_sentence",
        }],
        "exact_obligations": {
            "must_preserve": [{
                "token_id": "token:one",
                "token": "ReaderIntent",
                "reason": "产品名必须保持原样。",
                "content_unit_ids": ["content:answer"],
            }],
            "verbatim": [{
                "verbatim_id": "verbatim:one",
                "text": "必须保留的原文",
                "reason": "用户要求原文出现。",
                "content_unit_ids": ["content:answer"],
            }],
        },
        "claim_boundaries": [{
            "overclaim_id": "overclaim:one",
            "affected_content_unit_ids": ["content:answer"],
            "forbidden_meaning": "不得把有限材料写成普遍规律。",
            "reason": "当前证据范围不足以支持普遍化。",
        }],
    }
    rendered = pipeline.render_reader_spine_prompt(spine)
    assert "private:authority" not in rendered
    assert '"authority_refs"' not in rendered
    assert '"reader_constraints"' in rendered
    pipeline.validate_reader_spine(spine)


def test_reader_spine_rejects_private_route_payload_injection(tmp_path):
    chain = make_reader_chain(tmp_path / "private-route")
    spine = pipeline.build_reader_spine(chain["reader_brief"])
    mutated = copy.deepcopy(spine)
    mutated["route_guidance"]["route_payloads"] = []
    with pytest.raises(pipeline.ProductionPipelineBlocked, match="reader_spine_private_field"):
        pipeline.validate_reader_spine(mutated)


def test_reader_spine_deduplicates_evidence_and_retains_material_limit(tmp_path):
    chain = make_reader_chain(tmp_path / "chain")
    boundaries = copy.deepcopy(chain["reader_brief"]["content_boundaries"])
    boundaries["content_units"][0]["evidence_anchor_ids"] = ["evidence:one"]
    boundaries["limitations"] = [{
        "limitation_id": "limitation:scope",
        "safe_meaning": "这个结论只适用于当前样本范围。",
        "affected_content_unit_ids": ["content:answer"],
        "required_placement": "same_unit",
    }]
    plan = copy.deepcopy(chain["plan"])
    plan["planned_units"][0]["limitation_ids"] = ["limitation:scope"]
    plan["limitation_dispositions"] = [{
        "limitation_id": "limitation:scope",
        "affected_claim_ids": ["content:answer"],
        "materiality": "changes_scope",
        "materiality_reason": "读者需要知道结论的适用范围。",
        "disposition": "body",
        "destination_unit_ids": ["unit:answer"],
        "merged_into_id": None,
        "realization_requirement": "在结论附近说明适用范围。",
        "native_boundary_refs": [],
    }]
    plan["plan_fingerprint"] = fingerprint_without(plan, "plan_fingerprint")
    brief = _brief_with_boundaries(chain, boundaries, plan)
    spine = pipeline.build_reader_spine(brief, composition_plan=plan)

    assert len(spine["evidence_anchors"]) == 1
    assert spine["evidence_anchors"][0]["anchor_id"] == "evidence:one"
    assert spine["evidence_anchors"][0]["content_unit_ids"] == ["content:answer"]
    assert spine["conclusion_sensitive_limitations"] == [{
        "limitation_id": "limitation:scope",
        "meaning": "这个结论只适用于当前样本范围。",
        "affected_content_unit_ids": ["content:answer"],
        "required_placement": "same_unit",
        "materiality": "changes_scope",
        "materiality_reason": "读者需要知道结论的适用范围。",
        "disposition": "support",
        "destination_unit_ids": ["unit:answer"],
        "realization_requirement": "在结论附近说明适用范围。",
    }]
    assert spine["major_units"][0]["limitation_ids"] == ["limitation:scope"]
    pipeline.validate_reader_spine(spine)


def test_reader_spine_diagnostics_measure_positive_and_negative_patterns(tmp_path):
    chain = make_reader_chain(tmp_path / "chain")
    spine = pipeline.build_reader_spine(chain["reader_brief"])
    spine = copy.deepcopy(spine)
    spine["major_units"][0]["content"].append({
        "content_unit_id": "content:second",
        "meaning": "第二个独立发现需要合并进同一解释。",
        "disposition": "merge",
    })
    spine["editorial_dispositions"].append({
        "content_unit_id": "content:second",
        "planned_unit_ids": ["unit:answer"],
        "disposition": "merge",
    })
    pipeline.validate_reader_spine(spine)

    good = (
        "成品必须把中心问题、支撑、边界和收束写成连续正文；第二个独立发现需要合并进同一解释。"
        "这段文字让读者看到问题、理由和结论之间的连续关系。"
    )
    good_receipt = pipeline.diagnose_reader_output(good, spine)
    assert good_receipt["status"] == "passed"
    assert good_receipt["findings"] == []

    bad = "\n\n".join([
        "成品必须把中心问题、支撑、边界和收束写成连续正文。",
        "第二个独立发现需要合并进同一解释。",
        "需要注意：这段材料只说明当前范围。",
        "需要注意：这段材料只说明当前范围。",
        "- 条目一\n- 条目二\n- 条目三\n- 条目四\n- 条目五\n- 条目六\n- 条目七\n- 条目八",
        "LogicGuard 记录显示当前流程已经完成。",
        "因此，接下来。",
    ])
    bad_receipt = pipeline.diagnose_reader_output(bad, spine)
    codes = {row["code"] for row in bad_receipt["findings"]}
    assert bad_receipt["status"] == "repair"
    assert {
        "one_finding_one_paragraph",
        "repeated_no_information_disclaimer",
        "list_inflation",
        "guard_process_leakage",
        "transition_only_coherence",
    } <= codes
    assert bad_receipt["metrics"]["single_finding_paragraph_ratio"] == 1.0
    assert bad_receipt["metrics"]["repeated_no_information_disclaimer_count"] == 1
    assert bad_receipt["metrics"]["list_item_count"] == 8
    assert bad_receipt["metrics"]["workflow_leak_count"] == 1
    assert bad_receipt["metrics"]["transition_only_count"] == 1


def test_reader_spine_diagnostics_catches_fiction_author_note(tmp_path):
    chain = make_reader_chain(tmp_path / "fiction")
    spine = copy.deepcopy(pipeline.build_reader_spine(chain["reader_brief"]))
    spine["reader_context"]["purpose"] = "按受限视角写一段场景，结尾保留代价。"
    result = pipeline.diagnose_reader_output(
        "账本拿走后，搭档失去了工作。陈舟如何得知此事，尚无交代；这一后果不能写成他此刻的所知。",
        spine,
    )
    assert result["status"] == "repair"
    assert "fiction_author_meta" in {row["code"] for row in result["findings"]}
    assert result["metrics"]["fiction_author_meta_count"] == 2


def test_reader_spine_diagnostics_catches_travel_negative_only_branch(tmp_path):
    chain = make_reader_chain(tmp_path / "travel")
    spine = copy.deepcopy(pipeline.build_reader_spine(chain["reader_brief"]))
    spine["reader_context"]["purpose"] = "写雨天旅客半日旅行方案。"
    result = pipeline.diagnose_reader_output(
        "若到馆后入口或座位不可用，不能可靠折返，也不能未经核实改去馆A。",
        spine,
    )
    assert result["status"] == "repair"
    assert "travel_negative_only_failure" in {row["code"] for row in result["findings"]}
    assert result["metrics"]["travel_negative_only_failure_count"] == 1
