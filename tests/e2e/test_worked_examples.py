"""Smoke-check the shipped requests and their small, finite bad-text catalog."""
from pathlib import Path
import json
import shutil
import subprocess
import sys

import pytest

SKILL = Path(__file__).resolve().parents[2] / 'skills/logic-writing'
EXAMPLES = SKILL / 'assets/examples'
STEPS = [
    ('route', 'scripts/select_route.py', 'route-request.json', 'route-decision.json'),
    ('brief', 'scripts/build_reader_brief.py', 'brief-request.json', 'reader-brief.json'),
    ('map', 'scripts/build_artifact_map.py', 'map-request.json', 'artifact-map.json'),
    ('shared_writing', 'scripts/validate_shared_writing.py', 'shared-writing.json', 'shared-writing-result.json'),
    ('audit', 'scripts/audit_reader_output.py', 'audit-request.json', 'audit.json'),
    ('review', 'routes/{route}/scripts/validate_{route}_artifact.py', 'route-review.json', 'route-review-result.json'),
    ('closure', 'scripts/derive_closure.py', 'closure-input.json', 'closure.json'),
]


def run_chain(folder, route, until='closure'):
    outputs = {}
    for step, script, request, output in STEPS:
        run = subprocess.run([sys.executable, str(SKILL / script.format(route=route)),
                              '--input', str(folder / request), '--output', str(folder / output)],
                             cwd=SKILL, capture_output=True, text=True, timeout=30)
        assert (folder / output).exists(), (step, run.stdout, run.stderr)
        result = json.loads((folder / output).read_text())
        outputs[step] = result
        if step == until:
            return run.returncode, result
        assert run.returncode == 0, (step, result, run.stderr)
    return run.returncode, result


@pytest.mark.parametrize('route', ['investigation', 'academic', 'fiction', 'travel'])
def test_worked_example(tmp_path, route):
    source = EXAMPLES / route
    # Native research/trip inputs and generated mutation catalogs now accompany the same short piece.
    assert (source / 'piece.md').stat().st_size <= 10_000
    assert sum(p.stat().st_size for p in source.rglob('*') if p.is_file()) <= 100_000
    folder = tmp_path / route
    shutil.copytree(source, folder)
    code, result = run_chain(folder, route)
    assert code == 0, result
    assert result['closure']['status'] == 'passed', result
    assert result['closure']['broad_claim_allowed'] is False  # honest self-review
    expected = json.loads((folder / 'known-bad/expected.json').read_text())
    for filename, expectation in expected.items():
        shutil.copyfile(source / 'known-bad' / filename, folder / 'piece.md')
        code, result = run_chain(folder, route, expectation['step'])
        if 'code' in expectation:
            assert expectation['code'] in {r['code'] for r in result['reader_audit']['findings']}, (filename, result)
            assert result['reader_audit']['status'] != 'passed'
        else:
            assert code != 0, (filename, result)
            assert expectation['error'] in result['errors'], (filename, result)


@pytest.mark.parametrize('route', ['investigation', 'academic', 'fiction', 'travel'])
def test_known_bad_catalog_is_generated_and_fully_caught(tmp_path, route):
    folder = tmp_path / route
    shutil.copytree(EXAMPLES / route, folder)
    code, review = run_chain(folder, route, 'review')
    assert code == 0, review
    generated = tmp_path / 'generated'
    run = subprocess.run([sys.executable, str(SKILL / 'scripts/known_bad.py'),
                          '--input', str(folder / 'closure-input.json'), '--json',
                          '--write-catalog', str(generated)],
                         cwd=SKILL, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, (run.stdout, run.stderr)
    result = json.loads(run.stdout)
    assert result['variants'] and all(row['caught'] for row in result['variants'])
    expected = EXAMPLES / route / 'known-bad'
    assert {p.name: p.read_bytes() for p in generated.iterdir()} == {
        p.name: p.read_bytes() for p in expected.iterdir()}


@pytest.mark.parametrize('route', ['investigation', 'academic', 'fiction', 'travel'])
def test_show_plan_reads_every_chain_file(tmp_path, route):
    folder = tmp_path / route
    shutil.copytree(EXAMPLES / route, folder)
    code, review = run_chain(folder, route, 'review')
    assert code == 0, review
    plan = json.loads((folder / 'brief-request.json').read_text())['composition_plan']
    for filename in ('reader-brief.json', 'shared-writing.json',
                     'shared-writing-result.json', 'audit-request.json'):
        run = subprocess.run([sys.executable, str(SKILL / 'scripts/show_plan.py'),
                              '--input', str(folder / filename)],
                             cwd=SKILL, capture_output=True, text=True, timeout=30)
        assert run.returncode == 0, (filename, run.stdout, run.stderr)
        assert plan['central_question'] in run.stdout
        if filename == 'reader-brief.json':
            assert run.stdout.count('UNBOUND') == len(plan['planned_units'])

    if route == 'investigation':
        from copy import deepcopy

        saved = json.loads((folder / 'shared-writing-result.json').read_text())['shared_writing']
        bad_request = folder / 'show-plan-invalid-binding.json'
        for kind in ('unknown_plan', 'unknown_artifact', 'missing_quote', 'ambiguous_quote'):
            contract = deepcopy(saved)
            contract.pop('contract_fingerprint', None)
            binding = contract['unit_bindings'][0]
            if kind == 'unknown_plan':
                binding['planned_unit_id'] = 'planned-unit-that-does-not-exist'
            elif kind == 'unknown_artifact':
                binding['artifact_unit_ids'] = ['artifact:missing']
            else:
                binding.pop('artifact_unit_ids', None)
                binding.pop('artifact_spans', None)
                binding['anchor_excerpts'] = (['free-threaded'] if kind == 'ambiguous_quote'
                    else ['A quotation that is absent from this current article.'])
            bad_request.write_text(json.dumps(dict(reader_brief='reader-brief.json',
                artifact_map='artifact-map.json', shared_writing=contract)))
            run = subprocess.run([sys.executable, str(SKILL / 'scripts/show_plan.py'),
                                  '--input', str(bad_request)], cwd=SKILL,
                                 capture_output=True, text=True, timeout=30)
            assert run.returncode == 2, (kind, run.stdout, run.stderr)
            assert run.stdout.startswith('show_plan: ') and 'Traceback' not in run.stderr
        piece = folder / 'piece.md'
        original = piece.read_bytes()
        try:
            piece.write_bytes(original + b'\n')
            run = subprocess.run([sys.executable, str(SKILL / 'scripts/show_plan.py'),
                                  '--input', str(folder / 'shared-writing-result.json')],
                                 cwd=SKILL, capture_output=True, text=True, timeout=30)
            assert run.returncode == 2 and 'stale' in run.stdout
        finally:
            piece.write_bytes(original)


def test_saved_research_status_matches_researchguard():
    """The shipped research-status.json is exactly what the installed ResearchGuard writes for its folder."""
    import shutil as _shutil
    console = _shutil.which('researchguard')
    assert console, 'the researchguard console must be installed (both CI jobs install ResearchGuard)'
    folder = EXAMPLES / 'investigation'
    run = subprocess.run([console, 'status', str(folder / 'research'), '--json'],
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stdout + run.stderr
    assert json.loads(run.stdout) == json.loads((folder / 'research-status.json').read_text(encoding='utf-8'))
