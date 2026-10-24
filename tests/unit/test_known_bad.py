"""Known-bad edits of the user's piece: existing words only, original untouched, uncaught ones listed."""
from __future__ import annotations

from pathlib import Path
import re

import known_bad
from derive_closure import derive_closure
from known_bad import check_known_bad, text_variants
from tests.v2_support import closure_input, complete_chain


def _words(text):
    return set(re.findall(r"\w+", text))


def test_variants_use_only_existing_words_and_keep_the_original(tmp_path):
    request = closure_input(complete_chain(tmp_path))
    path = Path(request["artifact_map"]["artifact_path"])
    original = path.read_bytes()
    text = original.decode("utf-8")
    boundaries = request["reader_brief"]["content_boundaries"]
    allowed = _words(known_bad._INTERNAL_TERM) | {word for row in boundaries.get("prohibited_overclaims", [])
                                                  for word in _words(row["forbidden_meaning"])}
    cases = text_variants(text, reader_brief=request["reader_brief"], artifact_map=request["artifact_map"],
                          shared_writing=request["shared_writing"], route_review=request["route_review"])
    assert cases
    for case in cases:
        assert _words(case["text"]) - _words(text) <= allowed, case["name"]
        assert case["text"] != text, case["name"]
    result = check_known_bad(request)
    assert result["status"] == "passed" and all(row["caught"] for row in result["variants"])
    assert path.read_bytes() == original


def test_uncaught_variant_is_a_toothless_risk(tmp_path, monkeypatch):
    request = closure_input(complete_chain(tmp_path))
    real = known_bad._first_rejection

    def leak_is_never_caught(text, value):
        if known_bad._INTERNAL_TERM in text:
            return dict(caught=False, step=None)
        return real(text, value)

    monkeypatch.setattr(known_bad, "_first_rejection", leak_is_never_caught)
    uncaught = [row for row in check_known_bad(request)["variants"] if not row["caught"]]
    assert [row["kind"] for row in uncaught] == ["leak"]
    closure = derive_closure(request)["closure"]
    toothless = [row["defect_id"] for row in closure["residual_risk"] if row["defect_id"].startswith("toothless:")]
    assert toothless == ["toothless:leak:leak"]
    assert closure["status"] == "passed"
