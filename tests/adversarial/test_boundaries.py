from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint
from derive_closure import derive_closure
from reader_pipeline import validate_route_artifact_review
from tests.v2_support import closure_input, complete_chain


def test_sibling_route_review_cannot_close_artifact(tmp_path):
    investigation = complete_chain(tmp_path, "investigation")
    fiction = complete_chain(tmp_path, "fiction-writing")
    request = closure_input(investigation)
    request["route_review"] = fiction["route_review"]
    with pytest.raises(ValidationError):
        derive_closure(request)


def test_review_evidence_must_be_actual_current_excerpt(tmp_path):
    chain = complete_chain(tmp_path)
    review = copy.deepcopy(chain["route_review"])
    review["dimensions"][0]["evidence"][0]["excerpt"] = "invented evidence"
    review["dimensions"][0]["evidence"][0]["excerpt_fingerprint"] = fingerprint("invented evidence")
    review["review_fingerprint"] = fingerprint({k: v for k, v in review.items() if k != "review_fingerprint"})
    with pytest.raises(ValidationError):
        validate_route_artifact_review(
            review,
            owner="investigation",
            route_composition=chain["route_composition"],
            artifact_map=chain["artifact_map"],
            required_dimensions=[row["dimension_id"] for row in review["dimensions"]],
        )


def test_route_review_cannot_omit_one_required_dimension(tmp_path):
    chain = complete_chain(tmp_path, "academic-writing")
    review = copy.deepcopy(chain["route_review"])
    review["dimensions"].pop()
    review["review_fingerprint"] = fingerprint({k: v for k, v in review.items() if k != "review_fingerprint"})
    request = closure_input(chain)
    request["route_review"] = review
    with pytest.raises(ValidationError, match="omits required"):
        derive_closure(request)


def test_native_receipt_set_is_frozen_in_reader_brief(tmp_path):
    chain = complete_chain(tmp_path)
    request = closure_input(chain)
    request["native_receipt_fingerprints"] = [fingerprint({"foreign": True})]
    with pytest.raises(ValidationError, match="differ"):
        derive_closure(request)


def test_same_agent_cannot_self_judge(tmp_path):
    chain = complete_chain(tmp_path)
    judgment = copy.deepcopy(chain["judgment"])
    judgment["judge_id"] = judgment["producer_id"]
    judgment["judgment_fingerprint"] = fingerprint({k: v for k, v in judgment.items() if k != "judgment_fingerprint"})
    request = closure_input(chain)
    request["judgment"] = judgment
    with pytest.raises(ValidationError, match="independent"):
        derive_closure(request)
