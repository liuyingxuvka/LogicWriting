"""Regression checks for the compact reader-facing prompt projection."""

from __future__ import annotations

import copy

import pytest

from production_reader_pipeline import (
    ProductionPipelineBlocked,
    _dedupe_prompt_paragraphs,
    build_reader_spine,
    render_reader_spine_prompt,
    validate_reader_prompt_obligations,
    validate_reader_spine_prompt,
)
from tests.v2_support import make_reader_chain


def _spine_with_internal_references(tmp_path):
    chain = make_reader_chain(tmp_path / "chain", "investigation")
    spine = copy.deepcopy(build_reader_spine(chain["reader_brief"], composition_plan=chain["plan"]))
    spine["major_units"][0]["content"][0]["meaning"] = (
        "用户约束：只能在当前样本内解释，不得把观察推广到所有设备。\n"
        "冻结材料（逐条事实）：[T01] 当前设备的中负载结果为10%。"
    )
    spine["major_units"][0]["evidence_anchor_ids"] = ["evidence:T01"]
    spine["evidence_anchors"] = [{
        "anchor_id": "evidence:T01",
        "source_id": "source:T01",
        "locator": "materials-T.json:line:1",
        "relation": "support",
        "observed_summary": "当前设备的中负载结果为10%。",
        "boundary": "冻结材料；只能支持其中明确写出的事实，不可外推。",
        "content_unit_ids": ["content:answer"],
    }]
    spine["route_guidance"]["bounded_answer"] = [
        "用户任务：根据[T01]给出有边界的解释。",
    ]
    return spine


def test_compact_prompt_removes_internal_ids_and_field_repetition(tmp_path):
    spine = _spine_with_internal_references(tmp_path)

    prompt = render_reader_spine_prompt(spine)

    assert "10%" in prompt
    assert "只能在当前样本内解释" in prompt
    assert "[T01]" not in prompt
    assert "source:T01" not in prompt
    assert "materials-T.json" not in prompt
    assert "schema_version" not in prompt
    assert "root_question" not in prompt
    assert "major_units" not in prompt
    assert "reader_context" not in prompt
    assert "route_guidance" not in prompt
    assert "content_unit_id" not in prompt
    assert "planned_unit_id" not in prompt
    assert not any(line.lstrip().startswith(("-", "*")) for line in prompt.splitlines())
    assert not any(line.lstrip().startswith(("1.", "1、")) for line in prompt.splitlines())
    assert validate_reader_spine_prompt(prompt, spine) is True


def test_compact_prompt_preserves_explicit_user_structure_without_listifying_prose(tmp_path):
    chain = make_reader_chain(tmp_path / "chain", "investigation")
    spine = build_reader_spine(chain["reader_brief"], composition_plan=chain["plan"])
    spine["reader_context"]["required_content"] = ["先说明判断，再给出条件和下一步"]
    spine["reader_context"]["forbidden_content"] = ["工作流术语"]

    prompt = render_reader_spine_prompt(spine)

    assert "正文默认使用连续段落和自然过渡" in prompt
    assert "不要把材料拆成项目符号、编号清单或一行一项" in prompt
    assert "先说明判断，再给出条件和下一步" in prompt
    assert "工作流术语" in prompt
    assert "prose_default" not in prompt
    assert not any(line.lstrip().startswith(("-", "*")) for line in prompt.splitlines())


def test_compact_prompt_keeps_explicit_verbatim_obligation_even_when_it_looks_like_an_id(tmp_path):
    chain = make_reader_chain(tmp_path / "chain", "investigation")
    spine = build_reader_spine(chain["reader_brief"], composition_plan=chain["plan"])
    spine["reader_constraints"]["exact_obligations"]["verbatim"] = [{
        "verbatim_id": "verbatim:required",
        "text": "[T01]原文必须保留",
        "reason": "用户明确要求原文出现。",
        "content_unit_ids": ["content:answer"],
    }]

    prompt = render_reader_spine_prompt(spine)

    assert "[T01]原文必须保留" in prompt
    assert "<<<LW-EXACT-" in prompt
    assert prompt.count("[T01]原文必须保留") == 1


def test_prompt_binding_rejects_stale_or_modified_capture(tmp_path):
    chain = make_reader_chain(tmp_path / "chain", "investigation")
    spine = build_reader_spine(chain["reader_brief"], composition_plan=chain["plan"])
    prompt = render_reader_spine_prompt(spine)

    with pytest.raises(ProductionPipelineBlocked, match="reader_prompt_projection_mismatch"):
        validate_reader_spine_prompt(prompt + "\n", spine)

    changed = copy.deepcopy(spine)
    changed["root_conclusion"] = "改动后的结论。"
    with pytest.raises(ProductionPipelineBlocked, match="reader_prompt_projection_mismatch"):
        validate_reader_spine_prompt(prompt, changed)


def test_mixed_user_constraint_and_material_fact_are_both_projected(tmp_path):
    spine = _spine_with_internal_references(tmp_path)
    spine["major_units"][0]["content"][0]["meaning"] = (
        "用户约束：只能解释当前样本。\n材料事实：731。"
    )
    prompt = render_reader_spine_prompt(spine)

    assert "只能解释当前样本" in prompt
    assert "731" in prompt
    assert validate_reader_prompt_obligations(prompt, spine) is True
    with pytest.raises(ProductionPipelineBlocked, match="reader_prompt_obligation_missing"):
        validate_reader_prompt_obligations(prompt.replace("731", ""), spine)


def test_fact_source_marker_pair_changes_when_sources_are_swapped(tmp_path):
    spine = _spine_with_internal_references(tmp_path)
    spine["reader_context"]["citation_policy"] = "inline"
    spine["major_units"][0]["content"][0]["meaning"] = "阈值为731；剂量为842。"
    spine["major_units"][0]["evidence_anchor_ids"] = ["evidence:A", "evidence:B"]
    spine["evidence_anchors"] = [
        {
            "anchor_id": "evidence:A", "source_id": "source:A", "locator": "a",
            "relation": "support", "observed_summary": "阈值为731。",
            "boundary": "仅支持明确事实。", "content_unit_ids": ["content:answer"],
        },
        {
            "anchor_id": "evidence:B", "source_id": "source:B", "locator": "b",
            "relation": "support", "observed_summary": "剂量为842。",
            "boundary": "仅支持明确事实。", "content_unit_ids": ["content:answer"],
        },
    ]
    spine["reader_constraints"]["citation_rules"] = [
        {"citation_id": "citation:A", "content_unit_ids": ["content:answer"], "source_id": "source:A", "marker": "[A]", "placement": "same_paragraph"},
        {"citation_id": "citation:B", "content_unit_ids": ["content:answer"], "source_id": "source:B", "marker": "[B]", "placement": "same_paragraph"},
    ]
    prompt_a = render_reader_spine_prompt(spine)
    assert "事实“阈值为731。”（证据关系：support）（对应引用标记[A]）" in prompt_a
    assert "事实“剂量为842。”（证据关系：support）（对应引用标记[B]）" in prompt_a

    swapped = copy.deepcopy(spine)
    swapped["evidence_anchors"][0]["source_id"] = "source:B"
    swapped["evidence_anchors"][1]["source_id"] = "source:A"
    prompt_b = render_reader_spine_prompt(swapped)
    assert prompt_a != prompt_b
    assert "事实“阈值为731。”（证据关系：support）（对应引用标记[B]）" in prompt_b
    assert "事实“剂量为842。”（证据关系：support）（对应引用标记[A]）" in prompt_b
    assert validate_reader_prompt_obligations(prompt_b, swapped) is True


def test_exact_verbatim_tab_is_checked_without_normalization(tmp_path):
    chain = make_reader_chain(tmp_path / "exact", "investigation")
    spine = build_reader_spine(chain["reader_brief"], composition_plan=chain["plan"])
    raw = "原文\t必须保留\n第二行"
    spine["reader_constraints"]["exact_obligations"]["verbatim"] = [{
        "verbatim_id": "verbatim:tab",
        "text": raw,
        "reason": "用户明确要求原文出现。",
        "content_unit_ids": ["content:answer"],
    }]
    prompt = render_reader_spine_prompt(spine)
    assert raw in prompt
    assert validate_reader_prompt_obligations(prompt, spine) is True
    with pytest.raises(ProductionPipelineBlocked, match="reader_prompt_obligation_missing"):
        validate_reader_prompt_obligations(prompt.replace("\t", " ", 1), spine)


def test_prompt_equality_key_only_trims_edges_and_keeps_order_and_symbols():
    values = [
        "C/C++", "c/c++", "1/10", "1 / 10", "±", "+-", "< />", "<> ",
        "a  b", "a b", "same", "same",
    ]
    assert _dedupe_prompt_paragraphs(values) == values[:-1]


def test_prompt_keeps_ordinary_technical_terms_and_exact_unicode_bytes(tmp_path):
    chain = make_reader_chain(tmp_path / "exact", "investigation")
    spine = build_reader_spine(chain["reader_brief"], composition_plan=chain["plan"])
    raw = "\tC/C++  A/a\n1/10 ± < />\r\n双  空格"
    spine["reader_constraints"]["exact_obligations"]["verbatim"] = [{
        "verbatim_id": "verbatim:unicode",
        "text": raw,
        "reason": "用户要求逐字保留。",
        "content_unit_ids": ["content:answer"],
    }]
    spine["major_units"][0]["content"][0]["meaning"] = (
        "技术术语 C/C++、A/a、1/10、±、< />、逗号,小数点. 和 gaps locator 必须保留。"
    )
    prompt = render_reader_spine_prompt(spine)
    assert raw in prompt
    assert "C/C++、A/a、1/10、±、< />、逗号,小数点. 和 gaps locator" in prompt
    delimiter = next(line for line in prompt.splitlines() if line.startswith("<<<LW-EXACT-"))
    assert delimiter not in raw
    assert prompt.count(delimiter) == 2
