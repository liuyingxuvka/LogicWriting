"""Regression checks for the compact reader-facing prompt projection."""

from __future__ import annotations

import copy

import pytest

from production_reader_pipeline import (
    ProductionPipelineBlocked,
    build_reader_spine,
    render_reader_spine_prompt,
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
    assert "保留原文" in prompt


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
