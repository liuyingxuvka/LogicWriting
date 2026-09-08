from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint
from reader_execution import dispatch_judge
from reader_pipeline import validate_reader_judgment
from tests.v2_support import complete_chain


def test_judge_request_cannot_prefill_completion(tmp_path):
    chain = complete_chain(tmp_path)
    request = {
        "reader_intent_fingerprint": chain["intent"]["intent_fingerprint"],
        "writer_input_fingerprint": chain["reader_brief"]["writer_input_fingerprint"],
        "rubric_fingerprint": fingerprint({"rubric": "reader"}),
        "status": "completed",
    }
    with pytest.raises(ValidationError, match="prefill"):
        dispatch_judge(request, None)


def test_unverified_judge_execution_can_only_yield_repair(tmp_path):
    chain = complete_chain(tmp_path)
    execution = copy.deepcopy(chain["reader_execution_records"][0])
    execution["independence_status"] = "independence_unverified"
    execution["record_fingerprint"] = fingerprint({k: v for k, v in execution.items() if k != "record_fingerprint"})
    judgment = copy.deepcopy(chain["judgment"])
    judgment["status"] = "repair"
    judgment["execution_record_fingerprint"] = execution["record_fingerprint"]
    judgment["judgment_fingerprint"] = fingerprint({k: v for k, v in judgment.items() if k != "judgment_fingerprint"})
    validated = validate_reader_judgment(
        judgment, artifact_map=chain["artifact_map"], reader_brief=chain["reader_brief"],
        shared_writing=chain["shared_writing"], deterministic_audit=chain["deterministic_audit"],
        route_review=chain["route_review"], execution_record=execution,
    )
    assert validated["status"] == "repair"
