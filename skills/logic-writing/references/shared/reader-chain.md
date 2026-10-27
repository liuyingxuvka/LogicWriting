# Reader chain details

The details of the 8-step reader chain that `SKILL.md` lists one line per step.

## Entrypoint scope

This entrypoint owns routing, bounded handoffs, freshness, reader-facing
translation, and final closure. It does not take over a specialist's native
judgment or evidence authority.

## Entrypoint acceptance map

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

## Local material routing

Read only the route, shared contract, schema, and adapter reference needed for
the selected work. Do not load both route playbooks by default. Local scripts
validate the reader records and calculate closure; installed
providers and ResearchGuard members retain their own domain work.

## Commands

Start from the worked example of your route in assets/examples/<route>/ (see its README).

Run reader-chain request wrappers from the skill root with Python 3.10 or newer.
Each reads a JSON file through `--input <file>`, prints its JSON result (or saves
it with `--output <file>`), and exits 0 when that result passes. Readback and
known-bad commands below default to readable text and offer `--json`; provider
preflight takes the provider name instead of a request.
A top-level field that holds an object may instead name a `.json` file
(relative to the request file), including a file an earlier step wrote with
`--output`. Scalar IDs, artifact paths and opaque native result locators stay
strings even when they end in `.json`. A relative `artifact_path` is read relative
to the file that contains it. Leave every script-derived `*_fingerprint` field out of the records you write:
the scripts compute each record's own fingerprint and copy the ones it must
share with other records in the same request; a value you do give is still
checked. Keep real source-byte identities such as revision
`source_artifact_fingerprint` where the entrypoint schema requires them;
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
   `route_composition`. Optionally set `research_folder` to the ResearchGuard folder or `research.yaml`; missing anchors are imported from its `models.source`. Matching handwritten dispositions stay unchanged; a different source id or locator fails `anchor_conflict:<id>`. With `research_status` (the saved `researchguard status --json` report of that folder), imported anchors take their relation from the research direction; a contradicting handwritten relation fails `anchor_relation_conflict:<id>`.
3. Write the artifact as UTF-8 text or Markdown from `ReaderBrief.writer_input`. For travel, attach one `trip_plan`; for long-form fiction, name its `longform_project`. Supply `world_contract` and `world_refs` when the route requires a WorldGuard check.
4. `python scripts/build_artifact_map.py --input map-request.json` with
   `artifact_path`, `map_id`, `language`, `artifact_format`.
5. `python scripts/validate_shared_writing.py --input shared-writing.json`
   with `contract`, `artifact_map`, `reader_brief`. Prefer `anchor_excerpts`
   (exact unique quotes, each at least 12 characters) over hand-written unit IDs.
6. `python scripts/audit_reader_output.py --input audit-request.json` with
   `audit_id`, `artifact_map`, `reader_brief`, `shared_writing`, `audited_at`.
7. `python routes/<route>/scripts/validate_<route>_artifact.py --input review.json`
   with `review`, `route_composition`, `artifact_map`, `reader_brief`,
   `shared_writing`; `<route>` is
   `investigation`, `academic`, `fiction`, or `travel`.
8. `python scripts/derive_closure.py --input closure-input.json` with
   `closure_id`, `route_decision`, `reader_brief`, `route_composition`,
   `artifact_map`, `shared_writing`, `deterministic_audit`, `route_review`,
   `judgment`, and `revision_provenance` for `revise_existing` with real source
   and treatments; `create_new` may omit provenance and use the default not-applicable record.

For a readback, `python scripts/show_plan.py --input reader-brief.json [--json]`
shows the plan tree even before drafting, with `UNBOUND` units. It also reads
the later chain JSON files beside `reader-brief.json`; available text bindings
must still resolve against the current artifact. For known-bad checks,
`python scripts/known_bad.py --input closure-input.json [--json] [--write-catalog <directory>]`
checks deterministic edits of a copy of the current text. It reports the first
check that catches each applicable defect without changing the original text.

Before a specialist
handoff, `python scripts/provider_preflight.py <provider>` checks that the
provider is installed; for ResearchGuard status and its three semantic members it uses the
ResearchGuard installed in the running Python, or else the `researchguard`
command on PATH. Specialists run through
their own commands, not through these scripts.

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

For LogicGuard artifact synthesis, map the current
`researchguard.logic.synthesis-plan.v1` through
`scripts/researchguard_handoff.py` and its
`assets/schemas/researchguard-logic-handoff.schema.json` contract before constructing the
ReaderBrief. This bridge carries the reader-selected unit order, argument
closure, source branch ids, and dispositions while retaining the native result
locator as an opaque reference. A blocked or stale native plan remains
blocked; the bridge never licenses prose quality or final closure.

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
the ArtifactMap and rerun the audit and the read. If a revision round fixes
none of the reported defects, stop and return the artifact with the audit note.
Repeated closure calls never count as repair attempts.

## Run an existing example or working folder

`python scripts/run_chain.py <folder>` runs native steps in process on existing text.
It writes the usual JSON results, prints the plan summary and first failure, and
stops there: exit 0 for a passing chain, 1 for a native rejection, 2 for unreadable
inputs or an unavailable refresh provider. `--until` accepts route, brief, map,
binding, audit, review or closure. The single-step commands remain available.
Map and audit request files are optional; the command uses piece.md and current
result files. The seven chain-file fields in closure-input.json may be omitted;
explicit fields retain their meaning and resolve beside that input file.
`--refresh-providers` refreshes researchguard status for research_folder and runs
the same verified portable WorldGuard launcher as provider_preflight for a
world_contract. Install ResearchGuard >= 0.5.16 and WorldGuard >= 0.7.23 beside
this skill before refreshing. Closure itself only reads saved native reports.
