## Why

The v1.0.1 source passed its final validation while the original OpenSpec change was active, but archiving that change moved its verification contract. Three repository tests still referenced the former active-change path, so a fresh clone of the published tag produced 162 passes and 3 failures. The release evidence was current before archival but did not cover the repository after the archival state transition.

This is a release-process defect, not a reason to rewrite published history. The v1.0.1 tag and release remain immutable. The repair must establish one stable current verification authority, prove that archival cannot break live consumers, and publish the corrected source as v1.0.2 only after a post-archive full regression passes.

## What Changes

- Add one current release verification contract at `openspec/verification-contract.yaml`, outside active and archived change directories.
- Make every live validation consumer use that exact stable path; historical archived contracts remain records only and are not fallback authorities.
- Add a regression that rejects live references to an active change's verification contract after the change is archived.
- Model OpenSpec archival as a source-path lifecycle transition in FlowGuard and bind the observed v1.0.1 failure plus the same-class cases to Model-Test Alignment and TestMesh.
- Require two release phases: full verification while the repair change is active, then a full repository/FlowGuard/OpenSpec release gate after archival.
- Bump the corrected public source to v1.0.2. Existing v1.0.0 and v1.0.1 tags and releases SHALL NOT be moved, replaced, or deleted.

## Capabilities

### Modified Capabilities

- `evidence-freshness-closure`: add a stable release-contract authority and a mandatory post-archive regression gate.

## Impact

- Live validation paths in repository instructions, wrappers, FlowGuard models, TestMesh, and tests change to the stable contract.
- Release metadata advances from 1.0.1 to 1.0.2.
- No Logic Writing route behavior or installed skill projection changes.
- No predecessor repository is deleted; both remain private for the user to delete later.
