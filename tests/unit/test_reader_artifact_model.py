"""Current-text closure and independent reader obligations."""


import copy
import hashlib
from pathlib import Path
import pytest
from _common import ValidationError, fingerprint
from tests.v2_support import derive_protocol_closure as derive_closure
from tests.v2_support import closure_input, complete_chain

@pytest.mark.parametrize(
    "owner",
    ["investigation", "academic-writing", "fiction-writing", "travel-guide"],
)
def test_complete_current_chain_closes(owner, tmp_path, monkeypatch):
    import derive_closure as closure_module
    import artifact_map
    import reader_checks
    from pathlib import Path
    chain = complete_chain(tmp_path, owner)
    request = closure_input(chain)
    original_map = artifact_map.validate_artifact_map
    original_audit = reader_checks.build_reader_audit_from_current
    calls = {"map": 0, "audit": 0}
    def mapped(value):
        calls["map"] += 1
        return original_map(value)
    def audited(**kwargs):
        # Mutation audits intentionally use different bytes; the current artifact is rebuilt once.
        if kwargs["amap"]["artifact_fingerprint"] == request["artifact_map"]["artifact_fingerprint"]:
            calls["audit"] += 1
        return original_audit(**kwargs)
    monkeypatch.setattr(closure_module, "validate_artifact_map", mapped)
    monkeypatch.setattr(artifact_map, "validate_artifact_map", mapped)
    monkeypatch.setattr(closure_module, "build_reader_audit_from_current", audited)
    monkeypatch.setattr(reader_checks, "build_reader_audit_from_current", audited)
    result = derive_closure(request)
    assert calls == {"map": 1, "audit": 1}
    def changed_during_audit(**kwargs):
        report = original_audit(**kwargs)
        artifact = Path(chain["artifact_map"]["artifact_path"])
        artifact.write_bytes(artifact.read_bytes() + b"changed")
        return report
    monkeypatch.setattr(closure_module, "build_reader_audit_from_current", changed_during_audit)
    with pytest.raises(ValidationError, match="stale during closure"):
        derive_closure(request)
    assert result["closure"]["status"] == "passed"
    assert result["closure"]["broad_claim_allowed"] is True



@pytest.mark.parametrize("same_ids, pass_quality", [(True, True), (False, True), (True, False)])
def test_self_review_closes_without_a_broad_claim(tmp_path, same_ids, pass_quality):
    request = closure_input(complete_chain(tmp_path, pass_quality=pass_quality))
    judgment = request["judgment"]
    judgment["judge_kind"] = "self_review"
    if same_ids:
        judgment["judge_id"] = judgment["producer_id"]
    judgment.pop("judgment_fingerprint")
    judgment["judgment_fingerprint"] = fingerprint(judgment)
    closed = derive_closure(request)["closure"]
    assert closed["status"] == ("passed" if pass_quality else "needs_repair")
    assert closed["judge_kind"] == "self_review"
    assert closed["broad_claim_allowed"] is False
    assert {"defect_id": "reader.self-review", "owner": "investigation",
            "reason": "The reader judgment was a self-review by the writer, not an independent read."} in closed["residual_risk"]
    assert "self-review by the writer" in closed["safe_claim"]
    assert "independent" not in closed["safe_claim"]
    if not pass_quality:
        assert len(closed["residual_risk"]) > 1
        assert closed["next_actions"] == [{"owner": "investigation", "action": "repair_and_rerun"}]



def test_quality_failure_needs_repair(tmp_path):
    result = derive_closure(closure_input(complete_chain(tmp_path, pass_quality=False)))
    assert result["closure"]["status"] == "needs_repair"
    assert result["closure"]["next_actions"] == [{"owner": "investigation", "action": "repair_and_rerun"}]

