"""FlowGuard TestMesh derived from the OpenSpec verification contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import yaml
from flowguard import (
    EVIDENCE_CONFORMANCE_GREEN,
    TestMeshPlan,
    TestPartitionItem,
    TestSuiteEvidence,
    TestTargetSplitDerivation,
    contract_exhaustion_to_test_mesh_cell_ids,
)

FLOWGUARD_ROOT = Path(__file__).resolve().parents[1]
if str(FLOWGUARD_ROOT) not in sys.path:
    sys.path.insert(0, str(FLOWGUARD_ROOT))

from models.frozen_source_contract_exhaustion import (  # noqa: E402
    CASE_IDS as FROZEN_SOURCE_CASE_IDS,
    EXECUTION_CASE_IDS as FROZEN_EXECUTION_CASE_IDS,
    review_frozen_execution_boundary,
    review_frozen_source_name_family,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "openspec" / "changes" / "create-logic-writing" / "verification-contract.yaml"
RECEIPT_ROOT = "run-artifacts/validation-receipts"


def _contract() -> dict[str, Any]:
    value = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("checks"), list):
        raise ValueError("verification contract must contain a checks list")
    return value


def _checks(value: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    checks = tuple(dict(item) for item in value["checks"])
    ids = tuple(str(item.get("id", "")) for item in checks)
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("verification check ids must be nonempty and unique")
    return checks


def inventory_revision(value: Mapping[str, Any] | None = None) -> str:
    contract = dict(value or _contract())
    source_name_case_ids = tuple(
        case_id
        for case_id in contract_exhaustion_to_test_mesh_cell_ids(
            review_frozen_source_name_family()
        )
        if case_id in FROZEN_SOURCE_CASE_IDS
    )
    execution_boundary_case_ids = tuple(
        case_id
        for case_id in contract_exhaustion_to_test_mesh_cell_ids(
            review_frozen_execution_boundary()
        )
        if case_id in FROZEN_EXECUTION_CASE_IDS
    )
    payload = {
        "checks": contract["checks"],
        "version": contract.get("version"),
        "change_id": contract.get("change_id"),
        "frozen_source_case_ids": source_name_case_ids,
        "frozen_execution_case_ids": execution_boundary_case_ids,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _command(check: Mapping[str, Any]) -> str:
    if check.get("kind") != "command":
        return ""
    return " ".join([str(check.get("command", "")), *(str(item) for item in check.get("args", []))]).strip()


def _consumer_owner_map(checks: tuple[dict[str, Any], ...]) -> dict[str, tuple[str, ...]]:
    consumers: dict[str, list[str]] = {}
    command_ids = {str(item["id"]) for item in checks if item.get("kind") == "command"}
    for check in checks:
        if check.get("kind") != "receipt":
            continue
        owner = str(check.get("execution_owner", ""))
        if owner not in command_ids:
            raise ValueError(f"receipt consumer {check['id']} has no command owner")
        consumers.setdefault(owner, []).append(str(check["id"]))
    return {key: tuple(value) for key, value in consumers.items()}


def _receipt_suite(
    check: Mapping[str, Any],
    revision: str,
    owned_items: tuple[str, ...],
    receipt: Mapping[str, Any] | None,
) -> TestSuiteEvidence:
    receipt = dict(receipt or {})
    passed = receipt.get("status") == "passed" and receipt.get("exit_code") == 0
    return TestSuiteEvidence(
        str(check["id"]),
        command=_command(check),
        layer="release",
        result_status="passed" if passed else "not_run",
        evidence_tier=EVIDENCE_CONFORMANCE_GREEN,
        evidence_current=bool(passed and receipt.get("inventory_revision") == revision),
        test_count=1 if passed else 0,
        selected_count=1 if passed else 0,
        planned_count=1,
        executed_count=1 if passed else 0,
        failed_count=0,
        not_run_count=0 if passed else 1,
        diagnostic_campaign_id="logic-writing-final-validation",
        diagnostic_boundary="declared_complete" if passed else "targeted",
        release_required=True,
        skipped_visible=True,
        exit_code=receipt.get("exit_code"),
        result_path=str(receipt.get("result_path", "")),
        has_exit_artifact=passed,
        has_result_artifact=passed,
        not_run_reason="" if passed else "final frozen validation has not executed this owner",
        inventory_revision=revision,
        owned_inventory_item_ids=owned_items,
        run_id=str(receipt.get("run_id", "")),
        terminal_status="passed" if passed else "not_run",
        result_fingerprint=str(receipt.get("result_fingerprint", "")),
        covered_obligation_ids=owned_items if passed else (),
        artifact_version=str(receipt.get("artifact_version", "")),
        verifier_version=str(receipt.get("verifier_version", "")),
    )


def release_plan(receipts: Mapping[str, Mapping[str, Any]] | None = None) -> TestMeshPlan:
    contract = _contract()
    checks = _checks(contract)
    revision = inventory_revision(contract)
    command_checks = tuple(item for item in checks if item.get("kind") == "command")
    consumers = _consumer_owner_map(checks)
    receipt_map = dict(receipts or {})
    frozen_source_case_ids = tuple(
        case_id
        for case_id in contract_exhaustion_to_test_mesh_cell_ids(
            review_frozen_source_name_family()
        )
        if case_id in FROZEN_SOURCE_CASE_IDS
    )
    frozen_execution_case_ids = tuple(
        case_id
        for case_id in contract_exhaustion_to_test_mesh_cell_ids(
            review_frozen_execution_boundary()
        )
        if case_id in FROZEN_EXECUTION_CASE_IDS
    )
    frozen_boundary_case_ids = (
        *frozen_source_case_ids,
        *frozen_execution_case_ids,
    )

    check_items = tuple(
        TestPartitionItem(
            str(check["id"]),
            item_type="validation_obligation",
            owner_suite_id=(
                str(check["execution_owner"])
                if check.get("kind") == "receipt"
                else str(check["id"])
            ),
            description=str(check.get("semantic_check_id", check["id"])),
            touched_paths=tuple(str(item) for item in check.get("input_selectors", [])),
            inventory_revision=revision,
        )
        for check in checks
    )
    source_case_items = tuple(
        TestPartitionItem(
            case_id,
            item_type="validation_obligation",
            owner_suite_id="check.tests.full",
            description="OpenSpec frozen-source generated-output name collision",
            touched_paths=(
                "skills/logic-writing/assets/schemas/**",
                "tests/contract/test_schema_runtime_gate.py",
            ),
            inventory_revision=revision,
        )
        for case_id in frozen_source_case_ids
    )
    execution_case_items = tuple(
        TestPartitionItem(
            case_id,
            item_type="validation_obligation",
            owner_suite_id="check.tests.full",
            description=(
                "OpenSpec frozen owner runtime preparation, admitted-source, "
                "input-manifest, and repository-metadata boundary"
            ),
            touched_paths=(
                "scripts/check_reader_judgment.py",
                "scripts/prepare_reader_quality_receipt.py",
                "scripts/check_privacy.py",
                "scripts/check_public_docs.py",
                "scripts/check_release_surface.py",
                "scripts/check_skillguard_authority.py",
                "scripts/run_frozen_validation.py",
                "openspec/changes/create-logic-writing/verification-contract.yaml",
                "tests/contract/test_release_wrappers.py",
            ),
            inventory_revision=revision,
        )
        for case_id in frozen_execution_case_ids
    )
    items = check_items + source_case_items + execution_case_items
    suites = tuple(
        _receipt_suite(
            check,
            revision,
            (
                str(check["id"]),
                *consumers.get(str(check["id"]), ()),
                *(frozen_boundary_case_ids if str(check["id"]) == "check.tests.full" else ()),
            ),
            receipt_map.get(str(check["id"])),
        )
        for check in command_checks
    )
    return TestMeshPlan(
        parent_suite_id="logic-writing-frozen-release-validation",
        partition_items=items,
        child_suites=suites,
        target_split_derivation=TestTargetSplitDerivation(
            "model:release-retirement",
            target_suite_ids=tuple(str(item["id"]) for item in command_checks),
            covered_partition_item_ids=tuple(item.item_id for item in items),
            state_owner_fields=("validation_fingerprint", "validation_status", "validation_current"),
            side_effect_owner_fields=("validation_receipts",),
            source_model_path=".flowguard/models/release_retirement_model.py",
            rationale=(
                "The release-retirement model requires one frozen validation identity; "
                "each OpenSpec command is one execution owner and receipt rows are consumers."
            ),
        ),
        required_evidence_tier=EVIDENCE_CONFORMANCE_GREEN,
        decision_scope="release",
        release_deferred_allowed=False,
        inventory_revision=revision,
        required_inventory_item_ids=tuple(item.item_id for item in items),
        require_complete_inventory=True,
        require_final_receipts=True,
    )


def broken_missing_target_split_plan() -> TestMeshPlan:
    plan = release_plan()
    return TestMeshPlan(
        parent_suite_id="known-bad-missing-target-split",
        partition_items=plan.partition_items,
        child_suites=plan.child_suites,
        target_split_derivation=None,
        decision_scope="release",
        release_deferred_allowed=False,
        inventory_revision=plan.inventory_revision,
        required_inventory_item_ids=plan.required_inventory_item_ids,
        require_complete_inventory=True,
        require_final_receipts=True,
    )
