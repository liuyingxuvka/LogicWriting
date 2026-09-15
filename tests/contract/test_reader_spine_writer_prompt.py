"""Consumer contract for the production writer's reader-spine boundary."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from production_reader_pipeline import (
    ProductionPipelineBlocked,
    build_reader_spine,
    validate_reader_spine_prompt,
)
from tests.v2_support import make_reader_chain


def _load_benchmark():
    path = Path(__file__).resolve().parents[2] / "scripts" / "run_writing_quality_benchmark.py"
    spec = importlib.util.spec_from_file_location("logic_writing_benchmark_reader_spine", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_production_writer_prompt_serializes_only_validated_reader_spine(tmp_path):
    benchmark = _load_benchmark()
    chain = make_reader_chain(tmp_path / "chain")
    spine = build_reader_spine(chain["reader_brief"], composition_plan=chain["plan"])

    prompt = benchmark._production_writer_prompt(spine)

    assert "文章要回答" in prompt
    assert "推进线路是" in prompt
    assert "材料中必须保留的条件和作用" in prompt
    assert '"reader_context"' not in prompt
    assert '"major_units"' not in prompt
    assert '"selected_content"' not in prompt
    assert '"route_semantics"' not in prompt
    assert '"gaps"' not in prompt
    assert '"native_handoff"' not in prompt
    assert "WriterInput" not in prompt
    assert "schema_version" not in prompt
    assert "planned_unit_id" not in prompt
    assert "content_unit_id" not in prompt
    assert not any(line.lstrip().startswith(("-", "*")) for line in prompt.splitlines())
    assert validate_reader_spine_prompt(prompt, spine) is True
    with pytest.raises(ProductionPipelineBlocked, match="reader_prompt_projection_mismatch"):
        validate_reader_spine_prompt(prompt + "\n", spine)

    with pytest.raises(ProductionPipelineBlocked, match="reader_spine_non_minimal"):
        benchmark._production_writer_prompt(chain["reader_brief"]["writer_input"])


def test_repaired_writer_prompt_converts_missing_material_into_reader_action():
    benchmark = _load_benchmark()
    case = {
        "case_id": "H-T",
        "route": "travel-guide",
        "task": "安排雨天半日行程",
        "constraints": "连续步行不得超过10分钟",
        "material_records": [
            {"id": "E01", "text": "馆B单程步行8分钟，开放时间未提供。"},
        ],
    }

    prompt = benchmark._writer_prompt(case, "repaired")

    assert "不要把缺失信息改写成研究过程已经发生但‘目前尚未确认’" in prompt
    assert "不要把补材料的责任交给作者或读者" in prompt
    assert "决策前需要核实" in prompt
    assert "删除重复的未知项清单" in prompt
    assert "默认路线的可行条件和每条备用路线的退回条件必须分别绑定到所选路线" in prompt
    assert "某条备用路线核实失败不能否决已经核实可行的默认路线" in prompt
    assert "馆B作为默认" in prompt
    assert "公交去馆A作为独立备用" in prompt
    assert "不可把两条路线合成一个全局的‘或’或‘且’退回条件" in prompt


def test_production_reader_prompt_enforces_extent_and_fiction_information_boundary(tmp_path):
    benchmark = _load_benchmark()
    chain = make_reader_chain(tmp_path / "fiction", "fiction-writing")
    spine = build_reader_spine(chain["reader_brief"], composition_plan=chain["plan"])
    spine["reader_context"]["extent"] = {
        "unit": "characters",
        "minimum": 800,
        "target": 950,
        "maximum": 1100,
    }
    spine["root_question"] = "如何沿公开账页逼主管放行并承担信任代价？"
    spine["root_conclusion"] = "目标已选公开账页；砸锁仅为备选，先造成压力，再由主管放行完成开门，未知调换事实保持未知。"

    prompt = benchmark._production_writer_prompt(spine)

    assert "篇幅是硬约束" in prompt
    assert "范围为 800—1100" in prompt
    assert "在材料给出的合法知情路径出现前" in prompt
    assert "当前任务目的已经选定公开账页" in prompt
    assert "不得把砸锁、撬锁或铁锤改写成当前场景的实际开门手段" in prompt
    assert "不得新增第二把钥匙" in prompt


def test_production_reader_prompt_closes_restricted_starting_knowledge(tmp_path):
    benchmark = _load_benchmark()
    chain = make_reader_chain(tmp_path / "restricted-fiction", "fiction-writing")
    spine = build_reader_spine(chain["reader_brief"], composition_plan=chain["plan"])
    spine["reader_context"]["purpose"] = "按给定信息写受限视角场景；人物只知道门从内反锁和搭档在屋内。"
    spine["major_units"][0]["content"][0]["meaning"] = (
        "场景开始时人物只知道门从内反锁和搭档在屋内；账本的位置要等他看见后才能确认。"
    )

    prompt = benchmark._production_writer_prompt(spine)

    assert "受限/近距离视角的起始知情集合是封闭的" in prompt
    assert "不得把任务目标、场景常识、后文结果或逻辑上可能存在的事实倒推成已知" in prompt
    assert "集合外的事实必须等到视角人物通过材料允许的看见、听见、阅读、对话或其它可观察事件取得后才能写出" in prompt


def test_production_travel_prompt_requires_explicit_origin_fallback_when_none_is_supported(tmp_path):
    benchmark = _load_benchmark()
    chain = make_reader_chain(tmp_path / "travel-no-fallback", "travel-guide")
    spine = build_reader_spine(chain["reader_brief"], composition_plan=chain["plan"])
    spine["route_guidance"]["reachable_fallbacks"] = []

    prompt = benchmark._production_writer_prompt(spine)

    assert "如果材料没有支持的可达备用路线" in prompt
    assert "必须把留在起点、停止出发或原地休息写成明确可执行的退回方案" in prompt
    assert "不得把退回路径写成要求读者补资料的开放任务" in prompt
    assert "如果同时存在默认路线和备用路线，分别写清每条路线自己的启用条件与退回条件" in prompt
    assert "一条备用路线未通过核实时，不能因此取消已经满足条件的默认路线" in prompt
    assert "结尾必须按‘实际选择的路线→该路线条件不满足→留在起点’分别写出分支" in prompt
    assert "appendix:checks" not in prompt


def test_direct_repaired_prompt_keeps_f01_action_source_and_i01_length_contract():
    benchmark = _load_benchmark()
    f01 = {
        "case_id": "F01",
        "route": "fiction-writing",
        "task": "按F包写800—1100字完整仓库场景",
        "constraints": "不能提前揭示钥匙被调换；必须公开账页并保留信任代价。",
        "material_records": [{"id": "F04", "text": "可以公开账页逼开门，也可以砸锁；目标选择公开账页。"}],
    }
    i01 = {
        "case_id": "I01",
        "route": "investigation",
        "task": "写600—800个汉字的采购试点建议",
        "constraints": "回答是否扩大试点。",
        "material_records": [{"id": "E01", "text": "中负载匹配产出观察到10%。"}],
    }

    f_prompt = benchmark._writer_prompt(f01, "repaired")
    i_prompt = benchmark._writer_prompt(i01, "repaired")

    assert "当前目标明确选择公开账页逼主管开门" in f_prompt
    assert "砸锁只是材料列出的备选" in f_prompt
    assert "不能新增第二把钥匙" in f_prompt
    assert "正文必须落在该区间" in i_prompt
    assert "具体的采购判断、条件" in i_prompt


def test_production_boundaries_compile_only_explicit_citation_ranges():
    benchmark = _load_benchmark()
    cited = {
        "case_id": "A01",
        "route": "academic-writing",
        "language": "zh-CN",
        "task": "使用L包写1000—1400字概念论证，引用[L01]—[L03]。",
        "constraints": "不新增研究数据。",
        "material_records": [
            {"id": "L01", "text": "第一条材料。"},
            {"id": "L02", "text": "第二条材料。"},
            {"id": "L03", "text": "第三条材料。"},
            {"id": "L04", "text": "未被点名的材料。"},
        ],
    }

    _request, boundaries, _token = benchmark._production_request_and_boundaries(cited)

    assert [row["marker"] for row in boundaries["citation_duties"]] == [
        "[L01]", "[L02]", "[L03]"
    ]
    assert all(row["content_unit_ids"] == ["content:materials"] for row in boundaries["citation_duties"])
    assert all(row["placement"] == "same_paragraph" for row in boundaries["citation_duties"])


def test_reader_prompt_preserves_declared_citations_and_compacts_job_labels(tmp_path):
    chain = make_reader_chain(tmp_path / "chain", "academic-writing")
    spine = build_reader_spine(chain["reader_brief"], composition_plan=chain["plan"])
    spine["reader_constraints"]["citation_rules"] = [{
        "citation_id": "citation:L01",
        "content_unit_ids": ["content:answer"],
        "source_id": "source:L01",
        "marker": "[L01]",
        "placement": "same_paragraph",
    }]
    spine["root_conclusion"] = "中心判断依据[L01]收束。"
    spine["opening_job"] = "开篇先建立问题。"
    spine["conclusion_job"] = "结尾再给出边界。"

    from production_reader_pipeline import render_reader_spine_prompt

    prompt = render_reader_spine_prompt(spine)

    assert "依据[L01]收束" in prompt
    assert "相关句使用引用标记[L01]" in prompt
    assert "开头先建立问题" in prompt
    assert "结尾再给出边界" in prompt
    assert "开头开篇" not in prompt
    assert "结尾结尾" not in prompt
