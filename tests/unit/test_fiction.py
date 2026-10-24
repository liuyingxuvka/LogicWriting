from __future__ import annotations

import importlib.util
import copy
import json
import subprocess

import pytest
from pathlib import Path

from select_route import select_route
from tests.v2_support import make_reader_chain, route_request
from _common import ValidationError
from build_reader_brief import validate_request as build_brief_request


ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "skills" / "logic-writing" / "routes" / "fiction"


def _fiction_regression_module():
    path = ROOT / "scripts" / "run_fiction_regression.py"
    spec = importlib.util.spec_from_file_location("logic_writing_fiction_regression", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fiction_route_pack_is_internal_not_installable():
    assert ROUTE.is_dir()
    assert not (ROUTE / "SKILL.md").exists()
    assert not (ROUTE / "agents").exists()


def test_fiction_route_keeps_final_ownership_over_bounded_research():
    decision = select_route(route_request("novel", research=True))
    assert decision["final_owner"] == "fiction-writing"
    assert decision["child_routes"] == ["investigation"]


def test_native_fiction_binding_rejects_unbound_prose(tmp_path):
    from validate_shared_writing import validate_shared_writing
    chain = make_reader_chain(tmp_path, "fiction-writing")
    source = copy.deepcopy(chain["shared_writing"])
    source["unit_bindings"][0].pop("artifact_unit_ids")
    source["unit_bindings"][0].pop("artifact_spans")
    source["unit_bindings"][0]["anchor_excerpts"] = ["An invented sentence that is absent from the actual manuscript."]
    source.pop("contract_fingerprint", None)
    with pytest.raises(ValidationError, match="is not in the current text"):
        validate_shared_writing({"contract": source, "artifact_map": chain["artifact_map"], "reader_brief": chain["reader_brief"]})


def test_fiction_regression_timeout_kills_the_case(monkeypatch, tmp_path: Path):
    module = _fiction_regression_module()

    class FakeProcess:
        pid = 321
        returncode = -9

        def __init__(self):
            self.communicate_calls = []
            self.killed = False

        def kill(self):
            self.killed = True

        def communicate(self, timeout=None):
            self.communicate_calls.append(timeout)
            if len(self.communicate_calls) == 1:
                raise subprocess.TimeoutExpired(["fake-owner"], timeout)
            return "all output", "all diagnostics"

    process = FakeProcess()
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: process)
    result = module._run_case(["fake-owner"], tmp_path, 1)
    assert result["timed_out"] is True
    assert process.killed is True
    assert result["stdout"] == "all output"
    assert result["stderr"] == "all diagnostics"
    assert process.communicate_calls == [1, 30]


def test_longform_binding_negative_cannot_pass_from_input_failure(tmp_path):
    from validate_shared_writing import validate_shared_writing
    # A malformed envelope is an input failure, never the intended unbound-unit proof.
    with pytest.raises(ValidationError) as caught:
        validate_shared_writing({})
    assert "required planned units are unbound" not in str(caught.value)



def _fiction_brief_request(chain, route):
    return {
        "route_decision": copy.deepcopy(chain["route_decision"]),
        "content_boundaries": copy.deepcopy(chain["reader_brief"]["content_boundaries"]),
        "composition_plan": copy.deepcopy(chain["plan"]),
        "route_composition": route,
        "brief_id": "brief:voice-contract",
    }


def test_voice_contract_reaches_the_writer_without_a_gap(tmp_path):
    chain = make_reader_chain(tmp_path, "fiction-writing")
    assert any(row["reason"] == "fiction voice reference has no current POV/voice payload"
               for row in chain["reader_brief"]["writer_input"]["gaps"])
    voice = {"pov": "close third person", "tense": "past", "narration_distance": "close",
             "register": "plain", "allowed_variation": ["short fragments"]}
    route = copy.deepcopy(chain["route_composition"])
    route["voice_contract"] = voice
    route.pop("extension_fingerprint")
    first = build_brief_request(_fiction_brief_request(chain, route))["reader_brief"]
    assert first["writer_input"]["gaps"] == []
    assert first["writer_input"]["route_semantics"]["voice"] == voice
    changed = copy.deepcopy(route)
    changed["voice_contract"]["tense"] = "present"
    with pytest.raises(ValidationError, match="extension_fingerprint"):
        build_brief_request(_fiction_brief_request(chain, changed))
    changed.pop("extension_fingerprint")
    second = build_brief_request(_fiction_brief_request(chain, changed))["reader_brief"]
    assert second["route_extension"]["extension_fingerprint"] != first["route_extension"]["extension_fingerprint"]
    assert second["brief_fingerprint"] != first["brief_fingerprint"]


def test_voice_reference_must_be_an_identifier(tmp_path):
    chain = make_reader_chain(tmp_path, "fiction-writing")
    route = copy.deepcopy(chain["route_composition"])
    route["voice_contract_ref"] = "close third, Tova"
    route.pop("extension_fingerprint")
    with pytest.raises(ValidationError, match=r"\$\.voice_contract_ref"):
        build_brief_request(_fiction_brief_request(chain, route))


def test_unit_plans_take_shared_fields_from_the_planned_units(tmp_path):
    chain = make_reader_chain(tmp_path, "fiction-writing")
    request = _fiction_brief_request(chain, copy.deepcopy(chain["route_composition"]))
    route = request["route_composition"]
    fields = ("contribution", "reader_state_before", "reader_state_after", "downstream_unit_ids", "open_questions_in", "open_questions_out", "prohibited_reveals")
    for row in route["unit_plans"]:
        for field in fields:
            row.pop(field, None)
    route.pop("extension_fingerprint")
    result = build_brief_request(request)
    unit = result["composition_plan"]["planned_units"][0]
    row = result["route_composition"]["unit_plans"][0]
    assert row["contribution"] == unit["reader_job"]
    assert row["reader_state_before"] == unit["incoming_reader_state"]
    assert row["reader_state_after"] == unit["outgoing_reader_state"]
    assert row["downstream_unit_ids"] == unit["downstream_unit_ids"]
    assert row["open_questions_in"] == row["open_questions_out"] == row["prohibited_reveals"] == []


def test_worldguard_status_comes_from_native_reports(tmp_path, monkeypatch):
    import shutil
    monkeypatch.syspath_prepend(str(ROUTE / "scripts"))
    from story_ledger_check import read_worldguard_status, validate_ledger
    from scene_contract_check import worldguard_claim_passable

    fixtures = ROOT / "tests/fixtures/trials/trialB"
    ledger = tmp_path / "ledger.json"
    for filename, expected in (("wg-v2.json", "pass"), ("wg-late.json", "fail")):
        shutil.copyfile(fixtures / filename, tmp_path / filename)
        claim = {"worldguard_report": filename}
        assert read_worldguard_status(claim, str(ledger)) == expected
        assert worldguard_claim_passable(claim, str(ledger)) is (expected == "pass")
    with pytest.raises(ValueError, match="worldguard_status_without_report"):
        read_worldguard_status({"worldguard_status": "pass"}, str(ledger))
    with pytest.raises(ValueError, match="worldguard_status_mismatch"):
        read_worldguard_status({"worldguard_status": "pass", "worldguard_report": "wg-late.json"}, str(ledger))
    assert read_worldguard_status({}, str(ledger)) == "not_run"
    assert not worldguard_claim_passable({"adapter_status": "pass", "closure_effect": "continue"})
    report = validate_ledger({"worldguard_claims": [{"worldguard_status": "pass"}]}, str(ledger))
    assert "worldguard_status_without_report" in {row["code"] for row in report["issues"]}


def test_ledger_unit_must_be_a_planned_unit(tmp_path, monkeypatch):
    import shutil
    monkeypatch.syspath_prepend(str(ROUTE / "scripts"))
    from novel_ledger_check import validate_ledger
    from chapter_interface_check import validate as check_interfaces
    project = tmp_path / "project"
    shutil.copytree(ROUTE / "examples/longform_novel_project", project)
    path = project / "novel-ledger.json"
    payload = json.loads(path.read_text())
    payload["story_units"][0]["planned_unit_id"] = "unknown-book"
    report = validate_ledger(payload, str(path))
    assert "unit_not_in_plan:novel_ledger:unknown-book" in {row["code"] for row in report["issues"]}
    brief = project / "brief-request.json"
    request = json.loads(brief.read_text())
    for row in request["composition_plan"]["planned_units"]:
        if row["planned_unit_id"] == "chapter-01": row["planned_unit_id"] = "new-chapter"
    brief.write_text(json.dumps(request))
    ledger = validate_ledger(json.loads(path.read_text()), str(path))
    interfaces = check_interfaces(json.loads((project/"chapter-interfaces.json").read_text()), str(project/"chapter-interfaces.json"))
    assert "unit_not_in_plan:novel_ledger:chapter-01" in {row["code"] for row in ledger["issues"]}
    assert "unit_not_in_plan:chapter_interfaces:chapter-01" in {row["code"] for row in interfaces["issues"]}


def test_unit_fields_live_only_in_the_plan(monkeypatch):
    monkeypatch.syspath_prepend(str(ROUTE / "scripts"))
    from novel_ledger_check import validate_ledger
    project = ROUTE / "examples/longform_novel_project"
    ledger = json.loads((project/"novel-ledger.json").read_text())
    assert "hierarchy" not in ledger
    for row in ledger["story_units"]:
        assert "planned_unit_id" in row
        assert not {"id", "kind", "parent_id", "contribution", "downstream_use"} & row.keys()
    surfaces = json.loads((project/"chapter-interfaces.json").read_text())
    for row in surfaces["chapter_interfaces"]:
        assert "planned_unit_id" in row
        assert not {"chapter_id", "previous_chapter_id", "next_chapter_id", "reader_state_before", "reader_state_after"} & row.keys()
    path = project / "novel-ledger.json"
    assert not {row["code"] for row in validate_ledger(copy.deepcopy(ledger), str(path))["issues"]} & {"retired_unit_field"}
    ledger["story_units"][0]["contribution"] = "Restated from the plan."
    assert "retired_unit_field" in {row["code"] for row in validate_ledger(ledger, str(path))["issues"]}


def test_emptied_ledger_fails_longform_closure(tmp_path, monkeypatch):
    import shutil
    monkeypatch.syspath_prepend(str(ROUTE / "scripts"))
    from longform_closure_check import validate
    project = tmp_path/"project"
    shutil.copytree(ROUTE/"examples/longform_novel_project", project)
    source = project/"project-mesh.json"
    payload = json.loads(source.read_text())
    assert validate(payload, str(source))["passed"]
    (project/"novel-ledger.json").write_text("{}")
    report = validate(payload, str(source))
    assert report["decision"] == "needs_repair"
    assert report["surface_checks"]["novel_ledger"]["passed"] is False
