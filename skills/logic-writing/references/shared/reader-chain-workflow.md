# Reader Chain Workflow

## Required workflow

### Freeze the current reader contract

Before route work, validate one `WritingRequest` and preserve its complete
`ReaderIntent`: language, audience, purpose, artifact mode and format,
requested or existing structure, headings, list/table policy, style, extent,
citations, required and forbidden content, reference examples, and unresolved
choices. Do not collapse these fields into a short topic summary. A material
conflict blocks drafting until it is resolved. A material unresolved choice
returns `needs_user_choice`: ask the first question, record the user's answer
in ReaderIntent, and route again before planning.

The selected final route owns one whole-artifact `CompositionPlan`. Plan the
opening, central throughline, conclusion, hierarchy, reader-state progression,
content and limitation placement, handoffs, list/table zones, and planned
extent before drafting. A source finding is content authority, not a paragraph
plan. Never make one finding, claim, scene card, place, or checklist row equal
one paragraph by default.

### Preserve specialist ownership

This skill is an orchestration shell. It consumes provider-owned results as
they are; it does not recreate their domain decisions or write a result on a
provider's behalf. ResearchGuard is one suite
with one executable console; `scripts/provider_preflight.py` checks its
minimum version. `researchguard status` / `primary:researchguard:status` reads one research question and supplies the saved five-key `verdict`; the three direct semantic owners remain:

- `researchguard source` / `primary:researchguard:source`: SourceGuard owns
  evidence-discovery planning and source-depth status.
- `researchguard logic` / `primary:researchguard:logic`: LogicGuard owns source
  preservation, argument support, structure, citation semantics, model depth,
  and argument-ordered unit plans (`synthesize`). Its source-library, structured-artifact,
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
For ResearchGuard status or a semantic member, preflight the installed `researchguard`
console and the selected member command only. Never import an old member
package, invoke `python -m`, locate a sibling checkout, try another member, or
accept a provider-root override. If the console is missing, older than the
minimum version, or times out, report that status and stop that handoff.

Read [references/adapters/researchguard.md](../adapters/researchguard.md)
before a ResearchGuard handoff. It is the single adapter for the question and all three semantic members; save `researchguard status <folder> --json --output research-status.json` as the one research provider report for closure.

The four route sections are in the route references: [investigation](../routes/investigation.md),
[academic writing](../routes/academic-writing.md), [fiction writing](../routes/fiction-writing.md)
and [travel guide](../routes/travel-guide.md).

### Use the two-room writing boundary

Internal ledgers, Guard names, route ids, model ids, status fields, and agent
instructions belong in the work room. The prose writer receives only the sanitized
`ReaderBrief.writer_input` projection containing the exact ReaderIntent, content boundaries, the whole
CompositionPlan, and only the selected route extension. Safe meanings,
evidence anchors, alternatives, limitations, and citations constrain content;
they are not sentence templates or permitted-wording scripts.

Read:

- [references/shared/reader-brief.md](reader-brief.md)
- [references/shared/human-writing.md](human-writing.md)
- [references/shared/writing-contract.md](writing-contract.md)

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
   leakage, claim patterns, and declared bindings;
2. the selected route's semantic review against actual spans; each limitation
   and prohibited overclaim needs a conclusion with actual quotations. Bindings
   are the author's declarations; review quotations check their correctness;
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

Read [references/shared/closure.md](closure.md). Final status
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
the ArtifactMap and rerun the audit and the read. If a revision round resolves
none of the actual defects, stop and return the artifact with the audit note.
Repeated closure calls never count as repair attempts.

## Brief omissions and revisions

Brief requests may omit repeated body dispositions and shared fiction unit fields already present in planned units. The builder fills them before fingerprints; explicit values and deliberate omissions still require validation.

For revisions, `scripts/build_source_unit_manifest.py` lists real source units
before treatments; `scripts/validate_revision_provenance.py` checks them against
the revised current text. Closure performs the same required revision check.
`create_new` may omit provenance and receives the explicit not-applicable default;
this does not relax revision source-byte or treatment requirements.
