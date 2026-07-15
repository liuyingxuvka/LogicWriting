---
name: logic-writing
description: Use for deep, source-backed investigation and for creating or substantively revising academic papers, theses, literature reviews, proposals, reports, and other evidence-heavy writing. Routes each task to one final owner, coordinates SourceGuard, LogicGuard, TraceGuard, FlowGuard, Documents, and PDF without replacing them, and turns internal evidence work into clear prose for real readers. Skip for quick factual lookups, grammar-only edits, and casual low-stakes copy.
---

# Logic Writing

## Purpose

Logic Writing has one entrypoint and two focused routes. It investigates hard
questions, builds defensible academic artifacts, and translates internal
analysis into language a reader can follow.

## Entrypoint Scope

This entrypoint owns routing, bounded handoffs, freshness, reader-facing
translation, and final closure. It does not take over a specialist's native
judgment or evidence authority.

## Use When

Use this skill for a deep source-backed investigation or for creating or
substantively revising an academic paper, thesis, literature review, proposal,
or other evidence-heavy artifact.

## Do Not Use When

Do not use it for a quick factual lookup, grammar-only edit, casual low-stakes
copy, or a task whose final deliverable is owned entirely by one specialist
without a Logic Writing artifact.

## Entrypoint Acceptance Map

Select exactly one final owner by the terminal deliverable, not by the first
action:

- Use `investigation` when the final product is a research report, briefing,
  evidence package, decision note, or answer to a contested question.
- Use `academic-writing` when the final product is a paper, thesis chapter,
  dissertation section, literature review, proposal, or substantive revision.
- Academic writing may send a bounded evidence-gap request to investigation.
  The academic route remains the final owner.
- If the terminal deliverable is materially ambiguous, ask one focused
  question. Never activate two final owners.
- Exit visibly for grammar-only edits, quick lookups, and out-of-scope work.

Read [references/router.md](references/router.md) for routing details.

## Local Material Routing

Read only the route, shared contract, schema, and adapter reference needed for
the selected work. Do not load both route playbooks by default. Local scripts
validate envelopes, derive freshness, and calculate closure; installed
specialists retain their own domain work.

## Required Workflow

### Preserve specialist ownership

This skill is an orchestration shell. It calls installed specialist skills and
consumes their native receipts; it does not recreate their domain decisions:

- SourceGuard owns evidence-discovery planning and source-depth status.
- LogicGuard owns source preservation, argument support, structure, citation
  semantics, model depth, and synthesis plans.
- TraceGuard owns material temporal, causal, implementation, competing-story,
  counterfactual, and prediction-boundary analysis.
- FlowGuard owns process order, state, freshness, and closure behavior.
- Documents owns DOCX/Word/Google Docs mutation, tracked changes, comments,
  rendering, and page-level document QA.
- PDF owns PDF extraction, creation, rendering, and visual inspection.

Before every required adapter call, verify that its real provider is available.
If it is unavailable, return the typed degraded state. Never substitute a local
imitation or claim that the native check ran.

Validate the bounded handoff with `scripts/validate_adapter_request.py` before
the native call and `scripts/validate_adapter_result.py` after it. These
envelopes preserve the specialist's own route, receipt, scope, and failure
state; they do not re-run or reinterpret the specialist's native check.

Load only the relevant adapter reference under `references/adapters/`.

### Run the selected route

### Investigation

Read [references/routes/investigation.md](references/routes/investigation.md).
Begin with the claim, decision, scope, source roles, and stopping rule. Preserve
concrete sources through LogicGuard's source library before deeper synthesis.
Use SourceGuard to plan discovery, and invoke TraceGuard only when the claim
actually depends on a trace. Return a current ResearchPacket before prose.

### Academic writing

Read [references/routes/academic-writing.md](references/routes/academic-writing.md).
Model the real artifact units before broad drafting or revision. Deepen
important shallow units, keep a revision-provenance record, and use bounded
investigation requests for missing evidence. The academic route integrates the
evidence and owns the final artifact.

### Use the two-room writing boundary

Internal ledgers, Guard names, route ids, model ids, status fields, and agent
instructions belong in the work room. The prose writer receives a sanitized
ReaderBrief containing the reader question, genre, concepts, evidence,
alternatives, limitations, sequence, citations, and safe wording.

Read:

- [references/shared/research-packet.md](references/shared/research-packet.md)
- [references/shared/reader-brief.md](references/shared/reader-brief.md)
- [references/shared/human-writing.md](references/shared/human-writing.md)

Default final copy must sound like a knowledgeable person explaining the
subject, not an AI describing its workflow. Do not expose internal terminology
unless the user explicitly requests a methods appendix or audit record.

### Validate the actual delivered artifact

Inspect the actual current text or document, not metadata that says it is good.
Derive a reverse outline from the artifact, check concept introduction,
referents, claim-support movement, paragraph handoffs, genre, citations, and
limitations. Keep deterministic diagnostics separate from reader-quality
judgment. A material edit makes affected audits stale.

For document files, keep content evidence and visual evidence separate. Text
extraction is not proof of correct rendering. If LibreOffice or another required
provider is unavailable, preserve `render_not_run` or
`dependency_unavailable`; do not say visual QA passed.

### Derive closure

Read [references/shared/closure.md](references/shared/closure.md). Final status
comes from current native receipts and exact fingerprints. Caller-authored
`pass`, `complete`, or `reader_native` fields are claims, not proof.

Use `scripts/propagate_staleness.py` when an input identity changes, then use
`scripts/derive_closure.py` on the resulting current receipt set. Staleness
crosses from operation to release, or back, only through an explicit dependency
edge. A changed user artifact therefore cannot invalidate release evidence by
implication, and a green release receipt cannot validate reader-facing prose.

Never strengthen these states into pass: `not_run`, `stale`,
`provider_unavailable`, `dependency_unavailable`, `access_gap`,
`render_not_run`, `bounded`, `partial`, `blocked`, or `failed`.

Only the selected final route may issue final closure. Child routes close only
their bounded request. Every non-pass result names the affected claim or unit,
safe wording, unsafe boundary, next owner, and required repair. Two identical
failed repair attempts without new evidence terminate visibly instead of
looping.

## Hard Gates

- Do not draft a final investigation from an incomplete ResearchPacket.
- Do not close an investigation without current SourceGuard source-observation
  evidence, a current LogicGuard argument model, and actual-artifact reader
  review.
- Do not close academic work without a current LogicGuard argument model,
  revision provenance, and actual-artifact reader review.
- Do not convert a missing provider, stale receipt, skipped check, partial
  search, failed rendering, or unsupported claim into success.
- Do not expose internal workflow vocabulary in ordinary final prose.
- Do not release or install a maintained copy unless the current SkillGuard
  authority and the frozen validation owners agree on the same source identity.

## Output Requirements

Return the requested reader-facing artifact first. When the work is not fully
closed, add a short, plain-language audit note containing these exact fields:

- `failures`: checks that ran and failed;
- `blockers`: missing authority, access, provider, evidence, or user choice;
- `skipped_checks`: checks that did not run, with the reason;
- `residual_risk`: uncertainty that remains after completed checks;
- `claim_boundary`: what the current evidence does and does not license.

Keep those fields out of normal prose when every required gate passes and the
user did not request an audit record. Never describe an output as complete when
one of the five fields contains a material unresolved item.

## SkillGuard Maintenance

The sole current maintenance authority is `.skillguard/contract-source.json`,
compiled into `.skillguard/compiled-contract.json` and the exact
`.skillguard/check-manifest.json`. Maintainers must compile and check that
authority, run its target-owned calibration fixture, and verify the installed
projection. Do not add a legacy contract reader, alternate manifest, fallback
launcher, compatibility alias, or second source of truth.
