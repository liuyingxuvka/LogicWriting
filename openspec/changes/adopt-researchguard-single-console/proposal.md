## Why

Logic Writing still preflights LogicGuard, SourceGuard, and TraceGuard as independent Python providers even though their current authority is the versioned ResearchGuard suite. That stale topology permits divergent installation identities and makes a failed member look recoverable through an alternate module path.

## What Changes

- **BREAKING** Replace every direct LogicGuard, SourceGuard, and TraceGuard provider call with the sole `researchguard` console.
- Preserve `logicguard`, `sourceguard`, and `traceguard` as exact semantic owners while binding them to `primary:researchguard:logic`, `primary:researchguard:source`, and `primary:researchguard:trace`.
- Fail visibly when the console or selected member capability is unavailable; add no module import, `python -m`, alias, compatibility reader, or retry path.
- Remove the retired five LogicGuard satellite-skill ids and `traceguard-library` from current consumer guidance and tests.
- Keep Logic Writing as the only directly installed skill owned by this repository.
- Freeze the changed provider topology as source version `2.1.0` and publish
  the candidate commit only to the existing review branch.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `unified-routing`: Require one ResearchGuard console binding for the three research Guard semantic owners.
- `evidence-freshness-closure`: Bind provider availability and native receipts to the current ResearchGuard suite/member identity without changing domain ownership.

## Impact

Affected surfaces include `skills/logic-writing/SKILL.md`, ResearchGuard adapter references, provider preflight code, fiction Guard receipt fixtures, FlowGuard topology models, focused tests, Logic Writing version/release surfaces, and the Logic Writing SkillGuard maintenance contract. Installation, global routing, default-branch publication, tags, and GitHub Releases remain outside this candidate change.
