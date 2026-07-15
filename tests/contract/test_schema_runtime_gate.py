from __future__ import annotations

import copy
import json
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


EXPECTED = {
    "adapter-request.schema.json",
    "adapter-result.schema.json",
    "claim-support.schema.json",
    "closure.schema.json",
    "obligation-manifest.schema.json",
    "reader-audit.schema.json",
    "reader-brief.schema.json",
    "reader-judgment.schema.json",
    "receipt.schema.json",
    "research-packet.schema.json",
    "revision-provenance.schema.json",
    "route-decision.schema.json",
    "source-registry.schema.json",
    "source-unit-manifest.schema.json",
}


def _decision() -> dict:
    return select_route(
        {
            "request_id": "request:schema-runtime",
            "decision_id": "decision:schema-runtime",
            "decided_at": "2026-07-14T12:00:00Z",
            "terminal_deliverable": {
                "kind": "research_report",
                "description": "A bounded report",
                "acceptance_criteria": [],
            },
            "scope_class": "substantive",
            "substantial_research_required": False,
            "constraints": {},
            "material_assumptions": [],
        }
    )


def test_runtime_inventory_is_exactly_the_fourteen_current_contracts():
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
    assert completed.stdout.strip() == "14"


def test_schema_runtime_source_has_no_secondary_validator_import():
    source = (
        Path(__file__).resolve().parents[2]
        / "skills"
        / "logic-writing"
        / "scripts"
        / "schema_validation.py"
    ).read_text(encoding="utf-8")

    assert "import jsonschema" not in source
    assert "from jsonschema" not in source
