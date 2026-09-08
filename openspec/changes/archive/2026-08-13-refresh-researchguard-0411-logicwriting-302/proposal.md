## Why

Logic Writing 3.0.1 still describes and tests an older ResearchGuard provider contract, while the installed and released ResearchGuard is now 0.5.0 and the installed FlowGuard toolchain is 0.69.0. This patch keeps the existing writing behavior but makes the current provider identity, direct-member boundary, model evidence, installation projection, and release surface agree before publishing 4.0.0.

## What Changes

- Raise Logic Writing's patch version from 3.0.1 to 4.0.0.
- Replace current ResearchGuard dependency assertions with 0.5.0 and record FlowGuard 0.69.0 as the validation toolchain.
- Keep exactly three active direct ResearchGuard members: LogicGuard, SourceGuard, and TraceGuard.
- Keep ExperimentGuard and the ResearchGuard umbrella route explicitly out of scope, with visible blocking and zero provider execution for those requests.
- Strengthen topology, version-identity, adapter, schema, receipt-boundary, and negative-path tests without changing the public adapter shape.
- Repair the Logic Writing FlowGuard project/model authority through the official current migration path, then run affected model and test-mesh checks.
- Declare Logic Writing's exact current model denominator and native owner bindings
  in the project repository; FlowGuard validates that declaration without
  embedding Logic Writing model IDs in its public runtime.
- Recompile and install the SkillGuard consumer projection, run installed-route smoke checks, and publish a new v4.0.0 GitHub release.
- Do not add an automatic updater, ExperimentGuard support, compatibility readers, aliases, fallbacks, or a new provider route.

## Capabilities

### New Capabilities

- `current-researchguard-provider`: Defines the observable current-provider identity, direct-member boundary, scope-out behavior, and installed-projection parity for Logic Writing.

### Modified Capabilities

- `unified-routing`: The provider selection contract now rejects unsupported ExperimentGuard and umbrella requests instead of allowing an ambiguous provider path.

## Impact

- Affected Logic Writing provider preflight, adapter references, schemas, fixtures, topology checks, focused tests, FlowGuard project records/models, SkillGuard generated projection, release documents, and verification contract.
- ResearchGuard and FlowGuard repositories are dependencies only; their already-published releases and installed projections are evidence inputs and will not be edited or rolled back by this change.
- Existing v3.0.1 routes and valid adapter inputs remain supported; no public
  adapter field is removed, renamed, or made newly required. The internal
  FlowGuard authority is rebuilt directly into the current v4/v5 format; no
  compatibility reader or old authority fallback is added.
