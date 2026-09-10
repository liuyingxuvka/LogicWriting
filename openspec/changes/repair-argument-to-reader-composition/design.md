## Context

The candidate starts from LogicWriting `4.0.0` with one current route owner per request and a managed source contract whose compiled contract and check manifest are generated artifacts. The A00 governance gate is blocked, so this work is an isolated candidate only. Existing route packs already contain the runtime references and examples, but their consumer closure is implicit; the reader-v2 fixture currently exercises a synthetic complete chain and labels it as blind quality evidence.

## Goals / Non-Goals

**Goals:**

- Make installation projection metadata express the four required route/example subtrees without editing generated SkillGuard outputs.
- Validate staged consumer resources by recursive local reference traversal, manifest coverage, and JSON正文 associations.
- Preserve twelve case inputs and make their protocol status explicit while adding a real-provider runner with a terminal unavailable state.
- Record A01 requirements and a bounded implementation/verification map for this candidate.

**Non-Goals:**

- No changes to ResearchGuard, reader pipeline, `derive_closure`, SkillGuard engine, FlowGuard records, installed skills, or release publication.
- No automatic provider discovery, paid API invocation, fixture score fallback, or fabricated article/judge output.
- No attempt to claim formal author admission while A00 remains blocked.

## Decisions

1. **Source metadata is declarative.** Add only `content_role_overrides` to `skills/logic-writing/.skillguard/contract-source.json`; the compiler remains the sole producer of `compiled-contract.json` and `check-manifest.json`. This keeps source authority separate from generated projections.
2. **Closure is consumer-stage based.** The checker takes a source/stage root and a manifest, resolves Markdown links and JSON path fields from the selected route, and emits deterministic missing/escaped/test-only findings. This catches resources that route selection alone cannot observe.
3. **Route references are explicit and depth-aware.** Fiction names compact/short and longform references separately; travel names its native compiler, workflow, traveler profile, and negative-evidence/fallback references. The writer still loads only the selected route's required set.
4. **Benchmark execution is backend-injected.** The runner accepts a configured backend adapter or reports `execution_provider_unavailable`; it has no secret lookup or paid-service fallback. Protocol fixtures remain useful for transport/fingerprint regression but cannot supply quality scores.
5. **Evidence is isolated.** Runner and closure receipts live under `resources-benchmark-evidence/` in the task workspace, outside source authority. Candidate source edits retain portable relative paths and contain no private article or machine-specific evidence.

## Risks / Trade-offs

- [Generated contract mismatch] → Leave generated files untouched, record the candidate compile blocker, and validate source metadata plus staged closure independently.
- [Overly broad recursive loading] → Keep closure route-scoped and treat only explicitly selected manifest paths and local links as required.
- [False quality pass] → Require real writer/judge provenance and emit unavailable/incomplete when execution or comparable pairs are absent.
- [Fixture regressions become noisy] → Preserve transport assertions while renaming tests and adding explicit `protocol_only` metadata.

## Migration Plan

Build a clean candidate consumer stage from the source, run resource closure, then run protocol tests and invoke the benchmark runner without a backend to verify the terminal unavailable receipt. If formal admission later permits compilation, regenerate SkillGuard projections through the governed owner and rerun affected checks; do not copy this candidate into the daily installation.

## Current implementation-round amendment (R00–R10, 2026-09-09)

The context and non-goals above describe the earlier isolated candidate and
remain as history. For the current implementation round, the integration
boundary is the following:

* `skills/logic-writing` is the only LogicWriting source authority. The
  installed ResearchGuard console is the only ResearchGuard provider used by
  the production path. The shared `D:\FlowGuard_20260427` checkout is an
  external dependency and is never edited by this change.
* R01–R03 own process lifecycle, job identity, evidence provenance, and the
  single acceptance-owner entrypoint. R04 owns the generic
  `prepare_production_reader_input` chain. R05–R06 consume and validate
  ResearchGuard's native child/parent evidence and bound its suite checker.
  R07–R10 own isolated projection, quality, final regression, installation,
  and source publication in that order.
* Planner calls are a distinct execution role. They write a re-openable raw
  capture and execution record with their own run/context identity; they are
  never counted as writers or judges. A writer receives the validated
  `ReaderBrief.writer_input` projection only. An independent judge receives
  only the submitted artifact and its declared evaluation contract.
* Research importance, reader progression, and editorial prominence remain
  separate dimensions. ResearchGuard may deepen an important unresolved
  branch; LogicWriting decides which closed contribution belongs in the
  reader line and in what order. A limitation is included only when its
  materiality and reader duty require it, so the output does not become a
  list of every model field.
* The current production chain must be tested with the installed provider,
  current schemas, and re-openable receipts. Synthetic planner/provider
  doubles are permitted only at the process boundary of focused tests and
  carry `protocol_only` semantics. They cannot support `quality_passed`,
  `product_path_verified`, `installed_current`, or release claims.

The acceptance matrix is intentionally five-dimensional and is maintained in
the appended ledger: `implemented`, `protocol_tested`,
`current_model_closed`, `real_quality_proved`, and `installed_current`. The
first two can be green while the latter three remain open. Every final report
must preserve that distinction and identify the exact first failing gate.

## Current reader-spine hardening amendment (2026-09-10)

The existing `ReaderBrief.writer_input` contract is retained, but the
production compiler must now make its shape explicitly spine-first. It will
derive one ordered reader graph from the current `CompositionPlan`: root
question and conclusion, major units, predecessor/forward links, essential
evidence anchors, editorial dispositions, and conclusion-sensitive limits.
The complete model/receipt ledger remains available to internal audit only and
is not an equivalent writer input. The writer prompt therefore consumes the
spine and permitted reader material, while the producer receipt keeps the
full ledger and a fingerprinted projection record for re-opening.

This amendment is intentionally separate from model scoring. A deterministic
projection validator and actual-text diagnostics must first establish that a
finding is not promoted to a paragraph without reader work, that process-only
limits are consolidated, and that material limits remain adjacent to the
affected claim. Only after those checks pass may the real writer/judge quality
sequence run. A provider or transport failure remains an explicit incomplete
result.
