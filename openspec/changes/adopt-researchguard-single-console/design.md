## Context

Logic Writing is one consumer skill with four final writing routes. Its adapter envelopes already preserve `logicguard`, `sourceguard`, and `traceguard` as semantic owners, but provider preflight imports three independent Python packages. ResearchGuard v0.1.0 now provides the sole executable console and exact member bindings. Because this changes the external provider dependency while preserving Logic Writing's one-skill behavior, the frozen candidate source version is `2.1.1`:

| Semantic owner | Console command | Primary path |
| --- | --- | --- |
| LogicGuard | `researchguard logic` | `primary:researchguard:logic` |
| SourceGuard | `researchguard source` | `primary:researchguard:source` |
| TraceGuard | `researchguard trace` | `primary:researchguard:trace` |

The consumer must adopt this authority without hard-coding a sibling checkout, adding compatibility readers, or treating another member as recovery.

## Goals / Non-Goals

**Goals:**

- Keep `logic-writing` as this repository's sole installable skill.
- Preserve three exact domain owners while resolving all three through one versioned console.
- Make missing, timed-out, or failing provider capability checks visible and terminal.
- Eliminate current consumer references to retired LogicGuard satellite ids and old module commands.
- Bind fixtures, FlowGuard, tests, and SkillGuard supervision to the same topology.
- Bind every current source-version surface and installation-identity input to
  the same `2.1.1` candidate tree.

**Non-Goals:**

- Installing ResearchGuard or Logic Writing.
- Changing ResearchGuard member algorithms or receipt semantics.
- Publishing the default branch, tagging, creating a GitHub Release, or
  updating global routing. Pushing the existing candidate PR branch is allowed.
- Touching FlowPilot.

## Decisions

### One executable provider, three semantic owners

`provider_preflight.py` will keep the caller-facing provider ids `logicguard`, `sourceguard`, and `traceguard`, because those ids identify the native domain owner in adapter contracts. Each id maps to the same `researchguard` executable plus one exact member command and primary path. This avoids adding a redundant `researchguard` owner to schemas while still proving the executable suite identity.

The alternative—renaming every adapter owner to `researchguard`—would erase domain authority and weaken receipt checks.

### Capability probing is console-only and fail-closed

Preflight resolves the one `researchguard` console executable from the installed
ResearchGuard distribution record, executes `researchguard --version`, then
executes `researchguard logic|source|trace --help`. It does not depend on the
ambient PATH and does not retain PATH lookup as another authority. A missing or
ambiguous distribution executable, non-zero exit, or timeout yields
`provider_unavailable`. It will not import the old modules, run `python -m`,
inspect a sibling checkout, retry another member, or accept `--provider-root`
for these three providers.

The timeout is a bounded diagnostic limit, not a recovery trigger. Increasing it later remains a single-path configuration change.

### Current primary paths replace old route ids

Consumer fixtures that currently identify `logicguard`, `sourceguard`, or `traceguard` as an executable route will use the ResearchGuard primary paths. Semantic `guard_id` and `native_owner` fields remain unchanged.

### Version and installation identity move together

`VERSION`, package metadata, both README source badges, the changelog, source
reconciliation, current OpenSpec requirements, and the release-retirement
checklist identify source version `2.1.1`. SkillGuard is recompiled only after
those inputs and the consumer distribution are frozen. No installed projection
is activated in this change.

### Zero residual is target-owned

A focused checker will scan current consumer source, tests, active OpenSpec, and FlowGuard material while excluding archived history and generated SkillGuard projections. It will reject retired satellite ids, old module commands, direct old imports, and bare Guard route ids in executable receipt fields.

## Risks / Trade-offs

- [ResearchGuard is not installed during this phase] → Preflight tests use controlled process doubles; cross-repository source validation proves the declared console contract, while installation remains a later synchronized step.
- [Subprocess probing can time out] → Preserve `provider_unavailable` with timeout evidence and stop; never branch to another provider.
- [Fixture route changes invalidate content hashes] → Recompute every affected receipt and handoff reference, then run the full fiction regression.
- [Generated SkillGuard contracts become stale] → Recompile only after source, tests, and model identities are frozen.

## Migration Plan

1. Add the FlowGuard topology and zero-fallback invariants.
2. Replace provider preflight with the single-console mapping and focused tests.
3. Update skill guidance, adapter references, current route ids, and content-addressed fixtures.
4. Add zero-residual validation.
5. Update and compile the SkillGuard contract.
6. Freeze the `2.1.1` source and installation-identity inputs.
7. Run focused and full repository validation without installing, tagging, or
   creating a GitHub Release.
8. Commit and push the candidate to the existing review branch.

Rollback is a source-level revert of this change before installation. No runtime compatibility layer is retained.

## Open Questions

None. ResearchGuard v0.1.0 is the frozen dependency contract for this change.
