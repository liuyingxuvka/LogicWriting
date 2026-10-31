"""Known-bad edits of the user's piece: existing words only, original untouched, uncaught ones listed."""
from __future__ import annotations

from pathlib import Path
import re
import json
import shutil
from copy import deepcopy

import known_bad
from derive_closure import CLOSURE_INPUT_FILES, derive_closure
from _common import load_request
from reader_plan import validate_evidence_boundaries
from reader_fill import fill_closure_fingerprints
from run_chain import run_chain
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


def _evidence_request(tmp_path, *, unhardened=False):
    source = Path(__file__).resolve().parents[2] / 'skills/logic-writing/assets/examples/investigation'
    folder = tmp_path / 'investigation'
    shutil.copytree(source, folder)
    if unhardened:
        path = folder / 'brief-request.json'
        request = json.loads(path.read_text())
        request['content_boundaries']['prohibited_overclaims'] = [row for row in request['content_boundaries']['prohibited_overclaims']
                                                                 if row['overclaim_id'] != 'oc-unsupported-default-soon']
        path.write_text(json.dumps(request))
        path = folder / 'route-review.json'
        review = json.loads(path.read_text())
        review['review']['overclaim_checks'] = [row for row in review['review']['overclaim_checks']
                                                if row['overclaim_id'] != 'oc-unsupported-default-soon']
        path.write_text(json.dumps(review))
    assert run_chain(folder, until='review')['exit_code'] == 0
    return fill_closure_fingerprints(load_request(folder / 'closure-input.json', defaults=CLOSURE_INPUT_FILES))


def test_unsupported_alternative_variant_is_generated(tmp_path):
    request = _evidence_request(tmp_path)
    path = Path(request['artifact_map']['artifact_path'])
    original = path.read_bytes()
    cases = text_variants(original.decode(), reader_brief=request['reader_brief'], artifact_map=request['artifact_map'],
                          shared_writing=request['shared_writing'], route_review=request['route_review'])
    rows = [row for row in cases if row['name'] == 'unsupported-alt-default-soon']
    assert len(rows) == 1
    meaning = next(row['safe_meaning'] for row in request['reader_brief']['content_boundaries']['alternatives']
                   if row['alternative_id'] == 'alt-default-soon')
    assert rows[0]['text'] != original.decode()
    assert rows[0]['text'].replace(' ' + meaning, '', 1) == original.decode()
    assert path.read_bytes() == original


def test_uncaught_unsupported_variant_is_toothless(tmp_path):
    request = _evidence_request(tmp_path, unhardened=True)
    rows = check_known_bad(request)['variants']
    assert any(row['name'] == 'unsupported-alt-default-soon' and not row['caught'] for row in rows)
    closure = derive_closure(request)['closure']
    assert closure['status'] == 'passed'
    assert any(row['defect_id'] == 'toothless:unsupported:alt-default-soon'
               and row['owner'] == 'investigation' for row in closure['residual_risk'])


def test_noanchor_variant_is_caught_by_the_brief(tmp_path, monkeypatch):
    request = _evidence_request(tmp_path)
    before = deepcopy(request)
    observations = []
    def observe(brief):
        observations.append(deepcopy(brief))
        return validate_evidence_boundaries(brief)
    monkeypatch.setattr(known_bad, 'validate_evidence_boundaries', observe, raising=False)
    directory = tmp_path / 'catalog'
    rows = check_known_bad(request, write_catalog=directory)['variants']
    row = next((row for row in rows if row['name'] == 'noanchor-cu-perf'), None)
    assert row is not None
    assert row['caught'] and row['step'] == 'brief' and row['code'] == 'content_unit_unsupported'
    changed = deepcopy(request['reader_brief'])
    next(unit for unit in changed['content_boundaries']['content_units'] if unit['content_unit_id'] == 'cu-perf')['evidence_anchor_ids'] = []
    assert changed in observations
    assert request == before
    assert json.loads((directory / 'noanchor-cu-perf.json').read_text()) == {
        'content_unit_id': 'cu-perf', 'evidence_anchor_ids': []}
    assert not (directory / 'noanchor-cu-perf.md').exists()
