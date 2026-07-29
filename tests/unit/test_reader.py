from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint, fingerprint_text
from reader_pipeline import build_artifact_map, build_reader_audit, validate_reader_judgment
from tests.v2_support import complete_chain, make_reader_chain


def test_artifact_map_binds_exact_utf8_bytes_and_spans(tmp_path):
    chain = make_reader_chain(tmp_path)
    amap = build_artifact_map(chain["artifact_path"], map_id="map:again", language="zh-CN")
    assert amap["artifact_fingerprint"] == chain["artifact_map"]["artifact_fingerprint"]
    assert any(row["unit_kind"] == "paragraph" for row in amap["units"])


@pytest.mark.parametrize(
    ("text", "expected_code"),
    [
        ("# 完整回答\n\nTODO: 稍后补写。", "placeholder"),
        ("# 完整回答\n\nFlowGuard reports current_pass.", "workflow_leak"),
        ("# 完整回答\n\n第一点。\n\n第二点。\n\n第三点。\n\n第四点。", "microparagraph_sequence"),
    ],
)
def test_deterministic_audit_catches_reader_facing_failures(tmp_path, text, expected_code):
    chain = make_reader_chain(tmp_path)
    chain["artifact_path"].write_text(text, encoding="utf-8")
    amap = build_artifact_map(chain["artifact_path"], map_id="map:bad", language="zh-CN")
    # Rebind a minimal current contract so the audit tests the actual bytes.
    paragraph = next(row for row in amap["units"] if row["unit_kind"] == "paragraph")
    contract = copy.deepcopy(chain["shared_writing"])
    contract["artifact_map_fingerprint"] = amap["map_fingerprint"]
    contract["artifact_fingerprint"] = amap["artifact_fingerprint"]
    contract["artifact_path"] = str(chain["artifact_path"].resolve())
    contract["unit_bindings"][0]["artifact_unit_ids"] = [paragraph["artifact_unit_id"]]
    contract["unit_bindings"][0]["artifact_spans"] = [{
        "artifact_unit_id": paragraph["artifact_unit_id"],
        "locator": paragraph["locator"],
        "content_fingerprint": paragraph["content_fingerprint"],
    }]
    contract["contract_fingerprint"] = fingerprint({k: v for k, v in contract.items() if k != "contract_fingerprint"})
    audit = build_reader_audit(
        audit_id="audit:bad", artifact_map=amap,
        reader_brief=chain["reader_brief"], shared_writing=contract,
    )
    assert expected_code in {row["code"] for row in audit["findings"]}


def test_judge_must_be_independent(tmp_path):
    chain = complete_chain(tmp_path)
    judgment = copy.deepcopy(chain["judgment"])
    judgment["judge_id"] = judgment["producer_id"]
    judgment["judgment_fingerprint"] = fingerprint({k: v for k, v in judgment.items() if k != "judgment_fingerprint"})
    with pytest.raises(ValidationError, match="independent"):
        validate_reader_judgment(
            judgment,
            artifact_map=chain["artifact_map"],
            reader_brief=chain["reader_brief"],
            shared_writing=chain["shared_writing"],
            deterministic_audit=chain["deterministic_audit"],
            route_review=chain["route_review"],
        )


def test_judgment_excerpt_must_exist_in_current_unit(tmp_path):
    chain = complete_chain(tmp_path)
    judgment = copy.deepcopy(chain["judgment"])
    evidence = judgment["reverse_outline"][0]["evidence"]
    evidence["excerpt"] = "这段文字并不存在"
    evidence["excerpt_fingerprint"] = fingerprint_text(evidence["excerpt"])
    judgment["judgment_fingerprint"] = fingerprint({k: v for k, v in judgment.items() if k != "judgment_fingerprint"})
    with pytest.raises(ValidationError, match="absent"):
        validate_reader_judgment(
            judgment,
            artifact_map=chain["artifact_map"],
            reader_brief=chain["reader_brief"],
            shared_writing=chain["shared_writing"],
            deterministic_audit=chain["deterministic_audit"],
            route_review=chain["route_review"],
        )
