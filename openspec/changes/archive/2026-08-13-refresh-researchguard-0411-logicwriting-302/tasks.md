## 1. OpenSpec and worktree freeze

- [x] 1.1 Validate this change with `openspec validate refresh-researchguard-0411-logicwriting-302 --strict --json` and confirm the worktree, remote, coordination file, and parallel Guard-family boundary are understood.
- [x] 1.2 Read the apply instructions and record the exact current FlowGuard 0.69.0 and ResearchGuard 0.5.0 release/install identities without editing those repositories.

## 2. Current provider contract

- [x] 2.1 Update current Logic Writing version metadata and release surfaces from 3.0.1 to 4.0.0 while preserving historical entries.
- [x] 2.2 Update current ResearchGuard references to 0.5.0 and current FlowGuard verification identity to 0.69.0 only in files that describe the current contract.
- [x] 2.3 Strengthen provider preflight and topology validation to enforce the exact three-member set and one console identity.
- [x] 2.4 Make ExperimentGuard and umbrella requests visibly blocked with zero provider execution, and add no updater, alias, fallback, or compatibility reader.
- [x] 2.5 Update adapter/schema/reference fixtures and receipt-boundary validation so native ResearchGuard material remains opaque and provider-owned.

## 3. Tests and evidence

- [x] 3.1 Add wrong-version, metadata/CLI mismatch, missing/extra member, timeout/no-retry, scope-out, foreign-member, fake-receipt, stale, and non-terminal negative tests.
- [x] 3.2 Preserve valid v3.0.1 route behavior and update only current ResearchGuard fixtures; leave historical and WorldGuard-owned fixtures unchanged.
- [x] 3.3 Extend installed-route smoke coverage to fiction, travel, and the academic child handoff, then run focused provider, adapter, schema, authority, and route regressions.

## 4. FlowGuard model and process alignment

- [x] 4.1 Run current FlowGuard project-audit and current-only rebuild dry-run; inspect proposed files and blockers before any write.
- [x] 4.2 Use the official FlowGuard current-only authority-rebuild route to replace legacy authority only with real current evidence, preserving existing behavior commitments and ownership. The old authority is an opaque CAS value only; no v2/v3 reader or migration input is allowed.
- [x] 4.3 Update the verification contract and affected model/test bindings to FlowGuard 0.69.0, declare the exact seven-model native owner bindings in the Logic Writing repository, then run model alignment, conformance/replay, loop/stuck, progress/fairness, contract/refinement, and TestMesh checks.
- [x] 4.4 Record the project adoption/process evidence and ensure stale or skipped checks are not presented as passed; the resolved legacy model-authority blocker remains documented for audit history.

  - Previous blocker evidence: FlowGuard 0.68.14 rejected the accepted
    `flowguard.model_revision_set.v2` and the
    `flowguard.model_regression_manifest.v3`. The replacement path is now the
    0.69.0 current-only authority rebuild. Do not change schema strings by
    hand, create a fake v4/v5 artifact, add a compatibility reader, or consume
    the parallel FlowGuard worktree change as release evidence. Resume 4.2 only
    with a clean current v4 package, exact current design contributions,
    project-owned native-owner evidence, and a verified staging lineage. This
    blocker was resolved by the v0.69.0 current-only rebuild; no legacy
    reader or migration path was added.

## 5. SkillGuard source and installation

- [x] 5.1 Run the SkillGuard source compile check and identify all affected owners for the changed source, schemas, tests, and references.
- [x] 5.2 Compile the current source contract, stage a 4.0.0 consumer projection, activate it through the official installer, and verify installation currentness.
- [x] 5.3 Run installed route smoke and confirm the consumer projection contains no SkillGuard author receipts or stale 3.0.1/0.4.5 current references.

## 6. Final validation and release

- [x] 6.1 Run focused regressions, public/privacy/source-reconciliation checks, strict OpenSpec validation, and the complete pytest suite; fix failures at their source.
- [x] 6.2 Freeze source, dependency, toolchain, impact, model, and install identities and run exactly one foreground frozen full validation owner.
- [x] 6.3 Mark all implemented tasks complete, verify the OpenSpec change, sync/organize its specs, and archive it only after implementation evidence is current.
- [x] 6.4 Commit the scoped Logic Writing changes, push `main`, create annotated tag `v4.0.0`, publish the GitHub Release, and verify local/remote source, tag, release, package metadata, and installed projection separately.
- [x] 6.5 Perform the predictive-KB postflight and record a structured observation only if this work exposed a reusable lesson, route gap, or validation weakness.
