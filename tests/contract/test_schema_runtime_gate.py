from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from schema_validation import (
    DRAFT_2020_12,
    SUPPORTED_SCHEMA_NAMES,
    SchemaValidationError,
    UnknownSchemaError,
    assert_schema_valid,
    validate_schema,
)
from select_route import select_route
from _common import fingerprint
from tests.v2_support import make_intent


EXPECTED = {
    "academic-composition.schema.json",
    "artifact-map.schema.json",
    "closure.schema.json",
    "composition-plan.schema.json",
    "fiction-composition.schema.json",
    "investigation-composition.schema.json",
    "reader-audit.schema.json",
    "reader-brief.schema.json",
    "reader-intent.schema.json",
    "reader-judgment.schema.json",
    "revision-provenance.schema.json",
    "route-decision.schema.json",
    "route-artifact-review.schema.json",
    "shared-writing-contract.schema.json",
    "source-unit-manifest.schema.json",
    "travel-composition.schema.json",
    "writing-request.schema.json",
}


def _decision() -> dict:
    intent = make_intent()
    deliverable = {
        "kind": "research_report",
        "description": "A bounded report",
        "acceptance_criteria": [],
    }
    deliverable["fingerprint"] = fingerprint(deliverable)
    request = {
        "schema_version": "2.0",
        "request_id": "request:schema-runtime",
        "terminal_deliverable": deliverable,
        "reader_intent": intent,
    }
    request["request_fingerprint"] = fingerprint(request)
    return select_route(
        {
            "writing_request": request,
            "decision_id": "decision:schema-runtime",
            "decided_at": "2026-07-14T12:00:00Z",
            "substantial_research_required": False,
            "material_assumptions": [],
        }
    )


def test_runtime_inventory_is_exactly_the_current_contracts():
    schema_root = (
        Path(__file__).resolve().parents[2]
        / "skills"
        / "logic-writing"
        / "assets"
        / "schemas"
    )

    assert set(SUPPORTED_SCHEMA_NAMES) == EXPECTED
    assert {path.name for path in schema_root.glob("*.schema.json")} == EXPECTED


def test_all_schema_ids_are_canonical_and_offline():
    schema_root = (
        Path(__file__).resolve().parents[2]
        / "skills"
        / "logic-writing"
        / "assets"
        / "schemas"
    )
    for name in SUPPORTED_SCHEMA_NAMES:
        value = json.loads((schema_root / name).read_text(encoding="utf-8"))
        assert value["$schema"] == DRAFT_2020_12
        assert value["$id"] == f"https://github.com/liuyingxuvka/LogicWriting/schemas/{name}"
        for ref in _walk_refs(value):
            assert not ref.startswith(("http://", "https://"))


def _walk_refs(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref":
                yield item
            else:
                yield from _walk_refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_refs(item)


def test_runtime_accepts_current_artifact_without_mutation():
    artifact = _decision()
    before = copy.deepcopy(artifact)

    assert validate_schema("route-decision.schema.json", artifact) == ()
    assert artifact == before


def test_runtime_reports_stable_paths_and_keywords():
    artifact = _decision()
    artifact["decided_at"] = "not-a-date"
    artifact["unexpected"] = True

    first = validate_schema("route-decision.schema.json", artifact)
    second = validate_schema("route-decision.schema.json", artifact)

    assert first == second
    assert {issue.keyword for issue in first} >= {"format", "additionalProperties"}
    assert {issue.path for issue in first} >= {"$.decided_at", "$.unexpected"}


def test_assertion_raises_one_contract_error_vocabulary():
    with pytest.raises(SchemaValidationError) as exc:
        assert_schema_valid("route-decision.schema.json", {})

    assert exc.value.schema_name == "route-decision.schema.json"
    assert exc.value.issues


def test_unknown_schema_has_no_fallback():
    with pytest.raises(UnknownSchemaError, match="unknown Logic Writing schema"):
        validate_schema("former.schema.json", {})


def test_runtime_does_not_depend_on_site_packages():
    scripts = (
        Path(__file__).resolve().parents[2]
        / "skills"
        / "logic-writing"
        / "scripts"
    )
    command = (
        "import sys; "
        f"sys.path.insert(0, {str(scripts)!r}); "
        "import schema_validation as s; "
        "print(len(s.SUPPORTED_SCHEMA_NAMES))"
    )
    completed = subprocess.run(
        [sys.executable, "-S", "-c", command],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == str(len(EXPECTED))


def test_each_distinct_schema_object_is_validated_once(tmp_path, monkeypatch):
    import shutil
    import schema_validation
    from run_chain import run_chain

    monkeypatch.setattr(schema_validation, "_VALIDATION_MEMO", {}, raising=False)
    original_runtime = schema_validation._RUNTIME.validate
    original_gate = schema_validation.validate_schema
    seen = set()
    calls = 0
    depth = 0

    def count_runtime(*args, **kwargs):
        nonlocal calls, depth
        if depth == 0:
            calls += 1
        depth += 1
        try:
            return original_runtime(*args, **kwargs)
        finally:
            depth -= 1

    def count_gate(schema_name, artifact):
        seen.add(
            (
                schema_name,
                json.dumps(artifact, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            )
        )
        return original_gate(schema_name, artifact)

    monkeypatch.setattr(schema_validation._RUNTIME, "validate", count_runtime)
    monkeypatch.setattr(schema_validation, "validate_schema", count_gate)
    source = (
        Path(__file__).resolve().parents[2] / "skills/logic-writing/assets/examples/investigation"
    )
    folder = tmp_path / "investigation"
    shutil.copytree(source, folder)
    result = run_chain(folder)
    assert result["exit_code"] == 0
    assert calls == len(seen) > 0
    print(f"schema validation: {calls} real validations, {len(seen)} distinct schema/object pairs")


def test_schema_memo_cannot_reuse_a_json_array_result_for_a_tuple(monkeypatch):
    import schema_validation

    monkeypatch.setattr(schema_validation, "_VALIDATION_MEMO", {}, raising=False)
    artifact = make_intent()
    assert validate_schema("reader-intent.schema.json", artifact) == ()
    changed = copy.deepcopy(artifact)
    changed["required_content"] = tuple(changed["required_content"])
    issues = validate_schema("reader-intent.schema.json", changed)
    assert any(issue.path == "$.required_content" and issue.keyword == "type" for issue in issues)
