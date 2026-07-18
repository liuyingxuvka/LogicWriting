---
name: logic-writing
description: Use for deep source-backed investigation, academic writing, fiction planning or revision, and evidence-heavy travel guides. Routes each task to exactly one of four final owners, coordinates SourceGuard, LogicGuard, TraceGuard, WorldGuard, FlowGuard, Documents, and PDF without replacing them, and turns internal models into clear prose for real readers. Skip quick lookups, grammar-only edits, casual copy, and lightweight attraction lists.
---

# Logic Writing

## Purpose

Logic Writing has one entrypoint and four focused routes. It investigates hard
questions, builds defensible academic artifacts, plans and repairs fiction,
builds operational travel guides, and translates internal analysis into
language a reader can follow.

## Entrypoint Scope

This entrypoint owns routing, bounded handoffs, freshness, reader-facing
translation, and final closure. It does not take over a specialist's native
judgment or evidence authority.

## Use When

- Use for deep research, source-backed investigation, evidence synthesis, disputed claims, technical briefings, decision reports, and research reports.
- Use for academic papers, theses, dissertations, literature reviews, proposals, scholarly reports, and substantive academic revision.
- Use for fiction, story, short-story, chapter, novel, series, continuity, promise-payoff, manuscript planning, writing, auditing, or revision.
- Use for evidence-heavy travel guides, itineraries, destination guides, route plans, lodging strategy, weather or hazard planning, fallbacks, and traveler-fit recommendations.

## Do Not Use When

- Do not use for a quick factual lookup, grammar-only edit, casual low-stakes copy, or lightweight attraction list.
- Do not use when the final deliverable is owned entirely by one specialist and no investigation, academic, fiction, or travel writing artifact is required.

## Entrypoint Acceptance Map

Select exactly one final owner by the terminal deliverable, not by the first
action:

- Use `investigation` when the final product is a research report, briefing,
  evidence package, decision note, or answer to a contested question.
- Use `academic-writing` when the final product is a paper, thesis chapter,
  dissertation section, literature review, proposal, or substantive revision.
- Use `fiction-writing` when the final product is a story plan, short story,
  fiction chapter, novel, series bible, story audit, or substantive revision.
- Use `travel-guide` when the final product is an itinerary, destination guide,
  route plan, lodging strategy, or traveler-fit recommendation.
- Academic, fiction, and travel work may send a bounded evidence-gap request to
  investigation. The parent route remains the final owner.
- A travel paper is academic, a researched novel is fiction, and a story-shaped
  itinerary is travel. Subject and presentation technique do not transfer
  ownership.
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
- WorldGuard owns material event, agent, space, resource, access, capability,
  conflict, authority, and norm consistency in real and fictional worlds.
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

### Fiction writing

Read [references/routes/fiction-writing.md](references/routes/fiction-writing.md).
Choose compact, short-story, long-form, or final-manuscript depth from the
terminal artifact. Preserve story contribution, turning points, scene/chapter
interfaces, promises, continuity, voice, Guard handoffs, reader-state movement,
actual-manuscript identity, semantic review, and model-prose binding.

### Travel guide

Read [references/routes/travel-guide.md](references/routes/travel-guide.md).
Bind the traveler profile, time/weather mode, source roles, candidates,
WorldGuard feasibility, TraceGuard route mesh, lodging, fit, negative evidence,
reachable fallbacks, traveler-native projection, and reverse review of the
actual guide. Use the shared reader projection; never invoke the fiction route.

### Use the two-room writing boundary

Internal ledgers, Guard names, route ids, model ids, status fields, and agent
instructions belong in the work room. The prose writer receives a sanitized
ReaderBrief containing the reader question, genre, concepts, evidence,
alternatives, limitations, sequence, citations, and safe wording.

Read:

- [references/shared/research-packet.md](references/shared/research-packet.md)
- [references/shared/reader-brief.md](references/shared/reader-brief.md)
- [references/shared/human-writing.md](references/shared/human-writing.md)
- [references/shared/writing-contract.md](references/shared/writing-contract.md)

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
- Do not close fiction without current story-model, continuity, Guard lifecycle,
  shared-writing, actual-artifact semantic review, and model-prose binding
  evidence appropriate to the selected depth.
- Do not close travel without current source-time, feasibility, traveler-fit,
  fallback, shared-writing, final-artifact identity, and reverse-guide evidence.
- Do not let one sibling route call another or issue its closure.
- Do not convert a missing provider, stale receipt, skipped check, partial
  search, failed rendering, or unsupported claim into success.
- Do not expose internal workflow vocabulary in ordinary final prose.
- Do not release or install a maintained copy unless the frozen validation
  owners agree on the same source identity.

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
