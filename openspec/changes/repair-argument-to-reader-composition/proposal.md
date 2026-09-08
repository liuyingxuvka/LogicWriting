## Why

The current LogicWriting pipeline can preserve a large model and a checklist
while projecting too little of the selected route into the writer. That makes
the generated article enumerate small points, repeat limitations, and lose the
reader's main line. The candidate change makes the existing CompositionPlan a
single source for a controlled reader projection, editorial dispositions, and
verifiable independent evaluation.

## What Changes

- Extend the ReaderBrief envelope with a hash-bound `writer_input` view that
  carries route-specific reader jobs, order, selected evidence, and necessary
  boundaries without leaking private receipts or model diagnostics.
- Add explicit materiality and editorial dispositions so every native
  limitation is accounted for while only reader-useful material reaches prose.
- Validate the composition graph, route-specific review obligations, actual
  output bytes, and current audit derivations through one deterministic owner.
- Record real writer/judge execution provenance, including pair-input binding
  for blind comparisons; classify protocol fixtures separately from real
  quality evidence.
- Restore the nested route resources needed by the consumer projection and add
  a closure check for links and manifests.
- **BREAKING**: replace implicit top-N/old writer-input success paths with the
  current typed projection and execution contracts; stale or incomplete inputs
  remain non-passing.

## Capabilities

### New Capabilities

- `reader-execution-evidence`: Bind writer and independent judge outputs to
  actual execution contexts, inputs, and immutable receipt fields.
- `consumer-resource-closure`: Verify that selected route resources form a
  complete clean consumer projection.

### Modified Capabilities

- `reader-facing-synthesis`: Add a controlled writer projection, editorial
  material dispositions, current byte-level audit, and closure derivation.

## Impact

Affected files are the LogicWriting skill's reader pipeline, schemas, route
references, SkillGuard contract-source metadata, focused unit/adversarial/e2e
tests, and the candidate OpenSpec artifacts. The registered source checkout,
installed projection, shared SkillGuard engine, and release state remain outside
this candidate change while the A00 governance gate is blocked.
