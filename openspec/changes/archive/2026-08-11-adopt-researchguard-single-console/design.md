## Context

ResearchGuard `0.4.5` is the released provider identity used by this patch. It has four native members, but Logic Writing directly consumes only three existing semantic owners. Because the provider identity is being repaired while Logic Writing's public routes remain unchanged, the frozen source version is `3.0.1`:

| Semantic owner | Console command | Primary path |
| --- | --- | --- |
| LogicGuard | `researchguard logic` | `primary:researchguard:logic` |
| SourceGuard | `researchguard source` | `primary:researchguard:source` |
| TraceGuard | `researchguard trace` | `primary:researchguard:trace` |

`ExperimentGuard` and `researchguard run` (the umbrella composition route) are not Logic Writing `3.0.1` capabilities. A request for either is a visible scope block; it must not silently fan out to multiple members.

The consumer must adopt this authority without hard-coding a sibling checkout, adding compatibility readers, or treating another member as recovery. ResearchGuard owns the native result and receipt schema. Logic Writing stores an opaque provider reference plus its own adapter binding; it does not recreate the provider's validator.

## Goals / Non-Goals

**Goals:**

- Keep `logic-writing` as this repository's sole installable skill.
- Preserve three exact domain owners while resolving all three through one versioned console.
- Make missing, mismatched, timed-out, or failing provider capability checks visible and terminal.
- Eliminate current consumer references to retired LogicGuard satellite ids and old module commands.
- Bind fixtures, FlowGuard, tests, SkillGuard supervision, installation, and release metadata to the same `0.4.5`/`3.0.1` identity.
- Preserve the existing four writing routes and their semantic behavior.

**Non-Goals:**

- Changing ResearchGuard member algorithms or receipt semantics.
- Adding ExperimentGuard or umbrella composition to Logic Writing.
- Building or changing an automatic updater for other computers.
- Changing global routing or touching FlowPilot.

## Decisions

### One executable provider, three semantic owners

`provider_preflight.py` keeps the caller-facing provider ids `logicguard`, `sourceguard`, and `traceguard`, because those ids identify the native domain owner in adapter contracts. Each id maps to the same `researchguard` executable plus one exact member command and primary path. This avoids adding a redundant `researchguard` owner to schemas while still proving the executable suite identity.

### Capability probing is console-only and fail-closed

Preflight resolves the one `researchguard` console executable from the installed ResearchGuard distribution record, reads its distribution version, executes `researchguard --version`, and then executes only the selected member's `--help`. The distribution, console, and supported version must all be exactly `0.4.5`; a mismatch is `blocked`. A missing or ambiguous distribution executable, non-zero exit, or timeout yields `provider_unavailable`. It will not import old modules, run `python -m`, inspect a sibling checkout, retry another member, or accept `--provider-root` for these three providers.

### Direct members only

One Logic Writing adapter request has one native owner. Logic Writing may produce several sequential handoffs, but each handoff is still one direct member. ExperimentGuard and the umbrella `run` command are explicit scope-outs and execute zero provider commands.

### Opaque native evidence reference

The provider's raw result and receipt remain opaque ResearchGuard-owned material. Logic Writing validates only the frozen provider identity, member/path binding, immutable locator/fingerprint, provider qualification/status, and request binding. It may create its own managed closure receipt, but that receipt cannot be presented as a ResearchGuard native receipt. If the installed ResearchGuard release does not expose a provider-owned qualification/locator needed for a current claim, the Logic Writing claim remains blocked instead of fabricating one.

### Version and installation identity move together

`VERSION`, package metadata, both README source badges, the changelog, source reconciliation, current OpenSpec requirements, the release-retirement checklist, the consumer manifest, and the installation check identify source version `3.0.1`. SkillGuard is recompiled only after those inputs and the consumer distribution are frozen. No installed projection is activated until the source checks are current.

### Zero residual is target-owned

A focused checker scans current consumer source, tests, active OpenSpec, and FlowGuard material while excluding archived history and generated SkillGuard projections. It rejects retired satellite ids, old module commands, direct old imports, bare Guard route ids, unsupported provider versions, and active ExperimentGuard/umbrella paths.

## Risks / Trade-offs

- [ResearchGuard may be installed outside ambient PATH] → Resolve its one current distribution entry point and materialized executable directly.
- [Subprocess probing can time out] → Preserve `provider_unavailable` with timeout evidence and stop; never branch to another provider.
- [Fixture route changes invalidate content hashes] → Recompute every affected receipt and handoff reference, then run the full fiction regression.
- [ResearchGuard native qualification may not be available to this consumer] → Keep the adapter blocked and report the missing provider contract; do not copy a validator into Logic Writing.
- [Concurrent provider repositories may be dirty] → Bind this patch to the released `v0.4.5` tag/package/console identity and do not overwrite or merge another AI's worktree.

## Migration Plan

1. Update the existing FlowGuard topology and receipt-boundary invariants.
2. Replace provider version assumptions with the single `0.4.5` console identity and focused tests.
3. Update skill guidance, adapter references, current route ids, and ResearchGuard-owned fixture references.
4. Add zero-residual and scope-out validation for ExperimentGuard/umbrella paths.
5. Update and compile the SkillGuard contract.
6. Freeze the `3.0.1` source and installation-identity inputs.
7. Run focused and full repository validation on the frozen post-archive source snapshot.
8. Install the exact consumer projection, push the default branch, create the annotated tag and GitHub Release, and prove source/install/Git/tag/Release identity separately.

Rollback is a source-level revert before tag publication. After publication, corrections use a higher patch version; no compatibility layer or updater is retained.
