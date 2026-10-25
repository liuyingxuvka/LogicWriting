from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint, fingerprint_text
from artifact_map import build_artifact_map
from reader_checks import build_reader_audit, validate_reader_judgment
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
    judgment["judge_kind"] = "independent_context"
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


def test_brief_request_fills_plan_and_route_fingerprints(tmp_path):
    from build_reader_brief import validate_request as build_brief_request

    chain = make_reader_chain(tmp_path)
    plan = copy.deepcopy(chain["plan"])
    route = copy.deepcopy(chain["route_composition"])
    for field in ("reader_intent_fingerprint", "plan_fingerprint"):
        del plan[field]
    for field in ("reader_intent_fingerprint", "composition_plan_fingerprint", "extension_fingerprint"):
        del route[field]
    result = build_brief_request({
        "route_decision": chain["route_decision"],
        "content_boundaries": chain["reader_brief"]["content_boundaries"],
        "composition_plan": plan,
        "route_composition": route,
        "brief_id": chain["reader_brief"]["brief_id"],
    })
    assert result["status"] == "current_pass"
    assert result["reader_brief"]["brief_fingerprint"] == chain["reader_brief"]["brief_fingerprint"]
    assert result["route_composition"] == chain["route_composition"]


def test_forbidden_pattern_is_an_audit_finding(tmp_path):
    from tests.v2_support import complete_chain
    from reader_checks import _build_reader_audit_from_current
    chain = complete_chain(tmp_path, language='en')
    brief = chain['reader_brief']
    brief['content_boundaries']['prohibited_overclaims'] = [dict(overclaim_id='oc:problem', forbidden_patterns=[r'REAL\s+PROBLEM'])]
    result = _build_reader_audit_from_current(audit_id='audit:patterns', amap=chain['artifact_map'], brief=brief,
                                             contract=chain['shared_writing'])
    finding = next(f for f in result['findings'] if f['code'] == 'overclaim_pattern')
    assert 'oc:problem' in finding['message']
    assert result['quality_dimensions']['claim_boundaries'] == 'repair'


def test_show_plan_prints_every_planned_unit(tmp_path):
    from tests.v2_support import make_reader_chain
    from show_plan import plan_view, render_plan
    chain = make_reader_chain(tmp_path)
    view = plan_view({k:chain[k] for k in ('reader_brief', 'artifact_map', 'shared_writing')})
    assert len(view['planned_units']) == len(chain['plan']['planned_units'])
    text = render_plan(view)
    assert chain['plan']['central_question'] in text
    assert chain['paragraph']['text'][:40] in text
    chain['shared_writing']['unit_bindings'] = []
    assert 'UNBOUND' in render_plan(plan_view({k:chain[k] for k in ('reader_brief', 'artifact_map', 'shared_writing')}))


def test_audit_finds_text_out_of_plan_order(tmp_path):
    import shutil
    from pathlib import Path
    from tests.v2_support import run_example_steps, swap_sections
    example = Path(__file__).resolve().parents[2] / "skills/logic-writing/assets/examples/investigation"
    folder = tmp_path / "investigation"
    shutil.copytree(example, folder)
    audit = run_example_steps(folder)["audit"]["reader_audit"]
    assert audit["status"] == "passed" and audit["quality_dimensions"]["plan_order"] == "passed"
    # Quote bindings follow the moved paragraphs; only their order in the text changes.
    swap_sections(folder / "piece.md", "## What it costs", "## Will it become the default?")
    audit = run_example_steps(folder)["audit"]["reader_audit"]
    assert audit["status"] == "repair"
    mismatch = [row for row in audit["findings"] if row["code"] == "plan_order_mismatch"]
    assert len(mismatch) == 1 and "comes after" in mismatch[0]["message"]
    assert audit["quality_dimensions"]["plan_order"] == "repair"


def test_relation_variants_are_generated_and_caught(tmp_path):
    import json
    import shutil
    from pathlib import Path
    from _common import load_request
    from known_bad import check_known_bad
    from tests.v2_support import run_example_steps
    examples = Path(__file__).resolve().parents[2] / "skills/logic-writing/assets/examples"

    def variants(route, edit=None):
        folder = tmp_path / route
        shutil.rmtree(folder, ignore_errors=True)
        shutil.copytree(examples / route, folder)
        if edit:
            edit(folder)
        run_example_steps(folder, "review")
        result = check_known_bad(load_request(folder / "closure-input.json"))
        return {row["name"]: row for row in result["variants"]}

    fiction = variants("fiction")
    assert fiction["swap"]["caught"] and fiction["swap"]["code"] == "plan_order_mismatch"
    assert fiction["noworld-u-unlock"]["caught"]
    investigation = variants("investigation")
    assert investigation["swap"]["code"] == "plan_order_mismatch"
    assert not any(name.startswith(("noworld-", "noalt-")) for name in investigation)

    def live_alternative(folder):
        request = json.loads((folder / "brief-request.json").read_text(encoding="utf-8"))
        request["content_boundaries"]["alternatives"][0]["status"] = "live"
        (folder / "brief-request.json").write_text(json.dumps(request), encoding="utf-8")
    live = variants("investigation", live_alternative)
    assert live["noalt-alt-default-soon"]["caught"]
    assert all(row["caught"] for row in live.values())
