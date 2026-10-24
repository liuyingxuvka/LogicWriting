from __future__ import annotations

import copy

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
    original_audit = reader_checks._build_reader_audit_from_current
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
    monkeypatch.setattr(closure_module, "_build_reader_audit_from_current", audited)
    monkeypatch.setattr(reader_checks, "_build_reader_audit_from_current", audited)
    result = derive_closure(request)
    assert calls == {"map": 1, "audit": 1}
    def changed_during_audit(**kwargs):
        report = original_audit(**kwargs)
        artifact = Path(chain["artifact_map"]["artifact_path"])
        artifact.write_bytes(artifact.read_bytes() + b"changed")
        return report
    monkeypatch.setattr(closure_module, "_build_reader_audit_from_current", changed_during_audit)
    with pytest.raises(ValidationError, match="stale during closure"):
        derive_closure(request)
    assert result["closure"]["status"] == "passed"
    assert result["closure"]["broad_claim_allowed"] is True


def test_quality_failure_needs_repair(tmp_path):
    result = derive_closure(closure_input(complete_chain(tmp_path, pass_quality=False)))
    assert result["closure"]["status"] == "needs_repair"
    assert result["closure"]["next_actions"] == [{"owner": "investigation", "action": "repair_and_rerun"}]


def test_cli_exits_nonzero_unless_closure_passed(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path
    script = Path(__file__).resolve().parents[2] / "skills" / "logic-writing" / "scripts" / "derive_closure.py"
    for pass_quality, expected in ((True, 0), (False, 1)):
        workdir = tmp_path / ("pass" if pass_quality else "fail")
        workdir.mkdir()
        request = workdir / "closure-input.json"
        request.write_text(json.dumps(closure_input(complete_chain(workdir, pass_quality=pass_quality))), encoding="utf-8")
        run = subprocess.run([sys.executable, str(script), "--input", str(request)], capture_output=True, text=True)
        assert run.returncode == expected, run.stdout + run.stderr
        payload = json.loads(run.stdout)
        assert payload["status"] == payload["closure"]["status"]
        assert payload["errors"] == payload["warnings"] == []
    output = tmp_path / "blocked.json"
    request.write_text(json.dumps({"artifact_map": "missing-map.json"}))
    run = subprocess.run([sys.executable, str(script), "--input", str(request), "--output", str(output)], capture_output=True, text=True)
    assert run.returncode == 2
    payload = json.loads(output.read_text())
    assert payload["status"] == "blocked" and len(payload["errors"]) == 1 and payload["warnings"] == []


def test_repeating_closure_does_not_count_as_repair(tmp_path):
    request = closure_input(complete_chain(tmp_path, pass_quality=False))
    first = derive_closure(request)
    second = derive_closure(request)
    assert first["closure"]["status"] == second["closure"]["status"] == "needs_repair"


def test_foreign_reader_intent_is_rejected(tmp_path):
    request = closure_input(complete_chain(tmp_path))
    request["reader_brief"] = copy.deepcopy(request["reader_brief"])
    request["reader_brief"]["reader_intent_fingerprint"] = fingerprint({"foreign": True})
    with pytest.raises(ValidationError):
        derive_closure(request)


def test_closure_command_fills_judgment_and_provenance_fingerprints(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    from _common import fingerprint_without

    request = closure_input(complete_chain(tmp_path))
    judgment = request["judgment"]
    for field in [key for key in judgment if key.endswith("_fingerprint")]:
        del judgment[field]
    for row in [*judgment["reverse_outline"], *judgment["defects"], *judgment["strengths"]]:
        row["evidence"].pop("locator", None)
        row["evidence"].pop("excerpt_fingerprint", None)
    provenance = request["revision_provenance"]
    for field in ("reader_intent_fingerprint", "target_artifact_fingerprint", "provenance_fingerprint"):
        del provenance[field]
    path = tmp_path / "closure-input.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    script = Path(__file__).resolve().parents[2] / "skills" / "logic-writing" / "scripts" / "derive_closure.py"
    run = subprocess.run([sys.executable, str(script), "--input", str(path)], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    closure = json.loads(run.stdout)["closure"]
    assert closure["status"] == "passed"
    assert closure["revision_provenance_fingerprint"].startswith("sha256:")

    from reader_fill import fill_closure_fingerprints

    filled = fill_closure_fingerprints(json.loads(path.read_text(encoding="utf-8")))
    assert filled["judgment"]["judgment_fingerprint"] == fingerprint_without(filled["judgment"], "judgment_fingerprint")
    assert closure["judgment_fingerprint"] == filled["judgment"]["judgment_fingerprint"]


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


def test_missing_required_provider_report_blocks_the_broad_claim(tmp_path):
    request = closure_input(complete_chain(tmp_path))
    request.pop('provider_reports')
    result = derive_closure(request)['closure']
    assert result['status'] == 'passed'
    assert not result['broad_claim_allowed']
    assert result['provider_checks'] == [dict(provider='researchguard', path=None, status='not_run', passed=False, required=True, reason='researchguard report is missing: not_run')]
    assert result['residual_risk'][0]['defect_id'] == 'provider:researchguard'


def _research_document(*, withhold=False):
    from pathlib import Path
    import json
    document = json.loads((Path(__file__).resolve().parents[2] / "skills/logic-writing/assets/examples/investigation/research-status.json").read_text())
    if withhold:
        document["verdict"]["root_claim"] = {"id": "h-main-answer", "wording_license": "withhold", "reason": "Native counterevidence remains."}
        document["verdict"]["live_hypotheses"].append("h-other")
        document["hypotheses"].append({"id": "h-other"})
    return document


@pytest.mark.parametrize('provider,document,status', [
    ('researchguard', _research_document(), 'passed'),
    ('worldguard', {'status': 'FAIL', 'contract_id': 'old-market-day'}, 'FAIL'),
    ('researchguard', _research_document(withhold=True), 'failed'),
    ('researchguard', {}, 'unreadable'),
])
def test_provider_status_is_copied_from_the_report_file(tmp_path, provider, document, status):
    import json
    request = closure_input(complete_chain(tmp_path, 'travel-guide' if provider == 'worldguard' else 'investigation'))
    path = tmp_path / 'report.json'
    path.write_text(json.dumps(document))
    request['provider_reports'] = [row for row in request['provider_reports'] if row['provider'] != provider]
    request['provider_reports'].append(dict(provider=provider, path=str(path)))
    result = derive_closure(request)['closure']
    row = result['provider_checks'][-1]
    assert row['status'] == status
    assert result['broad_claim_allowed'] == (status == 'passed')
    assert f'{provider} {status}' in result['safe_claim']
    if status != 'passed':
        risk = next(r for r in result['residual_risk'] if r['defect_id'] == f'provider:{provider}')
        assert risk['reason']
        if document.get('verdict', {}).get('root_claim'):
            assert document['verdict']['root_claim']['reason'] in risk['reason']
    elif provider == 'researchguard':
        assert any(r['defect_id'] == 'research:root_claim_not_run' for r in result['residual_risk'])


@pytest.mark.parametrize('contents', [None, 'not json', '[]'])
def test_unreadable_report_is_not_a_pass(tmp_path, contents):
    from derive_closure import provider_checks
    path = tmp_path / 'missing.json'
    if contents is not None:
        path.write_text(contents)
    rows, risks, passed = provider_checks('investigation', {}, {}, [{'provider': 'researchguard', 'path': str(path)}])
    assert not passed and rows[0]['status'] == 'unreadable' and risks


def test_required_providers_follow_live_alternatives_and_fiction_opt_in():
    from derive_closure import required_providers
    live = {'content_boundaries': {'alternatives': [{'status': 'live'}]}}
    assert required_providers('investigation', live, {}) == {'researchguard'}
    assert required_providers('academic-writing', live, {}) == {'researchguard'}
    assert not required_providers('academic-writing', {}, {})
    assert required_providers('academic-writing', {'research_folder': 'native-question'}, {}) == {'researchguard'}
    assert required_providers('fiction-writing', {}, {'world_check_required': True}) == {'worldguard'}
    assert not required_providers('fiction-writing', {}, {})
    assert required_providers('travel-guide', {}, {}) == {'worldguard'}


def test_failing_world_report_limits_the_travel_closure(tmp_path):
    import json
    import sys
    from pathlib import Path
    route = Path(__file__).resolve().parents[2] / 'skills/logic-writing/routes/travel'
    if str(route / 'scripts') not in sys.path:
        sys.path.insert(0, str(route / 'scripts'))
    from fixture_mutation import apply_mutations
    from travel_contract import review_plan
    failed = tmp_path / 'world-fail.json'
    failed.write_text(json.dumps({'status': 'FAIL', 'contract_id': 'old-market-day'}))
    request = closure_input(complete_chain(tmp_path / 'chain', 'travel-guide'))
    request['provider_reports'] = [dict(provider='worldguard', path=str(failed))]
    closure = derive_closure(request)['closure']
    assert closure['provider_checks'][0]['status'] == 'FAIL'
    assert closure['broad_claim_allowed'] is False
    assert any(row['defect_id'] == 'provider:worldguard' for row in closure['residual_risk'])
    plan_path = route / 'examples/good_city_couple_trip/plan.json'
    current = json.loads((route / 'examples/positive_cases/near_future_bookable.json').read_text(encoding='utf-8'))
    plan = apply_mutations(json.loads(plan_path.read_text(encoding='utf-8')), current['mutations'])
    plan['world_feasibility']['checks'][0]['worldguard_report'] = str(failed)
    assert review_plan(plan, plan_path=plan_path)['allowed_claim_level'] == 'initial_plan'


def test_world_report_for_another_contract_fails_closure(tmp_path):
    import json
    from derive_closure import provider_checks
    request = closure_input(complete_chain(tmp_path / 'chain', 'travel-guide'))
    report = tmp_path / 'worldguard-check.json'
    report.write_text(json.dumps({'status': 'PASS', 'contract_id': 'another-world'}))
    request['provider_reports'] = [dict(provider='worldguard', path=str(report))]
    closure = derive_closure(request)['closure']
    assert closure['status'] == 'needs_repair'
    row = closure['provider_checks'][0]
    assert row['status'] == 'failed' and row['reason'].startswith('world_report_mismatch:contract_id')
    risk = next(r for r in closure['residual_risk'] if r['defect_id'] == 'provider:worldguard')
    assert risk['reason'].startswith('world_report_mismatch:contract_id')
    # Without contract_id the contract is named by claim.claim_id, as in WorldGuard.
    world = tmp_path / 'world.yaml'
    world.write_text('claim: {claim_id: c_only}\ninputs: {events: []}\n')
    report.write_text(json.dumps({'status': 'PASS', 'contract_id': 'c_only'}))
    rows, _risks, passed = provider_checks('travel-guide', {}, {'world_contract': str(world)},
                                           [dict(provider='worldguard', path=str(report))])
    assert passed and rows[0]['status'] == 'PASS'
    rows, _risks, passed = provider_checks('travel-guide', {}, {}, [dict(provider='worldguard', path=str(report))])
    assert not passed and rows[0]['reason'].startswith('world_report_unbound:world_contract')
