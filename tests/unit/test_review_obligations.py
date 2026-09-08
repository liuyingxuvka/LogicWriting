from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint
from review_obligations import resolve_review_obligations, validate_review_obligation_manifest
from tests.v2_support import make_reader_chain


def test_review_obligations_are_profile_specific(tmp_path):
    chain = make_reader_chain(tmp_path, "academic-writing")
    manifest = resolve_review_obligations(
        "academic-writing", "conceptual_argument", chain["intent"], chain["route_composition"]
    )
    by_id = {row["obligation_id"]: row for row in manifest["obligations"]}
    assert by_id["method_conditions"]["status"] == "not_applicable_with_reason"
    assert by_id["figure_table_jobs"]["status"] == "not_applicable_with_reason"
    assert by_id["method_conditions"]["applicability"] == "not_applicable"
    assert len({row["dimension_id"] for row in manifest["obligations"]}) == len(manifest["obligations"])
    assert manifest["manifest_fingerprint"].startswith("sha256:")


def test_manifest_validation_rederives_figure_applicability(tmp_path):
    chain = make_reader_chain(tmp_path, "academic-writing")
    manifest = resolve_review_obligations(
        "academic-writing", "conceptual_argument", chain["intent"], chain["route_composition"]
    )
    validate_review_obligation_manifest(
        manifest, owner="academic-writing", profile="conceptual_argument",
        reader_intent_fingerprint=chain["intent"]["intent_fingerprint"],
        selected_composition=chain["route_composition"],
    )
    forged = copy.deepcopy(manifest)
    forged["obligations"][0]["status"] = "not_applicable_with_reason"
    forged["obligations"][0]["applicability"] = "not_applicable"
    forged["manifest_fingerprint"] = fingerprint({k: v for k, v in forged.items() if k != "manifest_fingerprint"})
    with pytest.raises(ValidationError, match="derived|composition"):
        validate_review_obligation_manifest(
            forged, owner="academic-writing", profile="conceptual_argument",
            reader_intent_fingerprint=chain["intent"]["intent_fingerprint"],
            selected_composition=chain["route_composition"],
        )
