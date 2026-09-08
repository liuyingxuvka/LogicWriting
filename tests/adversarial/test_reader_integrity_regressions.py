from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint
from reader_pipeline import _measure_extent, build_artifact_map, build_reader_audit, validate_artifact_map, validate_reader_audit_current, validate_reader_intent
from text_extent import measure_text
from tests.v2_support import complete_chain, make_reader_chain, make_intent


def test_reader_audit_rejects_a_caller_modified_fingerprint(tmp_path):
    chain = complete_chain(tmp_path)
    audit = copy.deepcopy(chain["deterministic_audit"])
    audit["status"] = "passed" if audit["status"] == "repair" else "repair"
    audit["audit_fingerprint"] = fingerprint({k: v for k, v in audit.items() if k != "audit_fingerprint"})
    with pytest.raises(ValidationError, match="differs|current"):
        validate_reader_audit_current(
            audit, artifact_map=chain["artifact_map"],
            reader_brief=chain["reader_brief"], shared_writing=chain["shared_writing"],
        )


def test_artifact_map_cannot_hide_unmapped_non_whitespace_bytes(tmp_path):
    chain = complete_chain(tmp_path)
    forged = copy.deepcopy(chain["artifact_map"])
    body = [row for row in forged["units"] if row["unit_kind"] == "paragraph"]
    assert len(body) >= 2
    forged["units"].remove(body[-1])
    forged["map_fingerprint"] = fingerprint({k: v for k, v in forged.items() if k != "map_fingerprint"})
    with pytest.raises(ValidationError, match="unmapped|partition"):
        validate_artifact_map(forged)


def test_artifact_map_rejects_a_claimed_unmapped_prose_range(tmp_path):
    chain = complete_chain(tmp_path)
    forged = copy.deepcopy(chain["artifact_map"])
    body = [row for row in forged["units"] if row["unit_kind"] == "paragraph"]
    gap = {"start": body[-1]["start"], "end": body[-1]["end"]}
    forged["unmapped_ranges"] = [gap]
    forged["map_fingerprint"] = fingerprint({k: v for k, v in forged.items() if k != "map_fingerprint"})
    with pytest.raises(ValidationError, match="partition|whitespace"):
        validate_artifact_map(forged)


def test_reader_audit_uses_declared_word_extent_and_detects_language(tmp_path):
    chain = make_reader_chain(tmp_path, language="zh-CN")
    intent = copy.deepcopy(chain["intent"])
    intent["language"] = "en"
    intent["extent"]["unit"] = "words"
    intent["extent"]["minimum"] = 1000
    intent["extent"]["target"] = 1200
    intent["extent"]["maximum"] = 1400
    intent["intent_fingerprint"] = fingerprint({k: v for k, v in intent.items() if k != "intent_fingerprint"})
    brief = copy.deepcopy(chain["reader_brief"])
    brief["reader_intent"] = intent
    brief["reader_intent_fingerprint"] = intent["intent_fingerprint"]
    brief["brief_fingerprint"] = fingerprint({k: v for k, v in brief.items() if k != "brief_fingerprint"})
    shared = copy.deepcopy(chain["shared_writing"])
    shared["reader_intent_fingerprint"] = intent["intent_fingerprint"]
    shared["reader_brief_fingerprint"] = brief["brief_fingerprint"]
    shared["contract_fingerprint"] = fingerprint({k: v for k, v in shared.items() if k != "contract_fingerprint"})
    audit = build_reader_audit(
        audit_id="audit:words", artifact_map=chain["artifact_map"],
        reader_brief=brief, shared_writing=shared,
    )
    assert _measure_extent("one two, three", "words") == 3
    assert audit["structure_metrics"]["extent_unit"] == "words"
    assert audit["structure_metrics"]["extent_count"] < 1000
    assert "wrong_language" in {row["code"] for row in audit["findings"]}


def test_text_extent_uses_declared_unicode_metrics():
    assert measure_text("It's a well-known result: 10.5 kW.", "words") == 7
    assert measure_text("Ice melts.", "words") == 2
    assert measure_text("冰融化了。", "characters") == 5
    assert measure_text("冰融化了。", "user_defined", metric_id="han_characters") == 4
    assert measure_text("A冰 B", "characters") == 3
    assert measure_text("😀", "characters") == 1


def test_user_defined_extent_must_name_the_executable_metric():
    intent = make_intent()
    intent["extent"] = {
        "unit": "user_defined", "extent_metric_id": "han_characters",
        "minimum": 1, "target": 4, "maximum": 8,
    }
    intent["intent_fingerprint"] = fingerprint({k: v for k, v in intent.items() if k != "intent_fingerprint"})
    assert validate_reader_intent(intent)["extent"]["extent_metric_id"] == "han_characters"
