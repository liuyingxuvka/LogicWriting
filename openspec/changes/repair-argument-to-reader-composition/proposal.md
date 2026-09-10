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

## Current implementation-round amendment (R00–R10, 2026-09-09)

The candidate framing above is retained as the historical A01 proposal. The
current recovery round is authorised to carry the change through integration
and verification on the local machine. It therefore extends the scope to the
single installable `skills/logic-writing` source, the production reader
pipeline, the local process executor, the quality producer and consumer, the
ResearchGuard installed-console handoff, the temporary consumer projection,
and the final source synchronisation gate. It does not change the shared
FlowGuard checkout or create a second provider, solver, writer, or judge.

The current contract has four separate claim surfaces. A source change can be
implemented without proving the current FlowGuard model; a model receipt can
be current without proving article quality; a real quality run can pass without
proving daily installation; and a GitHub readback can prove only the pushed
source commit. The R00–R10 ledger in `tasks.md` records each surface
separately. A row is closed only when its named owner has a current receipt or
test result; inherited `[x]` rows above describe the historical candidate and
are not evidence of current closure.

The production path is deliberately generic: ResearchGuard supplies bounded
evidence and research handoff, while LogicWriting derives reader order,
materiality, composition, and the final `writer_input`. Case labels, rubrics,
expected answers, comparison labels, and judge preferences stay in the outer
quality harness and never enter planner or writer input. Missing provider
execution, incomplete process cleanup, stale model identity, missing
installation projection, or incomplete held-out evidence remains an explicit
non-passing state; no fixture score, copied answer, retry, or fallback may
close it.

The current recovery also makes the reader-spine boundary testable: the writer
receives the minimal ordered projection of the CompositionPlan, while raw
ledgers, model/status fields, complete gaps, private receipts, and duplicate
evidence remain internal. This is the concrete product change that addresses
fragmented card-by-card prose; changing model pricing or silently weakening
quality gates is outside the proposal.
