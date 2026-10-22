---
name: logic-writing
description: "Use for a finished piece for real readers: a source-backed investigation report, an academic paper or revision, fiction or a story plan, or an evidence-heavy travel guide. Not for checking claims, sources or causal timelines on their own; use researchguard."
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
validate the reader records and calculate closure; installed
providers and ResearchGuard members retain their own domain work.

## Commands

Run each script from the skill root with Python 3.10 or newer. Every script
reads one JSON file given as `--input <file>`, prints its JSON result (or
writes it to `--output <file>`), and exits 0 only when the result passes.
A top-level field that holds an object may instead name a `.json` file
(relative to the request file), including a file an earlier step wrote with
`--output`. Scalar IDs, artifact paths and opaque native result locators stay
strings even when they end in `.json`. A relative `artifact_path` is read relative
to the file that contains it. Leave every script-derived `*_fingerprint` field out of the records you write:
the scripts compute each record's own fingerprint and copy the ones it must
share with other records in the same request; a value you do give is still
checked. Keep external byte identities such as `observed_content_fingerprint`
and revision `source_artifact_fingerprint` as required by each entrypoint schema;
these identify actual source bytes. Field shapes are in `assets/schemas/`.
A failed result file without the requested record reports its first error; fix
that step before continuing. A vanished artifact unit is named before any
fingerprints are filled. Correct the binding or evidence against the current
ArtifactMap; the scripts never guess a replacement unit.

1. `python scripts/select_route.py --input route-request.json` with
   `writing_request`, `decision_id`, `decided_at`; returns the RouteDecision.
2. `python scripts/build_reader_brief.py --input brief-request.json` with
   `route_decision`, `content_boundaries`, `composition_plan`,
   `route_composition`, `brief_id` (add `native_plan`, `native_result_locator`
   and `native_handoff_mapping` only when a ResearchGuard synthesis plan is
   used). Later steps can name this result file for `reader_brief` and
   `route_composition`.
3. Write the artifact as UTF-8 text or Markdown.
4. `python scripts/build_artifact_map.py --input map-request.json` with
   `artifact_path`, `map_id`, `language`, `artifact_format`.
5. `python scripts/validate_shared_writing.py --input shared-writing.json`
   with `contract`, `artifact_map`, `reader_brief`.
6. `python scripts/audit_reader_output.py --input audit-request.json` with
   `audit_id`, `artifact_map`, `reader_brief`, `shared_writing`, `audited_at`.
7. `python routes/<route>/scripts/validate_<route>_artifact.py --input review.json`
   with `review`, `route_composition`, `artifact_map`; `<route>` is
   `investigation`, `academic`, `fiction`, or `travel`.
8. `python scripts/derive_closure.py --input closure-input.json` with
   `closure_id`, `route_decision`, `reader_brief`, `route_composition`,
   `artifact_map`, `shared_writing`, `deterministic_audit`, `route_review`,
   `judgment`, `revision_provenance`.

Before a specialist
handoff, `python scripts/provider_preflight.py <provider>` checks that the
provider is installed; for the three ResearchGuard members it uses the
ResearchGuard installed in the running Python, or else the `researchguard`
command on PATH. Specialists run through
their own commands, not through these scripts.

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

This skill is an orchestration shell. It consumes provider-owned results as
they are; it does not recreate their domain decisions or write a result on a
provider's behalf. ResearchGuard is one suite
with one executable console; `scripts/provider_preflight.py` checks its
minimum version. Logic Writing activates exactly
three direct semantic owners:

- `researchguard source` / `primary:researchguard:source`: SourceGuard owns
  evidence-discovery planning and source-depth status.
- `researchguard logic` / `primary:researchguard:logic`: LogicGuard owns source
  preservation, argument support, structure, citation semantics, model depth,
  and synthesis plans. Its source-library, structured-artifact,
  model-deepening, artifact-synthesis, and project-library-viewer capabilities
  are internal routes, not separate installed skills.
- How to run each member is in the one `researchguard` skill: its `source`,
  `logic` and `trace` routes.
- `researchguard trace` / `primary:researchguard:trace`: TraceGuard owns
  material temporal, causal, implementation, competing-story,
  counterfactual, and prediction-boundary analysis.
- ResearchGuard's `experiment` member and the umbrella `run` route are outside
  Logic Writing. Requests for them are visible scope blocks and do not
  cause automatic multi-member execution.
- WorldGuard owns material event, agent, space, resource, access, capability,
  conflict, authority, and norm consistency in real and fictional worlds.
- Documents owns DOCX/Word/Google Docs mutation, tracked changes, comments,
  rendering, and page-level document QA.
- PDF owns PDF extraction, creation, rendering, and visual inspection.

Before every required adapter call, verify that its real provider is available.
For the three ResearchGuard owners, preflight the installed `researchguard`
console and the selected member command only. Never import an old member
package, invoke `python -m`, locate a sibling checkout, try another member, or
accept a provider-root override. If the console is missing, older than the
minimum version, or times out, report that status and stop that handoff.

For LogicGuard artifact synthesis, map the current
`researchguard.logic.synthesis-plan.v1` through
`scripts/researchguard_handoff.py` and its
`assets/schemas/researchguard-logic-handoff.schema.json` contract before constructing the
ReaderBrief. This bridge carries the reader-selected unit order, argument
closure, source branch ids, and dispositions while retaining the native result
locator as an opaque reference. A blocked or stale native plan remains
blocked; the bridge never licenses prose quality or final closure.

Read [references/adapters/researchguard.md](references/adapters/researchguard.md)
before a ResearchGuard handoff, then load only the selected member adapter
reference under `references/adapters/`.

### Run the selected route

### Investigation

Read [references/routes/investigation.md](references/routes/investigation.md).
Begin with the claim, decision, scope, source roles, and stopping rule. Preserve
concrete sources through LogicGuard's source library before deeper synthesis.
Use SourceGuard to plan discovery, and invoke TraceGuard only when the claim
actually depends on a trace. Build the claim-and-evidence ledger before prose;
its rows become the content boundaries.

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
interfaces, promises, continuity, voice, reader-state movement,
actual-manuscript identity, semantic review, and model-prose binding.
Provide POV and tense in the optional `voice_contract`; the writer receives that
object, while an unfilled voice reference remains a gap.

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

The v2 automatic reader closure supports UTF-8 `text` and `markdown`. All seven
requested-format routes remain available. DOCX/PDF creation, revision, extraction,
rendering, and visual inspection stay with Documents/PDF. A text projection can
close only its own text layer; it does not bind the original binary or rendering
identity and cannot license a whole-document broad pass. Keep unresolved binary
or render dependencies explicitly bounded, `partial`, `render_not_run`, or
`dependency_unavailable` as applicable.

Build an `ArtifactMap` from the exact current text/markdown bytes, then bind every required
planned unit, content unit, model row, and route surface to real locators and
span fingerprints through `SharedWriting`. Inspect the actual current text or
document, not metadata that says it is good.

Preserve three quality responsibilities:

1. deterministic `ReaderAudit` for current bytes, locked structure, exact
   preservation, citations, list zones, fragmentation, placeholders, workflow
   leakage, and binding coverage;
2. the selected route's semantic review against actual spans;
3. a `ReaderJudgment` with an explicit `judge_kind`, preferably from an
   independent context, for reverse outline, clarity, coherence, naturalness, reader fit,
   genre fit, content fidelity, and instruction fidelity.

After the deterministic audit, have a reader that did not write the text read
the actual file, preferably a fresh sub-agent or a separate session. That one
read may cover both the selected route's review dimensions and the eight reader
dimensions; it quotes the actual spans it relies on. Record its result as the
route review and the `ReaderJudgment`. For `"judge_kind": "independent_context"`,
keep `producer_id` and `judge_id` different. If no separate context is available,
self-review is allowed: write `"judge_kind": "self_review"` in the judgment.
Closure records that kind, preserves an explicit self-review risk, and never
allows a broad claim from self-review, even when quality passes. A plan review, a score, or a route
saying its own draft is good cannot replace reading the actual text. A material
edit stales the ArtifactMap, bindings, audits, judgment, and closure.

For document files, keep content evidence and visual evidence separate. Text
extraction is not proof of correct rendering. If LibreOffice or another required
provider is unavailable, preserve `render_not_run` or
`dependency_unavailable`; do not say visual QA passed.

### Derive closure

Read [references/shared/closure.md](references/shared/closure.md). Final status
comes from the current actual-text checks and exact fingerprints. Caller-authored
`pass`, `complete`, or `reader_native` fields are claims, not proof.

Run `scripts/derive_closure.py` on the complete current v2 chain. It re-reads
the current artifact bytes, so an edit made after review makes closure fail
instead of passing.

Never strengthen these states into pass: `not_run`, `stale`,
`provider_unavailable`, `dependency_unavailable`, `access_gap`,
`render_not_run`, `bounded`, `partial`, `blocked`, or `failed`.

Only the selected final route may issue final closure. Child routes close only
their bounded request. Closure status is `passed` or `needs_repair`. If the
audit or the reader judgment reports defects, revise the actual text, rebuild
the ArtifactMap and rerun the audit and the read. If a revision round fixes
none of the reported defects, stop and return the artifact with the audit note.
Repeated closure calls never count as repair attempts.

## Hard Gates

- Do not write a confident final answer while a critical claim has no usable
  support; bound it or report it.
- Do not close an investigation without current SourceGuard source-observation
  evidence, a current LogicGuard argument model, and actual-artifact reader
  review.
- Do not close academic work without a current LogicGuard argument model,
  revision provenance, and actual-artifact reader review.
- Do not close fiction without current story-model, continuity,
  shared-writing, actual-artifact semantic review, and model-prose binding
  evidence appropriate to the selected depth.
- Do not close travel without current source-time, feasibility, traveler-fit,
  fallback, shared-writing, final-artifact identity, and reverse-guide evidence.
- Do not let one sibling route call another or issue its closure.
- Do not route LogicGuard, SourceGuard, or TraceGuard through any executable
  other than the single `researchguard` console.
- Do not convert a missing provider, stale result, skipped check, partial
  search, failed rendering, or unsupported claim into success.
- Do not expose internal workflow vocabulary in ordinary final prose.

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
