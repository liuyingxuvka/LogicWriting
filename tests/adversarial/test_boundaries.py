from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint
from tests.v2_support import derive_protocol_closure as derive_closure
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


def test_same_agent_cannot_self_judge(tmp_path):
    chain = complete_chain(tmp_path)
    judgment = copy.deepcopy(chain["judgment"])
    judgment["judge_kind"] = "independent_context"
    judgment["judge_id"] = judgment["producer_id"]
    judgment["judgment_fingerprint"] = fingerprint({k: v for k, v in judgment.items() if k != "judgment_fingerprint"})
    request = closure_input(chain)
    request["judgment"] = judgment
    with pytest.raises(ValidationError, match="independent"):
        derive_closure(request)


def _boundary_review(chain):
    from tests.v2_support import span_evidence
    brief = copy.deepcopy(chain['reader_brief'])
    brief['content_boundaries']['limitations'] = [dict(limitation_id='lim:scope', safe_meaning='Limited scope',
        affected_content_unit_ids=['content:answer'], required_placement='same_unit')]
    brief['composition_plan']['limitation_dispositions'] = [dict(limitation_id='lim:scope', disposition='body',
        destination_unit_ids=['unit:answer'])]
    brief['content_boundaries']['prohibited_overclaims'] = [dict(overclaim_id='oc:universal')]
    review = copy.deepcopy(chain['route_review'])
    review['limitation_checks'] = [dict(limitation_id='lim:scope', status='present', evidence=[span_evidence(chain)])]
    review['overclaim_checks'] = [dict(overclaim_id='oc:universal', status='absent', evidence=[])]
    return brief, review


def test_review_must_answer_every_limitation_and_overclaim(tmp_path):
    from reader_pipeline import _review_boundary_checks
    chain = complete_chain(tmp_path)
    brief, review = _boundary_review(chain)
    review['limitation_checks'] = []
    review['overclaim_checks'] = []
    with pytest.raises(ValidationError, match='lim:scope.*oc:universal'):
        _review_boundary_checks(review, brief=brief, shared=chain['shared_writing'], amap=chain['artifact_map'])


def test_limitation_excerpt_must_be_in_its_planned_unit(tmp_path):
    from reader_pipeline import _review_boundary_checks
    chain = complete_chain(tmp_path)
    brief, review = _boundary_review(chain)
    shared = copy.deepcopy(chain['shared_writing'])
    units = [u for u in chain['artifact_map']['units'] if u['unit_kind'] == 'paragraph']
    shared['unit_bindings'][0]['artifact_unit_ids'] = [units[1]['artifact_unit_id']]
    with pytest.raises(ValidationError, match='lim:scope.*bound planned unit'):
        _review_boundary_checks(review, brief=brief, shared=shared, amap=chain['artifact_map'])
    brief['content_boundaries']['limitations'][0]['required_placement'] = 'adjacent_unit'
    _review_boundary_checks(review, brief=brief, shared=shared, amap=chain['artifact_map'])


def test_present_overclaim_forces_repair(tmp_path):
    from reader_pipeline import _route_review_from_current
    from tests.v2_support import span_evidence
    chain = complete_chain(tmp_path)
    brief, review = _boundary_review(chain)
    review['overclaim_checks'][0].update(status='present', evidence=[span_evidence(chain)])
    review.pop('review_fingerprint')
    review['review_fingerprint'] = fingerprint(review)
    with pytest.raises(ValidationError, match='status is not derived'):
        _route_review_from_current(review, owner='investigation', route=chain['route_composition'], amap=chain['artifact_map'],
                                   brief=brief, shared=chain['shared_writing'])
    review.update(status='repair', required_repairs=['oc:universal'])
    review.pop('review_fingerprint')
    review['review_fingerprint'] = fingerprint(review)
    assert _route_review_from_current(review, owner='investigation', route=chain['route_composition'], amap=chain['artifact_map'],
                                     brief=brief, shared=chain['shared_writing'])['status'] == 'repair'
