## Context

The current Logic Writing source and installed projection still carry ResearchGuard 0.4.5 and Logic Writing 3.0.1 references even though the released dependency is 0.4.11. The repository also records a legacy FlowGuard project/model authority, so a version-only edit would leave the release gate unable to establish current model ownership. See `proposal.md` for the motivation and the delta spec for observable requirements.

FlowGuard 0.68.15 supplies a current-only direct rebuild and a provider-neutral, project-owned native owner declaration. This is part of the current authority boundary, not a compatibility reader.

## Goals / Non-Goals

**Goals:**

- Make one current version identity flow through source, tests, schemas, examples, FlowGuard verification inputs, SkillGuard projection, package metadata, and release documentation.
- Model one explicit provider decision: three direct members are active; ExperimentGuard and umbrella requests are blocked before provider execution.
- Preserve provider-owned evidence and receipt ownership; Logic Writing may bind references but must not manufacture or reinterpret native ResearchGuard receipts.
- Rebuild the existing FlowGuard project authority through the official
  current-only CLI, using a clean current v4 genesis/final package and a
  project-owned native owner declaration; bind affected checks to current
  source and tests.
- Prove source, installed projection, Git tag, and GitHub Release identities independently.

**Non-Goals:**

- Adding ExperimentGuard, umbrella composition, an automatic updater, or a new compatibility layer.
- Editing the FlowGuard or ResearchGuard repositories, their open worklists, tags, releases, or installed packages.
- Rewriting historical changelog/archive evidence or changing the public adapter schema shape.

## Decisions

1. **Use a new current-provider capability.** The provider identity and scope-out behavior are externally observable and deserve a spec rather than only implementation notes. Existing routing requirements receive a small delta for the new rejection behavior.
2. **Use exact-set topology validation.** The active set is exactly `logicguard`, `sourceguard`, and `traceguard`; a set comparison plus disjoint scope-out set prevents accidental fifth-member or umbrella activation. A looser substring scan is rejected because it cannot distinguish documentation from execution.
3. **Use one version source per boundary.** Current source constants and package metadata must agree with ResearchGuard distribution/console evidence. Historical files remain immutable; no global replacement is used.
4. **Use provider-owned evidence references.** Adapter validation checks provider identity, member, locator, fingerprint, qualification, and terminal status, while preserving native payloads as opaque references. Recomputing a self-authored native receipt is not accepted.
5. **Use official FlowGuard current-only rebuild and one final owner.** First
   preview the project audit and rebuild package; use the old authority only as
   an opaque CAS guard, never as a semantic input. Write only through the
   official CLI when current inputs are real and exact. After
   source/toolchain/impact identities are frozen, run one foreground frozen
   validation owner; focused regressions may run separately.
6. **Use SkillGuard's direct-current consumer projection.** Compile from the source contract, check affected owners, stage and activate the consumer projection, then read back installed currentness and route smoke. Generated hashes are never hand-edited.

## Risks / Trade-offs

- **[Risk]** The legacy FlowGuard authority may be mistaken for a migration
  input. **Mitigation:** use only its raw authority section for CAS, build a
  clean current v4 genesis/final package, and stop if any old revision or
  manifest is opened.
- **[Risk]** A stale current fixture could be mistaken for ResearchGuard evidence. **Mitigation:** label fixture-only material and require provider-owned qualification plus current version identity for closure.
- **[Risk]** A broad version replacement could alter historical or WorldGuard-owned records. **Mitigation:** use an allowlist of current files and verify historical paths are unchanged.
- **[Risk]** Parallel Guard-family work may leave dirty or active paths. **Mitigation:** do not edit those repositories; re-check status and release/install identities and preserve all existing work.

## Migration Plan

1. Validate the OpenSpec change and freeze the clean Logic Writing worktree.
2. Update current provider/version and tests, preserving historical records and scope-outs.
3. Preview and execute the official FlowGuard current-only rebuild, then run model alignment and TestMesh checks.
4. Compile, stage, activate, and verify the SkillGuard consumer projection.
5. Run focused regressions, then the single frozen full validation.
6. Commit, push, tag `v3.0.2`, create the formal GitHub Release, and verify source/tag/release/install identities independently.

## Open Questions

None. If the official FlowGuard migration cannot obtain real current authority inputs, that is a concrete execution blocker rather than a design choice.
