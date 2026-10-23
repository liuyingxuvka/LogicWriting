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
    assert sum(p.stat().st_size for p in source.rglob('*') if p.is_file()) <= 30_000
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
            assert expectation['error'] in json.dumps(result), (filename, result)
