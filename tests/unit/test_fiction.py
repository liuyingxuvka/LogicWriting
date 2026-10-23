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


def test_native_fiction_binding_rejects_unbound_prose(monkeypatch):
    monkeypatch.syspath_prepend(str(ROUTE / "scripts"))
    from model_prose_binding_check import validate

    source_path = ROUTE / "examples" / "longform_novel_project" / "model-prose-binding.json"
    binding = json.loads(source_path.read_text(encoding="utf-8"))
    report = validate(binding, str(source_path), repository_root=ROOT)
    assert report["passed"] is True
    assert report["issues"] == []

    unbound = copy.deepcopy(binding)
    unbound["unbound_prose_refs"] = ["final-prose.md#unbound-span"]
    report = validate(unbound, str(source_path), repository_root=ROOT)
    assert report["passed"] is False
    assert {row["code"] for row in report["issues"]} == {
        "unresolved_binding_gap", "passed_with_binding_errors",
    }


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


@pytest.mark.parametrize("input_kind", ["missing", "invalid_json", "invalid_schema"])
def test_longform_binding_negative_cannot_pass_from_input_failure(tmp_path, input_kind):
    path = ROUTE / "scripts" / "run_longform_regression.py"
    spec = importlib.util.spec_from_file_location("longform_fixture_oracle", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    case = next(row for row in module.command_matrix(ROOT) if row["id"] == "negative.unbound_prose_span")
    external = tmp_path / "input.json"
    if input_kind == "invalid_json":
        external.write_text("{invalid JSON", encoding="utf-8")
    elif input_kind == "invalid_schema":
        external.write_text("{}", encoding="utf-8")
    case["argv"][2] = str(external)
    result = module.run_case(case, ROOT)
    assert result["actual_exit_code"] == 1
    assert result["passed"] is False
    assert {"read_error", "json_decode_error", "invalid_schema_version"} & set(result["observed_issue_codes"])


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
