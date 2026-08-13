---
name: logic-writing
description: Use for deep source-backed investigation, academic writing, fiction planning or revision, and evidence-heavy travel guides. Routes each task to exactly one of four final owners, coordinates the LogicGuard, SourceGuard, and TraceGuard members through the single ResearchGuard console plus WorldGuard, FlowGuard, Documents, and PDF without replacing them, and turns internal models into clear prose for real readers. Skip quick lookups, grammar-only edits, casual copy, and lightweight attraction lists.
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
providers and ResearchGuard members retain their own domain work.

## Required Workflow

### Freeze the current reader contract

Before route work, validate one `WritingRequest` and preserve its complete
`ReaderIntent`: language, audience, purpose, artifact mode and format,
requested or existing structure, headings, list/table policy, style, extent,
citations, required and forbidden content, reference examples, and unresolved
choices. Do not collapse these fields into a short topic summary. A material
conflict blocks drafting until it is resolved.

The selected final route owns one whole-artifact `CompositionPlan`. Plan the
opening, central throughline, conclusion, hierarchy, reader-state progression,
content and limitation placement, handoffs, list/table zones, and target
extent before drafting. A source finding is content authority, not a paragraph
plan. Never make one finding, claim, scene card, place, or checklist row equal
one paragraph by default.

### Preserve specialist ownership

This skill is an orchestration shell. It consumes provider-owned results and
receipts through an opaque, fingerprinted reference; it does not recreate their
domain decisions or manufacture a native receipt. ResearchGuard `0.4.11` is one
versioned suite and one executable console. Logic Writing activates exactly
three direct semantic owners:

- `researchguard source` / `primary:researchguard:source`: SourceGuard owns
  evidence-discovery planning and source-depth status.
- `researchguard logic` / `primary:researchguard:logic`: LogicGuard owns source
  preservation, argument support, structure, citation semantics, model depth,
  and synthesis plans. Its source-library, structured-artifact,
  model-deepening, artifact-synthesis, and project-library-viewer capabilities
  are internal routes, not separate installed skills.
- `researchguard trace` / `primary:researchguard:trace`: TraceGuard owns
  material temporal, causal, implementation, competing-story,
  counterfactual, and prediction-boundary analysis.
- ResearchGuard's `experiment` member and the umbrella `run` route are outside
  Logic Writing `3.0.2`. Requests for them are visible scope blocks and do not
  cause automatic multi-member execution.
- WorldGuard owns material event, agent, space, resource, access, capability,
  conflict, authority, and norm consistency in real and fictional worlds.
- FlowGuard owns process order, state, freshness, and closure behavior.
- Documents owns DOCX/Word/Google Docs mutation, tracked changes, comments,
  rendering, and page-level document QA.
- PDF owns PDF extraction, creation, rendering, and visual inspection.

Before every required adapter call, verify that its real provider is available.
For the three ResearchGuard owners, preflight the installed `researchguard`
console and the selected member command only. Never import an old member
package, invoke `python -m`, locate a sibling checkout, try another member, or
accept a provider-root override. Require distribution metadata and console
output to identify ResearchGuard `0.4.11`. If the one current path is
unavailable, mismatched, or times out, return the typed degraded state and stop
that handoff.

Validate the bounded handoff with `scripts/validate_adapter_request.py` before
the native call and `scripts/validate_adapter_result.py` after it. These
envelopes preserve the specialist's own route, receipt, scope, and failure
state; they do not re-run or reinterpret the specialist's native check.

Read [references/adapters/researchguard.md](references/adapters/researchguard.md)
before a ResearchGuard handoff, then load only the selected member adapter
reference under `references/adapters/`.

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
ReaderBrief containing the exact ReaderIntent, content boundaries, the whole
CompositionPlan, and only the selected route extension. Safe meanings,
evidence anchors, alternatives, limitations, and citations constrain content;
they are not sentence templates or permitted-wording scripts.

Read:

- [references/shared/research-packet.md](references/shared/research-packet.md)
- [references/shared/reader-brief.md](references/shared/reader-brief.md)
- [references/shared/human-writing.md](references/shared/human-writing.md)
- [references/shared/writing-contract.md](references/shared/writing-contract.md)

Draft the complete reader artifact as one integrated work. Default final copy
must sound like a knowledgeable person explaining the subject, not an AI
describing its workflow. Prose is the default for explanatory and narrative
body zones. Lists and tables belong only in ReaderIntent-authorized functional
zones. Do not repair a missing logical relation by adding canned transitions,
more headings, or more bullet cards.

### Validate the actual delivered artifact

Build an `ArtifactMap` from the exact current bytes, then bind every required
planned unit, content unit, model row, and route surface to real locators and
span fingerprints through `SharedWriting`. Inspect the actual current text or
document, not metadata that says it is good.

Run three distinct quality owners:

1. deterministic `ReaderAudit` for current bytes, locked structure, exact
   preservation, citations, list zones, fragmentation, placeholders, workflow
   leakage, and binding coverage;
2. the selected route's semantic review against actual spans;
3. an independent `ReaderJudgment`, with producer and judge identities
   separated, for reverse outline, clarity, coherence, naturalness, reader fit,
   genre fit, content fidelity, and instruction fidelity.

Self-scored quality, plan review, or a route saying its draft is good cannot
substitute for these checks. A material edit stales the ArtifactMap, bindings,
audits, judgment, and closure.

For document files, keep content evidence and visual evidence separate. Text
extraction is not proof of correct rendering. If LibreOffice or another required
provider is unavailable, preserve `render_not_run` or
`dependency_unavailable`; do not say visual QA passed.

### Derive closure

Read [references/shared/closure.md](references/shared/closure.md). Final status
comes from current native receipts and exact fingerprints. Caller-authored
`pass`, `complete`, or `reader_native` fields are claims, not proof.

Use `scripts/propagate_staleness.py` when an input identity changes, then use
`scripts/derive_closure.py` on the complete current v2 chain. Staleness
crosses from operation to release, or back, only through an explicit dependency
edge. A changed user artifact therefore cannot invalidate release evidence by
implication, and a green release receipt cannot validate reader-facing prose.

Never strengthen these states into pass: `not_run`, `stale`,
`provider_unavailable`, `dependency_unavailable`, `access_gap`,
`render_not_run`, `bounded`, `partial`, `blocked`, or `failed`.

Only the selected final route may issue final closure. Child routes close only
their bounded request. Every non-pass result creates a typed
`ReaderRepairRequest` naming actual target units, required structural change,
content to preserve, and forbidden shortcuts. After real new bytes exist,
record `ReaderRepairResult`, rebuild all byte-bound evidence, and rerun the
three quality owners. Two consecutive current repair results with the same
defect lineage, same remaining defect set, and no byte-level progress terminate
visibly; repeated closure calls never count as repair attempts.

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
- Do not route LogicGuard, SourceGuard, or TraceGuard through any executable
  other than the single `researchguard` console.
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
