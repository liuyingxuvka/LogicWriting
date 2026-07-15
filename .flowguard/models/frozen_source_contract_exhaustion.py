"""Finite coverage for OpenSpec frozen-source and execution boundaries."""

from __future__ import annotations

from dataclasses import replace

from flowguard import (
    CONTRACT_MUTATION_ANALOGOUS_DEFECT,
    ContractCoverageUniverse,
    ContractDimension,
    ContractExhaustionPlan,
    ContractMutationCase,
    ContractOracle,
    ObservedProblemBackfeed,
    review_contract_exhaustion,
)


DIMENSION_ID = "dimension:openspec-generated-json-basename"
FAMILY_ID = "family:openspec-generated-json-basename"
MODEL_ID = "model:release-retirement"
ORACLE_ID = "oracle:rename-authority-source"
REQUIRED_ROUTES = ("model_test_alignment", "test_mesh")
COLLIDING_SCHEMA_BASENAMES = (
    "receipt.schema.json",
    "receipts.schema.json",
    "cache.schema.json",
    "progress.schema.json",
    "registry.schema.json",
    "verification-receipt.schema.json",
)
CASE_IDS = tuple(
    "case:source-name:" + name.replace(".", "-")
    for name in COLLIDING_SCHEMA_BASENAMES
)

EXECUTION_DIMENSION_ID = "dimension:frozen-execution-boundary"
EXECUTION_FAMILY_ID = "family:frozen-execution-boundary"
EXECUTION_ORACLE_ID = "oracle:self-contained-frozen-owner"
EXECUTION_BOUNDARY_MEMBERS = (
    "runtime-prerequisite-declared-as-source",
    "ignored-coordination-record-admitted",
    "ignored-adoption-record-admitted",
    "ignored-verification-output-admitted",
    "check-input-selector-unbound",
    "vcs-metadata-required-inside-frozen-root",
    "project-identity-bound-to-random-frozen-directory",
)
EXECUTION_CASE_IDS = tuple(
    f"case:frozen-boundary:{member}" for member in EXECUTION_BOUNDARY_MEMBERS
)


def _base_plan() -> ContractExhaustionPlan:
    dimension = ContractDimension(
        DIMENSION_ID,
        "source_filename",
        source_route="openspec",
        owner_model_id=MODEL_ID,
        required=False,
        finite=True,
        values=COLLIDING_SCHEMA_BASENAMES,
        mutation_types=(CONTRACT_MUTATION_ANALOGOUS_DEFECT,),
        producer="repository source authority",
        consumer="OpenSpec frozen-root materializer",
        currentness_rule=(
            "renaming or adding a tracked authority source reruns the frozen-source case"
        ),
        description="tracked source names must not collide with generated-output basenames",
        metadata={"family_id": FAMILY_ID},
    )
    cases = tuple(
        ContractMutationCase(
            case_id=case_id,
            dimension_id=DIMENSION_ID,
            mutation_type=CONTRACT_MUTATION_ANALOGOUS_DEFECT,
            source_route="openspec",
            required=True,
            oracle_id=ORACLE_ID,
            input_delta={"tracked_authority_basename": name},
            expected_status="blocked",
            family_id=FAMILY_ID,
            member_id=name,
            evidence_refs=("tests/contract/test_schema_runtime_gate.py",),
            required_routes=REQUIRED_ROUTES,
            required_test_cell_id="test:frozen-source-materialization",
            risk_gate_id="risk:frozen-source-materialization",
            freshness_scope="development_process",
            description=(
                f"tracked authority source {name} collides with the OpenSpec "
                "generated-output classifier"
            ),
            dimension_ids=(DIMENSION_ID,),
            model_id=MODEL_ID,
        )
        for case_id, name in zip(CASE_IDS, COLLIDING_SCHEMA_BASENAMES, strict=True)
    )
    oracle = ContractOracle(
        ORACLE_ID,
        "blocked",
        expected_message_fields=("conflicting_source_path", "classification_rule"),
        forbidden_downstream_steps=("final_full_validation",),
        required_repair_fields=("replacement_source_name",),
        description=(
            "block release validation until the tracked source uses a non-generated "
            "basename and the frozen replay passes"
        ),
    )
    universe = ContractCoverageUniverse(
        "universe:openspec-generated-json-basename",
        "release",
        source_refs=(
            "OpenSpec 1.6.0 verification-generated-output-v2",
            "git tracked schema inventory",
        ),
        required_dimension_ids=(DIMENSION_ID,),
        required_case_ids=CASE_IDS,
        require_full_product=False,
    )
    return ContractExhaustionPlan(
        "plan:frozen-source-name-family",
        dimensions=(dimension,),
        seed_cases=cases,
        oracles=(oracle,),
        claim_scope="release",
        source_model_ids=(MODEL_ID,),
        source_bug_refs=("openspec-run:b54e821c-5bea-4d04-9250-bd162797d2f8",),
        required_route_ids=REQUIRED_ROUTES,
        model_id=MODEL_ID,
        model_level="leaf",
        require_model_coverage_receipt=True,
        coverage_universe=universe,
        require_coverage_universe=True,
        require_actionable_oracle_feedback=True,
        inventory_revision="openspec-generated-output-v2",
        inventory_current=True,
    )


def review_frozen_source_name_family():
    base = _base_plan()
    preliminary = review_contract_exhaustion(base)
    if not preliminary.coverage_receipts:
        return preliminary
    observed = ObservedProblemBackfeed(
        "problem:frozen-source-schema-omitted",
        observed_failure=(
            "receipt.schema.json was absent from the frozen execution root while "
            "present in the tracked worktree"
        ),
        failure_mode="boundary_missing",
        affected_dimension_ids=(DIMENSION_ID,),
        matched_case_ids=(CASE_IDS[0],),
        matched_coverage_receipt_ids=(preliminary.coverage_receipts[0].receipt_id,),
        same_class_case_ids=CASE_IDS[1:],
        source_refs=(
            "openspec/changes/create-logic-writing/verification-report.json",
            "tests/contract/test_schema_runtime_gate.py",
        ),
    )
    return review_contract_exhaustion(
        replace(base, observed_problem_backfeed=(observed,))
    )


def _execution_boundary_plan() -> ContractExhaustionPlan:
    dimension = ContractDimension(
        EXECUTION_DIMENSION_ID,
        "frozen_execution_input_class",
        source_route="openspec",
        owner_model_id=MODEL_ID,
        required=False,
        finite=True,
        values=EXECUTION_BOUNDARY_MEMBERS,
        mutation_types=(CONTRACT_MUTATION_ANALOGOUS_DEFECT,),
        producer="repository working tree and validation owner",
        consumer="OpenSpec frozen-root materializer",
        currentness_rule=(
            "changing runtime preparation, source exclusions, per-check selectors, "
            "frozen metadata requirements, or project-identity projection reruns "
            "every execution-boundary case"
        ),
        description=(
            "runtime prerequisites belong to their execution owner and ignored "
            "internal records do not become frozen public source; every check binds "
            "concrete admitted inputs, asks only for metadata present in the root, "
            "and projects stable logical identity without trusting a temporary path"
        ),
        metadata={"family_id": EXECUTION_FAMILY_ID},
    )
    cases = tuple(
        ContractMutationCase(
            case_id=case_id,
            dimension_id=EXECUTION_DIMENSION_ID,
            mutation_type=CONTRACT_MUTATION_ANALOGOUS_DEFECT,
            source_route="openspec",
            required=True,
            oracle_id=EXECUTION_ORACLE_ID,
            input_delta={"boundary_member": member},
            expected_status="blocked",
            family_id=EXECUTION_FAMILY_ID,
            member_id=member,
            evidence_refs=("tests/contract/test_release_wrappers.py",),
            required_routes=REQUIRED_ROUTES,
            required_test_cell_id="test:frozen-execution-boundary",
            risk_gate_id="risk:frozen-execution-boundary",
            freshness_scope="development_process",
            description=(
                f"frozen validation must reject the unowned or inadmissible "
                f"boundary member {member}"
            ),
            dimension_ids=(EXECUTION_DIMENSION_ID,),
            model_id=MODEL_ID,
        )
        for case_id, member in zip(
            EXECUTION_CASE_IDS, EXECUTION_BOUNDARY_MEMBERS, strict=True
        )
    )
    oracle = ContractOracle(
        EXECUTION_ORACLE_ID,
        "blocked",
        expected_message_fields=("boundary_member", "source_or_runtime_disposition"),
        forbidden_downstream_steps=("final_full_validation",),
        required_repair_fields=("source_or_runtime_disposition",),
        description=(
            "block release until runtime prerequisites are generated inside their "
            "owner, ignored internal records are excluded, check inputs are bound, "
            "repository metadata remains outside metadata-free frozen checks, and "
            "logical project identity survives random snapshot directories"
        ),
    )
    universe = ContractCoverageUniverse(
        "universe:frozen-execution-boundary",
        "release",
        source_refs=(
            "OpenSpec run 0487aec7-5efd-4388-8f78-72f1276bdbca",
            "Logic Writing ignored runtime and internal-record inventory",
        ),
        required_dimension_ids=(EXECUTION_DIMENSION_ID,),
        required_case_ids=EXECUTION_CASE_IDS,
        require_full_product=False,
    )
    return ContractExhaustionPlan(
        "plan:frozen-execution-boundary",
        dimensions=(dimension,),
        seed_cases=cases,
        oracles=(oracle,),
        claim_scope="release",
        source_model_ids=(MODEL_ID,),
        source_bug_refs=(
            "openspec-run:0487aec7-5efd-4388-8f78-72f1276bdbca",
            "openspec-run:ec1fe313-48de-45f7-937e-06652e2f86d1",
        ),
        required_route_ids=REQUIRED_ROUTES,
        model_id=MODEL_ID,
        model_level="leaf",
        require_model_coverage_receipt=True,
        coverage_universe=universe,
        require_coverage_universe=True,
        require_actionable_oracle_feedback=True,
        inventory_revision="logic-writing-frozen-execution-boundary-v2",
        inventory_current=True,
    )


def review_frozen_execution_boundary():
    base = _execution_boundary_plan()
    preliminary = review_contract_exhaustion(base)
    if not preliminary.coverage_receipts:
        return preliminary
    observed = ObservedProblemBackfeed(
        "problem:frozen-execution-input-boundary",
        observed_failure=(
            "the reader judgment expected an ignored runtime prerequisite while "
            "ignored coordination and adoption records entered the frozen public root; "
            "the same audit exposed empty dot-selector manifests and a later source "
            "check that required unavailable Git metadata, while a subsequent full "
            "run bound SkillGuard project identity to a random snapshot directory"
        ),
        failure_mode="boundary_missing",
        affected_dimension_ids=(EXECUTION_DIMENSION_ID,),
        matched_case_ids=(EXECUTION_CASE_IDS[0],),
        matched_coverage_receipt_ids=(
            preliminary.coverage_receipts[0].receipt_id,
        ),
        same_class_case_ids=EXECUTION_CASE_IDS[1:],
        source_refs=(
            "openspec/changes/create-logic-writing/verification-report.json",
            "tests/contract/test_release_wrappers.py",
        ),
    )
    return review_contract_exhaustion(
        replace(base, observed_problem_backfeed=(observed,))
    )
