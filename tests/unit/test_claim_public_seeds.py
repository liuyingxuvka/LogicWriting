"""The complete public prototype corpus, reduced to original bytes and claim bindings.

These examples are no longer blind: explicit known misses are documented rather
than silently relabelled as caught. The native reader owns source interpretation.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from artifact_map import build_artifact_map
from claim_readings import build_sensors, plan_readings, text_readings
from reader_binding import quote_binding_units

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures' / 'claim_readings'
CASES = json.loads((FIXTURES / 'cases.json').read_text(encoding='utf-8'))


def _prepare(case, folder):
    folder.mkdir()
    brief = {'request': case['request'], 'content_boundaries': copy.deepcopy(case['content_boundaries'])}
    if 'capture' in case:
        capture = case['capture']
        research = folder / 'research'
        research.mkdir()
        shutil.copytree(FIXTURES / 'originals' / capture['family'], research / 'captures')
        (research / 'captures.yaml').write_text(capture['manifest'], encoding='utf-8')
        brief['research_folder'] = str(research)
    if 'pg_family' in case:
        pg = folder / 'physics'
        shutil.copytree(FIXTURES / 'originals' / case['pg_family'], pg)
        brief['provider_reports'] = [{'provider': 'physicsguard', 'path': str(pg / 'pg-result.json')}]
    piece = folder / 'piece.md'
    piece.write_text(case['text'], encoding='utf-8')
    artifact = build_artifact_map(piece, map_id='map:public', language='en')
    shared = {'unit_bindings': copy.deepcopy(case['bindings'])}
    units = {row['artifact_unit_id']: row for row in artifact['units']}
    for binding in shared['unit_bindings']:
        if 'artifact_unit_ids' not in binding:
            binding['artifact_unit_ids'] = [row['artifact_unit_id'] for row in quote_binding_units(binding, units)]
    return brief, artifact, shared


@pytest.mark.parametrize('case', CASES, ids=[case['name'] for case in CASES])
def test_all_public_claim_seeds_use_saved_originals(case, tmp_path):
    brief, artifact, shared = _prepare(case, tmp_path / case['name'])
    sensors = build_sensors(brief)
    rows = plan_readings(brief, sensors=sensors) + text_readings(brief, artifact, shared, sensors=sensors)
    red = [row for row in rows if row['colour'] == 'red']
    counts = {colour: sum(row['colour'] == colour for row in rows) for colour in ('green', 'red', 'grey')}
    assert bool(red) is case['expected_red'], {'case': case['name'], 'counts': counts, 'red': red}
    assert counts == case['expected_counts'], {'case': case['name'], 'actual': counts, 'prototype': case['expected_counts']}
    assert int(bool(red)) == case['expected_exit']
    assert any(row['colour'] == 'green' for row in rows), {'case': case['name'], 'rows': rows}
    if case['name'] == 's0_without_captures':
        assert counts['grey'] > 0
    if 'known_limit' in case:
        assert not red, case['known_limit']


def test_public_corpus_keeps_all_eight_original_and_twenty_nine_later_cases():
    assert len(CASES) == 37
    assert sum(case['category'] == 'first-eight' for case in CASES) == 8
    assert sum(case['category'] == 'later-public' for case in CASES) == 29
    assert {case['name'] for case in CASES if 'known_limit' in case} == {
        's4_range_from_other_source', 'lib_swap_years', 'bus_person_noquote', 'bus_half',
    }


def test_public_physics_sources_still_match_the_saved_input_hashes():
    for family in ('heater', 'radiator'):
        base = FIXTURES / 'originals' / family
        report = json.loads((base / 'pg-result.json').read_text(encoding='utf-8'))
        for row in report['input_digests']:
            assert hashlib.sha256((base / row['path']).read_bytes()).hexdigest() == row['sha256'], (family, row['path'])
