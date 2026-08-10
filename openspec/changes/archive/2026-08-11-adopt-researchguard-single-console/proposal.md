## Why

Logic Writing's current consumer contract still describes the ResearchGuard provider as the old `0.1.x` suite even though the installed and released provider is now `0.4.5`. The source, fixtures, preflight checks, and release records therefore do not prove that the three existing member routes use the same current provider identity. A failed member must remain visible; this change must not introduce an updater, compatibility reader, or alternate execution path.

## What Changes

- Preserve `logicguard`, `sourceguard`, and `traceguard` as exact semantic owners while binding them to the sole `researchguard` console and its exact `logic`, `source`, and `trace` members.
- Require the installed distribution record, console output, and frozen provider identity to agree on ResearchGuard `0.4.5`; reject another version visibly.
- Keep native ResearchGuard result/receipt ownership with ResearchGuard. Logic Writing may store an opaque, fingerprinted reference and its own outer binding, but it must not manufacture a provider-native receipt.
- Keep the existing four Logic Writing routes and their behavior. `experimentguard` and the ResearchGuard umbrella are explicitly outside this patch.
- Update current fixtures, documentation, FlowGuard bindings, tests, and release metadata to Logic Writing `3.0.1` without rewriting historical records.
- Do not add or modify an automatic updater. Other computers remain outside this repository change and continue using the existing upgrade mechanism.

## Capabilities

### New Capabilities

None. This is a provider-identity and maintenance-correctness patch, not a new writing route.

### Modified Capabilities

- `unified-routing`: Require one ResearchGuard console binding for the three research Guard semantic owners.
- `evidence-freshness-closure`: Bind provider availability and opaque native evidence references to the current ResearchGuard suite/member identity without changing domain ownership.

## Impact

Affected surfaces include `skills/logic-writing/SKILL.md`, ResearchGuard adapter references, provider preflight code, fiction Guard fixtures, FlowGuard topology models, focused tests, Logic Writing version/release surfaces, the Logic Writing SkillGuard maintenance contract, the local consumer installation, Git, and the GitHub release. Global routing and any automatic updater remain outside this change.
