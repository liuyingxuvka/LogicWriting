"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Review a development lifecycle as a sibling process route, tracking artifact versions and validation evidence freshness before done or release claims.
Guards against: stale validation after code/test/model/requirement/UI observed inventory/UI functional capability coverage/UI functional chain/UI source-baseline interaction/UI done-claim/payload-schema/field-lifecycle/contract-exhaustion interaction group, shard, or receipt changes, oversized direct model evidence, slow or broad direct validation evidence, progress-only evidence, hidden skips, missing V-style validation pairs, peer writes, and release overclaims.
Use before editing: Update this development process flow when changing development ordering, UI click-through, observed-inventory, functional capability coverage, functional-chain, source-baseline interaction, done-claim, payload-pack validation gates, ContractExhaustionMesh generated cases/shards/receipts, release readiness, or evidence freshness policy.
Run: python .flowguard/development_process_flow/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    PROCESS_ARTIFACT_CODE,
    PROCESS_ARTIFACT_BUG_REPAIR_CLOSURE,
    PROCESS_ARTIFACT_FIELD_LIFECYCLE,
    PROCESS_ARTIFACT_FIELD_PROJECTION,
    PROCESS_ARTIFACT_UI_SOURCE_BASELINE_GATE,
    PROCESS_ARTIFACT_MODEL,
    PROCESS_ARTIFACT_REPLACEMENT_DISPOSITION,
    PROCESS_ARTIFACT_REQUIREMENT,
    PROCESS_ARTIFACT_TEST,
    PROCESS_ARTIFACT_UI_DONE_CLAIM,
    PROCESS_ARTIFACT_UI_FUNCTIONAL_CAPABILITY_COVERAGE,
    PROCESS_ARTIFACT_UI_FUNCTIONAL_CHAIN,
    PROCESS_ARTIFACT_UI_OBSERVED_INVENTORY,
    PROCESS_EVIDENCE_BUG_REPAIR_CLOSURE,
    PROCESS_EVIDENCE_FIELD_LIFECYCLE,
    PROCESS_EVIDENCE_FIELD_PROJECTION,
    PROCESS_EVIDENCE_UI_SOURCE_BASELINE_GATE,
    PROCESS_EVIDENCE_MODEL_MISS_REVIEW,
    PROCESS_EVIDENCE_PASSED,
    PROCESS_EVIDENCE_UI_DONE_CLAIM_REVIEW,
    PROCESS_EVIDENCE_UI_FUNCTIONAL_CAPABILITY_COVERAGE,
    PROCESS_EVIDENCE_UI_FUNCTIONAL_CHAIN,
    PROCESS_EVIDENCE_UI_IMPLEMENTATION_VALIDATION,
    PROCESS_EVIDENCE_UI_OBSERVED_INVENTORY,
    PROCESS_SCOPE_RELEASE,
    DevelopmentProcessPlan,
    FreshnessRule,
    ProofArtifactRef,
    ProcessAction,
    ProcessArtifact,
    ProcessEvidence,
    ValidationRequirement,
    review_development_process_flow,
)


def proof_artifact(artifact_id: str, *covered: str) -> ProofArtifactRef:
    result_path = f"tmp/{artifact_id.replace(':', '_')}.json"
    return ProofArtifactRef(
        artifact_id,
        result_status=PROCESS_EVIDENCE_PASSED,
        exit_code=0,
        result_path=result_path,
        artifact_fingerprints={result_path: "sha256:template"},
        covered_obligation_ids=covered,
    )


def artifacts(code_version: str = "2", test_version: str = "1", requirement_version: str = "1"):
    return (
        ProcessArtifact("requirements.checkout", PROCESS_ARTIFACT_REQUIREMENT, requirement_version),
        ProcessArtifact(
            "model.checkout",
            PROCESS_ARTIFACT_MODEL,
            "1",
            upstream_artifact_ids=("requirements.checkout",),
        ),
        ProcessArtifact(
            "code.checkout",
            PROCESS_ARTIFACT_CODE,
            code_version,
            upstream_artifact_ids=("requirements.checkout", "model.checkout"),
        ),
        ProcessArtifact("tests.checkout", PROCESS_ARTIFACT_TEST, test_version),
    )


def routine_plan() -> DevelopmentProcessPlan:
    return DevelopmentProcessPlan(
        "checkout-development-lifecycle",
        require_proof_artifacts=True,
        artifacts=artifacts(code_version="2"),
        actions=(
            ProcessAction("edit-code", writes_artifacts=("code.checkout",)),
            ProcessAction("run-unit", produced_evidence_ids=("unit-pass",)),
            ProcessAction("claim-done", action_type="claim_done", required_validation_ids=("unit-current",)),
        ),
        evidence=(
            ProcessEvidence(
                "unit-pass",
                evidence_kind="unit",
                producer_route="test_mesh_maintenance",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("code.checkout",),
                verifier_artifacts=("tests.checkout",),
                covered_versions={"code.checkout": "2", "tests.checkout": "1"},
                validation_requirement_ids=("unit-current",),
                produced_by_action_id="run-unit",
                command="python -m unittest tests.test_checkout",
                proof_artifact=proof_artifact("artifact:unit-pass", "unit-current"),
            ),
        ),
        validation_requirements=(
            ValidationRequirement(
                "unit-current",
                required_artifact_ids=("code.checkout",),
                required_evidence_kinds=("unit",),
                v_model_pair=True,
                command="python -m unittest tests.test_checkout",
            ),
        ),
    )


def broken_plan() -> DevelopmentProcessPlan:
    return DevelopmentProcessPlan(
        "checkout-broken-lifecycle",
        artifacts=artifacts(code_version="2", requirement_version="2"),
        actions=(
            ProcessAction("run-unit", produced_evidence_ids=("unit-pass",)),
            ProcessAction("edit-code", writes_artifacts=("code.checkout",)),
            ProcessAction("edit-requirement", writes_artifacts=("requirements.checkout",)),
            ProcessAction(
                "claim-release",
                action_type="claim_release",
                required_evidence_ids=("unit-pass",),
                decision_scope=PROCESS_SCOPE_RELEASE,
            ),
        ),
        evidence=(
            ProcessEvidence(
                "unit-pass",
                evidence_kind="unit",
                producer_route="test_mesh_maintenance",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("code.checkout",),
                verifier_artifacts=("tests.checkout",),
                covered_versions={"code.checkout": "1", "tests.checkout": "1"},
                validation_requirement_ids=("unit-current",),
                produced_by_action_id="run-unit",
                command="python -m unittest tests.test_checkout",
            ),
        ),
        validation_requirements=(
            ValidationRequirement(
                "unit-current",
                required_artifact_ids=("code.checkout",),
                required_evidence_kinds=("unit",),
                evidence_ids=("unit-pass",),
                v_model_pair=True,
                command="python -m unittest tests.test_checkout",
            ),
        ),
        freshness_rules=(
            FreshnessRule(
                "requirements-affect-code-validation",
                upstream_artifact_id="requirements.checkout",
                invalidates_artifact_ids=("code.checkout", "model.checkout"),
            ),
        ),
        decision_scope=PROCESS_SCOPE_RELEASE,
    )


def run_checks():
    return review_development_process_flow(routine_plan()), review_development_process_flow(broken_plan())
