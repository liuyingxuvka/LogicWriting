from __future__ import annotations

import copy

import pytest

from schema_validation import SUPPORTED_SCHEMA_NAMES, SchemaValidationError, assert_schema_valid
from tests.v2_support import closure_input, complete_chain
from derive_closure import derive_closure


@pytest.fixture
def v2_examples(tmp_path):
    chain = complete_chain(tmp_path)
    closure = derive_closure(closure_input(chain))["closure"]
    return {
        "reader-intent.schema.json": chain["intent"],
        "composition-plan.schema.json": chain["plan"],
        "investigation-composition.schema.json": chain["route_composition"],
        "route-decision.schema.json": chain["route_decision"],
        "reader-brief.schema.json": chain["reader_brief"],
        "artifact-map.schema.json": chain["artifact_map"],
        "shared-writing-contract.schema.json": chain["shared_writing"],
        "reader-audit.schema.json": chain["deterministic_audit"],
        "route-artifact-review.schema.json": chain["route_review"],
        "reader-judgment.schema.json": chain["judgment"],
        "revision-provenance.schema.json": chain["revision_provenance"],
        "closure.schema.json": closure,
    }


def test_all_v2_reader_examples_validate(v2_examples):
    for name, value in v2_examples.items():
        assert_schema_valid(name, value)


@pytest.mark.parametrize(
    "name",
    [
        "reader-intent.schema.json", "composition-plan.schema.json",
        "investigation-composition.schema.json", "route-decision.schema.json",
        "reader-brief.schema.json", "artifact-map.schema.json",
        "shared-writing-contract.schema.json", "reader-audit.schema.json",
        "route-artifact-review.schema.json", "reader-judgment.schema.json",
        "revision-provenance.schema.json", "closure.schema.json",
    ],
)
def test_current_reader_contracts_reject_unknown_fields(v2_examples, name):
    value = copy.deepcopy(v2_examples[name])
    value["legacy_reader_alias"] = True
    with pytest.raises(SchemaValidationError, match="additionalProperties"):
        assert_schema_valid(name, value)


def test_schema_inventory_has_no_unregistered_files():
    assert len(SUPPORTED_SCHEMA_NAMES) == 30
