from __future__ import annotations

import copy

from reader_pipeline import build_writer_input
from tests.v2_support import make_reader_chain


def test_internal_semantic_material_is_not_projected_to_the_writer(tmp_path):
    chain = make_reader_chain(tmp_path)
    boundaries = copy.deepcopy(chain["reader_brief"]["content_boundaries"])
    boundaries["content_units"].append({
        "content_unit_id": "content:internal",
        "safe_meaning": "internal audit metadata for the planner",
        "required": False,
        "evidence_anchor_ids": [],
        "alternative_ids": [],
        "limitation_ids": [],
        "model_row_ids": [],
    })
    writer = build_writer_input(
        owner="investigation", intent=chain["intent"], plan=chain["plan"],
        route=chain["route_composition"], boundaries=boundaries,
    )
    assert "content:internal" not in {row["content_unit_id"] for row in writer["selected_content"]}
