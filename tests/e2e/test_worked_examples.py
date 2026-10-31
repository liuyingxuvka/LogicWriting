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
    for name, request in {
        'map-request.json': {'artifact_path': 'piece.md', 'map_id': 'map:single', 'language': 'en', 'artifact_format': 'markdown'},
        'audit-request.json': {'audit_id': 'audit:single', 'artifact_map': 'artifact-map.json', 'reader_brief': 'reader-brief.json', 'shared_writing': 'shared-writing-result.json'},
    }.items():
        path = folder / name
        if not path.exists(): path.write_text(json.dumps(request))
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


@pytest.mark.parametrize("route", ["investigation", "academic", "fiction", "travel"])
def test_worked_example(tmp_path, route):
    source = EXAMPLES / route
    # Native research/trip inputs and generated mutation catalogs now accompany the same short piece.
    print(
        f"{route}: piece.md {(source / 'piece.md').stat().st_size} bytes, example folder {sum(p.stat().st_size for p in source.rglob('*') if p.is_file())} bytes"
    )
    folder = tmp_path / route
    shutil.copytree(source, folder)
    code, result = run_chain(folder, route)
    assert code == 0, result
    assert result["closure"]["status"] == "passed", result
    assert result["closure"]["broad_claim_allowed"] is False  # honest self-review
    expected = json.loads((folder / "known-bad/expected.json").read_text())
    for filename, expectation in expected.items():
        shutil.copyfile(source / "known-bad" / filename, folder / "piece.md")
        code, result = run_chain(folder, route, expectation["step"])
        if "code" in expectation:
            assert expectation["code"] in {r["code"] for r in result["reader_audit"]["findings"]}, (
                filename,
                result,
            )
            assert result["reader_audit"]["status"] != "passed"
        else:
            assert code != 0, (filename, result)
            assert expectation["error"] in result["errors"], (filename, result)


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


@pytest.mark.parametrize("route", ["investigation", "academic", "fiction", "travel"])
def test_show_plan_reads_every_chain_file(tmp_path, route):
    folder = tmp_path / route
    shutil.copytree(EXAMPLES / route, folder)
    code, review = run_chain(folder, route, "review")
    assert code == 0, review
    plan = json.loads((folder / "brief-request.json").read_text())["composition_plan"]
    summary = None
    for filename in (
        "reader-brief.json",
        "shared-writing.json",
        "shared-writing-result.json",
        "audit-request.json",
    ):
        run = subprocess.run(
            [
                sys.executable,
                str(SKILL / "scripts/show_plan.py"),
                "--input",
                str(folder / filename),
            ],
            cwd=SKILL,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert run.returncode == 0, (filename, run.stdout, run.stderr)
        assert plan["central_question"] in run.stdout
        current = run.stdout.splitlines()[0]
        if summary is None:
            summary = current
        assert current == summary

    if route == "investigation":
        from copy import deepcopy

        saved = json.loads((folder / "shared-writing-result.json").read_text())["shared_writing"]
        bad_request = folder / "show-plan-invalid-binding.json"
        for kind in ("unknown_plan", "unknown_artifact", "missing_quote", "ambiguous_quote"):
            contract = deepcopy(saved)
            contract.pop("contract_fingerprint", None)
            binding = contract["unit_bindings"][0]
            if kind == "unknown_plan":
                binding["planned_unit_id"] = "planned-unit-that-does-not-exist"
            elif kind == "unknown_artifact":
                binding["artifact_unit_ids"] = ["artifact:missing"]
            else:
                binding.pop("artifact_unit_ids", None)
                binding.pop("artifact_spans", None)
                binding["anchor_excerpts"] = (
                    ["free-threaded"]
                    if kind == "ambiguous_quote"
                    else ["A quotation that is absent from this current article."]
                )
            bad_request.write_text(
                json.dumps(
                    dict(
                        reader_brief="reader-brief.json",
                        artifact_map="artifact-map.json",
                        shared_writing=contract,
                    )
                )
            )
            run = subprocess.run(
                [sys.executable, str(SKILL / "scripts/show_plan.py"), "--input", str(bad_request)],
                cwd=SKILL,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert run.returncode == 2, (kind, run.stdout, run.stderr)
            assert run.stdout.startswith("show_plan: ") and "Traceback" not in run.stderr
        piece = folder / "piece.md"
        original = piece.read_bytes()
        try:
            piece.write_bytes(original + b"\n")
            run = subprocess.run(
                [
                    sys.executable,
                    str(SKILL / "scripts/show_plan.py"),
                    "--input",
                    str(folder / "shared-writing-result.json"),
                ],
                cwd=SKILL,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert run.returncode == 2 and "stale" in run.stdout
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


def test_show_plan_names_anchors_per_says_line(tmp_path):
    sys.path.insert(0, str(SKILL / "scripts"))
    from show_plan import plan_view, render_plan

    folder = tmp_path / "investigation"
    shutil.copytree(EXAMPLES / "investigation", folder)
    path = folder / "brief-request.json"
    request = json.loads(path.read_text())
    meaning = "Teams should move production services to the free-threaded build this year."
    request["content_boundaries"]["content_units"].append({
        "content_unit_id": "cu-migrate", "safe_meaning": meaning, "required": True,
        "source": "ai",
        "evidence_anchor_ids": [], "alternative_ids": [], "limitation_ids": [],
        "model_row_ids": [],
    })
    unit = next(row for row in request["composition_plan"]["planned_units"]
                if row["planned_unit_id"] == "u-recommend")
    unit["content_unit_ids"].append("cu-migrate")
    path.write_text(json.dumps(request))

    view = plan_view(request, input_path=path)
    lines = [line.strip() for line in render_plan(view).splitlines()]
    supported = next(row["safe_meaning"]
                     for row in request["content_boundaries"]["content_units"]
                     if row["content_unit_id"] == "cu-recommend")
    assert f"says: {meaning} [no anchor]" in lines
    assert f"says: {supported} [anc-314-supported (support), anc-314-phase3-undecided (limit)]" in lines
    assert not any(line.startswith("anchors:") for line in lines)


def test_show_plan_shows_findings_on_the_failing_unit(tmp_path):
    sys.path.insert(0, str(SKILL / 'scripts'))
    from _common import load_request
    from show_plan import plan_view, render_plan
    from tests.v2_support import run_example_steps
    folder = tmp_path / 'investigation'
    shutil.copytree(EXAMPLES / 'investigation', folder)
    code, _closure = run_chain(folder, 'investigation')
    assert code == 0
    view = plan_view(load_request(folder / 'closure-input.json', defaults=__import__('derive_closure').CLOSURE_INPUT_FILES), input_path=folder / 'closure-input.json')
    first = render_plan(view).splitlines()[0]
    assert first.startswith('units: 5 (5 bound, 0 unbound); audit: passed')
    assert 'closure: passed' in first and first.endswith('known-bad: 0 uncaught')
    assert all(unit['anchors'] for unit in view['planned_units'])
    # A result file made from other bytes is stale, never shown as current.
    piece = folder / 'piece.md'
    original = piece.read_text(encoding='utf-8')
    piece.write_text(original + '\nAn added closing sentence for the stale check.\n', encoding='utf-8')
    run_example_steps(folder, 'shared_writing')
    stale = plan_view(load_request(folder / 'closure-input.json', defaults=__import__('derive_closure').CLOSURE_INPUT_FILES), input_path=folder / 'closure-input.json')
    assert 'audit: stale' in stale['summary'] and 'closure: stale' in stale['summary']
    piece.write_text(original, encoding='utf-8')
    # The known-bad leak text, audited: the leaking unit shows workflow_leak under it.
    shutil.copyfile(EXAMPLES / 'investigation/known-bad/leak.md', piece)
    audit = run_example_steps(folder)['audit']['reader_audit']
    assert audit['status'] == 'repair'
    view = plan_view(load_request(folder / 'audit-request.json'), input_path=folder / 'audit-request.json')
    leaking = [unit['planned_unit_id'] for unit in view['planned_units']
               if any(row['code'] == 'workflow_leak' for row in unit['findings'])]
    assert len(leaking) == 1
    assert 'audit: repair' in view['summary'] and 'review: stale' in view['summary']
    assert 'findings: workflow_leak' in render_plan(view)


def test_show_plan_reads_back_while_the_plan_is_ahead(tmp_path,monkeypatch,capsys):
    import copy,hashlib
    from _common import cli_validate
    from validate_shared_writing import validate_shared_writing
    from tests.v2_support import run_example_steps
    from show_plan import main,render_plan
    def view(path):
        with monkeypatch.context() as patch:
            patch.setattr(sys,'argv',['show_plan.py','--input',str(path),'--json'])
            assert main()==0
        return json.loads(capsys.readouterr().out)
    folder=tmp_path/'ahead'
    shutil.copytree(EXAMPLES/'investigation',folder)
    run_example_steps(folder,until='review')
    healthy=view(folder/'shared-writing-result.json')
    rendered=render_plan(healthy)
    assert 'checks: limitation lim-perf: present' in rendered
    assert 'findings: limitation lim-perf: present' not in rendered
    request=json.loads((folder/'brief-request.json').read_text())
    rows=request['composition_plan']['planned_units']
    unit=copy.deepcopy(rows[-1]);unit.update(planned_unit_id='u-libs',order=max(row['order'] for row in rows)+1,title='Libraries',content_unit_ids=[],limitation_ids=[])
    rows.append(unit)
    (folder/'brief-request.json').write_text(json.dumps(request))
    run_example_steps(folder,until='map')
    with monkeypatch.context() as patch:
        patch.setattr(sys,'argv',['validate_shared_writing.py','--input',str(folder/'shared-writing.json'),'--output',str(folder/'shared-writing-result.json')])
        assert cli_validate(validate_shared_writing,'Bind current text')==1
    before={path.relative_to(folder).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in folder.rglob('*') if path.is_file()}
    result=view(folder/'shared-writing-result.json')
    assert len(result['planned_units'])==6
    added=next(row for row in result['planned_units'] if row['planned_unit_id']=='u-libs')
    assert added['new'] and not added['bound']
    assert sum(row['bound'] for row in result['planned_units'])==5
    assert 'u-libs new' in result['summary'] and 'shared_writing: blocked' in result['summary']
    assert before=={path.relative_to(folder).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in folder.rglob('*') if path.is_file()}
    bare=tmp_path/'bare'
    shutil.copytree(EXAMPLES/'investigation',bare)
    names={path.relative_to(bare) for path in bare.rglob('*') if path.is_file()}
    assert not (bare/'route-decision.json').exists()
    assert len(view(bare/'brief-request.json')['planned_units'])==5
    assert names=={path.relative_to(bare) for path in bare.rglob('*') if path.is_file()}


def test_show_plan_reads_back_the_same_from_every_chain_file(tmp_path, monkeypatch, capsys):
    import copy
    import hashlib
    from run_chain import run_chain as run_full_chain
    from show_plan import main

    expected = {
        "ok": "units: 5 (5 bound, 0 unbound); audit: passed (0 findings); review: passed; closure: passed; known-bad: 0 uncaught",
        "inv": "units: 6 (5 bound, 1 unbound: u-libs new); shared_writing: blocked (required planned units are unbound: ['u-libs']); audit: not_run; review: not_run; closure: not_run; known-bad: not_run",
    }
    for name in ("ok", "inv"):
        folder = tmp_path / name
        shutil.copytree(EXAMPLES / "investigation", folder)
        if name == "inv":
            path = folder / "brief-request.json"
            request = json.loads(path.read_text())
            rows = request["composition_plan"]["planned_units"]
            unit = copy.deepcopy(rows[-1])
            unit.update(
                planned_unit_id="u-libs",
                order=max(row["order"] for row in rows) + 1,
                title="Libraries",
                content_unit_ids=[],
                limitation_ids=[],
            )
            rows.append(unit)
            path.write_text(json.dumps(request))
        result = run_full_chain(folder)
        assert result["exit_code"] == (0 if name == "ok" else 1)
        before = {
            p.relative_to(folder): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*")
            if p.is_file()
        }
        summaries = []
        for filename in (
            "brief-request.json",
            "reader-brief.json",
            "closure-input.json",
            "shared-writing.json",
            "shared-writing-result.json",
        ):
            with monkeypatch.context() as patch:
                patch.setattr(
                    sys, "argv", ["show_plan.py", "--input", str(folder / filename), "--json"]
                )
                assert main() == 0
            summaries.append(json.loads(capsys.readouterr().out)["summary"])
        assert summaries == [expected[name]] * 5
        after = {
            p.relative_to(folder): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*")
            if p.is_file()
        }
        assert before == after
