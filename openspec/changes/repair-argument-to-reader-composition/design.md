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
