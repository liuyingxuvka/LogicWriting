from __future__ import annotations

import pytest

from derive_closure import derive_closure
from tests.v2_support import closure_input, complete_chain


@pytest.mark.parametrize(
    "owner",
    ["investigation", "academic-writing", "fiction-writing", "travel-guide"],
)
def test_each_final_owner_delivers_one_complete_current_artifact(owner, tmp_path):
    chain = complete_chain(tmp_path, owner)
    result = derive_closure(closure_input(chain))
    closure = result["closure"]
    assert closure["final_owner"] == owner
    assert closure["artifact_fingerprint"] == chain["artifact_map"]["artifact_fingerprint"]
    assert closure["status"] == "passed"


def test_route_quality_repair_cannot_be_overwritten_by_shared_kernel(tmp_path):
    chain = complete_chain(tmp_path, "travel-guide", pass_quality=False)
    result = derive_closure(closure_input(chain))
    assert result["closure"]["status"] == "blocked"
    assert result["closure"]["next_actions"][0]["owner"] == "travel-guide"


def test_independent_judgment_is_required_after_route_review(tmp_path):
    chain = complete_chain(tmp_path, "fiction-writing")
    request = closure_input(chain)
    request.pop("judgment")
    with pytest.raises(Exception, match="missing"):
        derive_closure(request)
