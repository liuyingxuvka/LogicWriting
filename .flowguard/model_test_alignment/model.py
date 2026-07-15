"""Current FlowGuard model-code-test bindings for Logic Writing.

This review maps each registered behavior commitment to one owner code
contract and one ordinary external-contract test.  It is structural alignment;
the frozen validation owner supplies terminal execution receipts later.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

from flowguard import CodeContract, ModelObligation, ModelTestAlignmentPlan, TestEvidence

FLOWGUARD_ROOT = Path(__file__).resolve().parents[1]
if str(FLOWGUARD_ROOT) not in sys.path:
    sys.path.insert(0, str(FLOWGUARD_ROOT))

from models.retirement_field_lifecycle import review_retirement_visibility_fields


@dataclass(frozen=True)
class BindingSpec:
    obligation_id: str
    description: str
    plane: str
    intent_id: str
    commitment_id: str
    path_id: str
    contract_id: str
    code_path: str
    symbol: str
    test_id: str
    test_name: str
    test_path: str
    required_kinds: tuple[str, ...] = ("happy_path",)


BINDINGS = (
    BindingSpec(
        "obligation:one-final-owner",
        "one terminal artifact has exactly one final owner",
        "agent_operation",
        "intent:select-one-final-owner",
        "C01:select-one-final-owner",
        "logic_writing.entry",
        "contract:select-route",
        "skills/logic-writing/scripts/select_route.py",
        "select_route",
        "test:routing",
        "test_ambiguous_deliverable_blocks_instead_of_assigning_two_owners",
        "tests/unit/test_routing.py",
        ("happy_path", "negative_path"),
    ),
    BindingSpec(
        "obligation:native-owner",
        "specialist owner and evidence domain remain native",
        "agent_operation",
        "intent:preserve-specialist-authority",
        "C02:preserve-specialist-authority",
        "logic_writing.adapter",
        "contract:adapter-envelope",
        "skills/logic-writing/scripts/validate_adapter_result.py",
        "validate_adapter_result",
        "test:adapters",
        "test_owner_cannot_claim_another_specialist_domain",
        "tests/contract/test_adapters.py",
        ("happy_path", "negative_path"),
    ),
    BindingSpec(
        "obligation:minimum-core-content",
        "a ResearchPacket needs source observation and argument-model content",
        "agent_operation",
        "intent:build-current-research-packet",
        "C03:build-current-research-packet",
        "logic_writing.investigation.packet",
        "contract:research-packet",
        "skills/logic-writing/scripts/validate_research_packet.py",
        "assemble_research_packet",
        "test:process-green-content-not-run",
        "test_process_green_content_not_run_cannot_issue_final_closure",
        "tests/adversarial/test_boundaries.py",
        ("happy_path", "negative_path"),
    ),
    BindingSpec(
        "obligation:two-room-boundary",
        "internal workflow data becomes a sanitized ReaderBrief",
        "agent_operation",
        "intent:build-reader-brief",
        "C04:build-reader-brief",
        "logic_writing.reader.brief",
        "contract:reader-brief",
        "skills/logic-writing/scripts/build_reader_brief.py",
        "build_reader_brief",
        "test:reader",
        "test_reader_brief_contains_reader_content_not_internal_workflow",
        "tests/unit/test_reader.py",
    ),
    BindingSpec(
        "obligation:actual-artifact-audit",
        "reader evidence inspects the exact current artifact",
        "agent_operation",
        "intent:audit-actual-artifact",
        "C05:audit-actual-artifact",
        "logic_writing.reader.audit",
        "contract:reader-audit",
        "skills/logic-writing/scripts/audit_reader_output.py",
        "audit_reader_output",
        "test:reader-quality",
        "test_reader_native_metadata_cannot_make_bad_prose_pass",
        "tests/adversarial/test_boundaries.py",
        ("happy_path", "negative_path"),
    ),
    BindingSpec(
        "obligation:minimum-final-content",
        "final closure requires route content, reader evidence, and academic provenance when applicable",
        "agent_operation",
        "intent:issue-final-artifact-closure",
        "C06:issue-final-artifact-closure",
        "logic_writing.operation.closure",
        "contract:derive-closure",
        "skills/logic-writing/scripts/derive_closure.py",
        "derive_closure",
        "test:freshness-closure",
        "test_repeated_identical_failure_becomes_terminal_no_progress",
        "tests/unit/test_freshness_closure.py",
        ("happy_path", "negative_path", "replay"),
    ),
    BindingSpec(
        "obligation:frozen-validation",
        "one frozen validation identity owns final execution",
        "development_process",
        "intent:freeze-one-validation-owner",
        "C07:freeze-one-validation-owner",
        "logic_writing.release.validation",
        "contract:verification-owner-plan",
        ".flowguard/models/common.py",
        "FreezeValidation",
        "test:full-validation",
        "test_release_requires_frozen_install_and_global_route",
        "tests/flowguard/test_model_contracts.py",
        ("happy_path", "negative_path"),
    ),
    BindingSpec(
        "obligation:recoverable-install",
        "installation is staged before activation and retains rollback",
        "development_process",
        "intent:activate-recoverable-install",
        "C08:activate-recoverable-install",
        "logic_writing.release.install",
        "contract:installation-projection",
        ".flowguard/models/common.py",
        "ActivateInstall",
        "test:installed-smoke",
        "test_release_requires_frozen_install_and_global_route",
        "tests/flowguard/test_model_contracts.py",
    ),
    BindingSpec(
        "obligation:one-global-route",
        "only the active installation can become the global route",
        "development_process",
        "intent:project-one-global-route",
        "C09:project-one-global-route",
        "logic_writing.release.global-route",
        "contract:global-router-projection",
        ".flowguard/models/common.py",
        "ProjectGlobalRoute",
        "test:global-routing",
        "test_release_requires_frozen_install_and_global_route",
        "tests/flowguard/test_model_contracts.py",
    ),
    BindingSpec(
        "obligation:publish-release",
        "publication requires current validation, install, and global route",
        "development_process",
        "intent:publish-logic-writing-release",
        "C10:publish-logic-writing-release",
        "logic_writing.release.publish",
        "contract:release-gate",
        ".flowguard/models/common.py",
        "PublishRelease",
        "test:fresh-clone",
        "test_release_requires_frozen_install_and_global_route",
        "tests/flowguard/test_model_contracts.py",
        ("happy_path", "negative_path"),
    ),
    BindingSpec(
        "obligation:sequential-retirement",
        "predecessors become private only after recovery gates and in research-then-academic order, followed by a user deletion handoff",
        "development_process",
        "intent:retire-predecessors-safely",
        "C11:retire-predecessors-safely",
        "logic_writing.release.retirement",
        "contract:retirement-gate",
        ".flowguard/models/common.py",
        "PrivatizeLegacyRemote",
        "test:legacy-residual",
        "test_remote_retirement_privatizes_sequentially_and_records_handoff",
        "tests/flowguard/test_model_contracts.py",
        ("happy_path", "negative_path"),
    ),
    BindingSpec(
        "obligation:no-deletion-state-aliases",
        "deletion-named remote state and events are absent rather than preserved as compatibility aliases",
        "development_process",
        "intent:retire-predecessors-safely",
        "C11:retire-predecessors-safely",
        "logic_writing.release.retirement",
        "contract:no-deletion-state-aliases",
        ".flowguard/models/common.py",
        "DevelopmentState",
        "test:retirement-field-replacement",
        "test_deleted_remote_fields_and_events_have_no_compatibility_alias",
        "tests/flowguard/test_model_contracts.py",
        ("happy_path", "failure_path", "negative_path", "replay"),
    ),
)


def _obligation(spec: BindingSpec) -> ModelObligation:
    return ModelObligation(
        spec.obligation_id,
        obligation_type="external_contract",
        description=spec.description,
        required_test_kinds=spec.required_kinds,
        behavior_plane=spec.plane,
        business_intent_id=spec.intent_id,
        behavior_commitment_id=spec.commitment_id,
        primary_path_id=spec.path_id,
    )


def _contract(spec: BindingSpec) -> CodeContract:
    return CodeContract(
        spec.contract_id,
        path=spec.code_path,
        symbol=spec.symbol,
        role="owner",
        implements_obligations=(spec.obligation_id,),
        behavior_plane=spec.plane,
        business_intent_id=spec.intent_id,
        behavior_commitment_id=spec.commitment_id,
        primary_path_id=spec.path_id,
    )


def _evidence(spec: BindingSpec, kind: str) -> TestEvidence:
    return TestEvidence(
        f"{spec.test_id}:{kind}",
        test_name=spec.test_name,
        path=spec.test_path,
        command=f"python -m pytest -q {spec.test_path}",
        result_status="passed",
        evidence_current=True,
        test_kind=kind,
        covered_obligations=(spec.obligation_id,),
        covered_code_contracts=(spec.contract_id,),
        assertion_scope="external_contract",
        behavior_plane=spec.plane,
        business_intent_id=spec.intent_id,
        behavior_commitment_id=spec.commitment_id,
        primary_path_id=spec.path_id,
    )


def aligned_plan() -> ModelTestAlignmentPlan:
    field_lifecycle = review_retirement_visibility_fields()
    return ModelTestAlignmentPlan(
        model_id="logic-writing-model-test-alignment",
        obligations=tuple(_obligation(spec) for spec in BINDINGS),
        code_contracts=tuple(_contract(spec) for spec in BINDINGS),
        test_evidence=tuple(
            _evidence(spec, kind)
            for spec in BINDINGS
            for kind in spec.required_kinds
        ),
        field_lifecycle_reports=(field_lifecycle,),
        field_lifecycle_projections=field_lifecycle.projections,
        require_stable_authority_ids=True,
        require_behavior_plane_binding=True,
    )


def broken_missing_actual_artifact_plan() -> ModelTestAlignmentPlan:
    plan = aligned_plan()
    return ModelTestAlignmentPlan(
        model_id="known-bad-process-green-content-not-run",
        obligations=plan.obligations,
        code_contracts=plan.code_contracts,
        test_evidence=tuple(
            item
            for item in plan.test_evidence
            if "test:reader-quality" not in item.evidence_id
        ),
        field_lifecycle_reports=plan.field_lifecycle_reports,
        field_lifecycle_projections=plan.field_lifecycle_projections,
        require_stable_authority_ids=True,
        require_behavior_plane_binding=True,
    )
