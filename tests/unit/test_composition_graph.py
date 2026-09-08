from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint
from reader_pipeline import validate_composition_plan
from tests.v2_support import make_reader_chain


def test_composition_parent_graph_rejects_cycles(tmp_path):
    chain = make_reader_chain(tmp_path)
    plan = copy.deepcopy(chain["plan"])
    plan["planned_units"][0]["parent_unit_id"] = "unit:answer"
    plan["plan_fingerprint"] = fingerprint({k: v for k, v in plan.items() if k != "plan_fingerprint"})
    with pytest.raises(ValidationError, match="cycle"):
        validate_composition_plan(
            plan, reader_intent=chain["intent"],
            content_unit_ids=["content:answer"], limitation_ids=[],
        )
