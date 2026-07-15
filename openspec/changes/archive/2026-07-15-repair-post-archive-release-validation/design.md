## Context

OpenSpec change directories are lifecycle-scoped: an active directory is moved beneath `openspec/changes/archive/` when the change closes. The repository incorrectly used that lifecycle-scoped location as the permanent input to release wrappers and FlowGuard TestMesh. Pre-archive evidence therefore could not prove post-archive source health.

## Goals / Non-Goals

**Goals:**

- Keep exactly one current release verification authority at a path that archival does not move.
- Preserve active change verification as provider-scoped evidence without making it the live release authority.
- Add an explicit post-archive full regression before a tag or GitHub Release is created.
- Preserve published release immutability and repair with a higher patch version.

**Non-goals:**

- Add an active-or-archive path search, alias, compatibility reader, or fallback.
- Rewrite the archived create-logic-writing change or move v1.0.0/v1.0.1 tags.
- Change the Logic Writing skill package or reinstall an unchanged projection.

## Decisions

### One stable current authority

`openspec/verification-contract.yaml` is the only live repository release contract. Scripts, tests, AGENTS guidance, FlowGuard commitment lookup, and TestMesh bind this exact path. Archived change contracts remain immutable historical evidence and no live consumer reads them.

### Two-phase release closure

The active repair change is verified in full before archival. Archival then changes the source tree. The archived tree must pass the stable release contract, the complete pytest suite, FlowGuard model/alignment/TestMesh checks, strict validation of all current OpenSpec specs and changes, privacy/public-source checks, and release-surface checks. A tag may be created only from that post-archive green commit.

### Immutable patch repair

The failed fresh-clone observation limits v1.0.1 confidence but does not authorize history rewriting. v1.0.1 stays at its published commit. The corrected source becomes v1.0.2 with release notes that name the repair and its verification boundary.

## Risks / Trade-offs

- A stable contract adds a maintained repository-level artifact. This is intentional: its lifecycle matches the repository release, unlike an individual change.
- The post-archive gate repeats some high-value checks. That repetition is required because archival changes governed source identity; pre-archive receipts cannot prove the new snapshot.
- FlowGuard project adoption still reports the separately bounded `suite_map_missing` gap. Model and test evidence may pass, but no claim of complete vendored FlowGuard agent-suite adoption is made.

## Migration Plan

1. Add the stable release contract and repoint every live consumer.
2. Add the archival lifecycle regression and FlowGuard model-miss coverage.
3. Run focused and full active-change verification.
4. Archive this repair change and strictly validate all canonical OpenSpec specs.
5. Run the stable post-archive release gate on the final source snapshot.
6. Commit, push, tag, and publish v1.0.2 without changing older tags.
7. Validate a fresh clone of v1.0.2 and recheck installation, routing, and repository visibility.
