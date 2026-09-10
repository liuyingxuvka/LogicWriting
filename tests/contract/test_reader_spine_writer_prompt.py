"""Consumer contract for the production writer's reader-spine boundary."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from production_reader_pipeline import ProductionPipelineBlocked, build_reader_spine
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

    assert '"reader_context"' in prompt
    assert '"major_units"' in prompt
    assert '"selected_content"' not in prompt
    assert '"route_semantics"' not in prompt
    assert '"gaps"' not in prompt
    assert '"native_handoff"' not in prompt
    assert "WriterInput" not in prompt

    with pytest.raises(ProductionPipelineBlocked, match="reader_spine_non_minimal"):
        benchmark._production_writer_prompt(chain["reader_brief"]["writer_input"])
