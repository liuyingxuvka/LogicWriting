from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from _common import ValidationError
from tests.v2_support import derive_protocol_closure as derive_closure
from reader_pipeline import validate_artifact_map
from tests.v2_support import closure_input, complete_chain


BENCHMARK = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "fixtures" / "reader_v2" / "benchmark.json"
    ).read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", BENCHMARK["frozen_cases"], ids=lambda row: row["case_id"])
def test_reader_v2_protocol_fixture_has_full_mapping_and_current_closure(case, tmp_path):
    chain = complete_chain(
        tmp_path / case["case_id"],
        case["owner"],
        language=case["language"],
    )
    closure = derive_closure(closure_input(chain))["closure"]
    assert closure["status"] == "passed"
    assert chain["shared_writing"]["unit_bindings"]
    assert BENCHMARK["evidence_mode"] == "protocol_only"


def test_protocol_fixture_has_twelve_balanced_cases():
    cases = BENCHMARK["frozen_cases"]
    assert len(cases) == 12
    assert {row["owner"] for row in cases} == {
        "investigation", "academic-writing", "fiction-writing", "travel-guide"
    }
    assert all(sum(row["owner"] == owner for row in cases) == 3 for owner in {
        "investigation", "academic-writing", "fiction-writing", "travel-guide"
    })
    assert {row["language"] for row in cases} == {"zh-CN", "en"}




@pytest.mark.parametrize(
    "owner",
    ["investigation", "academic-writing", "fiction-writing", "travel-guide"],
)
def test_each_route_exposes_repair_and_stale_edit(owner, tmp_path):
    chain = complete_chain(tmp_path / owner, owner, pass_quality=False)
    assert derive_closure(closure_input(chain))["closure"]["status"] == "needs_repair"
    chain["artifact_path"].write_text("materially changed", encoding="utf-8")
    with pytest.raises(ValidationError, match="stale"):
        validate_artifact_map(chain["artifact_map"])
