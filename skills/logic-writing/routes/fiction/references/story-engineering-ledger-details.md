# Story Engineering Ledger — detailed checks

## Promise And Payoff Rows

Purpose: preserve every material setup, question, mystery, emotional contract, clue, and payoff.

Each promise row should include:

- `id`: stable promise id.
- `promise_type`: dramatic_question, mystery, emotional_contract, clue, threat, desire, norm, or thematic_setup.
- `introduced_by`: scene, structure, premise, or user constraint id.
- `expected_payoff`: what kind of answer or emotional release is implied.
- `payoff_rows`: scene or structure ids that fulfill it.
- `status`: open, partial, pass, deferred, reversed, unsupported, or blocked.
- `deferral_reason`: required when intentionally left unresolved.

Closure semantics:

- A promise without payoff or deferral blocks full closure.
- A payoff without mapped setup is unsupported unless it is intentionally classified as surprise, reversal, or late reveal and has support.

## WorldGuard Claim Rows

Purpose: record generic world consistency checks without putting literary fields into WorldGuard core.

Each claim row should include:

- `id`: stable claim id.
- `source_row_id`: scene, structure, premise, support, or promise row that created the claim.
- `claim_type`: event, agent, space, resource, causal, conflict, norm, timeline, or authority.
- `claim_text`: generic world claim in non-literary terms.
- `authority_scope`: user_canon, draft_current, generated_assumption, external_source, or unknown.
- `worldguard_report`: native WorldGuard check summary path, relative to the ledger. Read its top-level status (PASS, FAIL, GAP or BOUNDARY_EXCEEDED) in lower case. No report means not_run and never passes. Legacy worldguard_status: not_run is accepted; other handwritten statuses require a report and must match it.
- `worldguard_evidence_refs`: downstream evidence ids or paths.
- `adapter_note`: why this mapping belongs in the adapter layer.

Closure semantics:

- Non-pass WorldGuard status must narrow the story claim boundary or send the workflow back to the earliest affected ledger row.
- Do not add WorldGuard core fields for chapter, scene, theme, arc, voice, style, or prose quality.

## Support Rows

Purpose: distinguish user-provided facts from generated assumptions and external sources.

Each support row should include:

- `id`: stable support id.
- `support_type`: user_constraint, premise_support, source_material, generated_assumption, continuity_rule, or human_note.
- `content_summary`: concise statement of the support.
- `scope`: which rows it supports.
- `authority`: user, source, generated, inferred, or unknown.
- `currentness`: current, stale, superseded, or disputed.
- `required_before_prose`: true when prose would overclaim without this support.

Closure semantics:

- Generated assumptions cannot silently become user constraints.
- Stale or disputed support must be visible to review and closure.

## Computed checks

Do not author validation status rows. Run current domain validators and the
standard eight-step reader chain. Each computed result keeps the native owner,
issue codes and real evidence boundary. Missing or not-run specialist work does
not become a pass through prose or a copied report.

## Closure

Do not author a closure object. `derive_closure.py` computes final closure from
current reader-chain results; long form also directly validates the project
mesh. Preserve unresolved domain facts, scoped deferrals, stale sources, repairs
and human-review boundaries. Domain open/paid/active/resolved states remain.

## Planning, Drafting, Review, Revision, And Closure Use

- Planning reads and updates target, premise, theme, protagonist, opposition, stakes, structure, scene, promise, support, and WorldGuard rows.
- Drafting and drafting checks read the ledger and write prose only inside the allowed claim boundary.
- Review checks whether story-facing output matches ledger rows and whether any gap was hidden by prose.
- Revision updates the ledger first, then refreshes affected outline, draft, validation, and closure rows.
- Closure aggregates ledger and validation state; it does not infer completion from polished prose.

## Minimal Ledger Readiness Checklist

Before complete-story prose, confirm:

1. Target artifact is clear and `prose_allowed` can become true.
2. Premise has dramatic question, starting state, disruption, success condition, and failure condition.
3. Theme is linked to structure, arc, or payoff rows.
4. Protagonist has desire, obstacle, agency, and arc movement.
5. Opposition creates credible pressure and escalation.
6. Stakes change and have payoff links.
7. Structure rows have function, entry state, exit state, and child scene links.
8. Important scenes have scene contracts and irreversible changes.
9. Promises have payoffs, deferrals, reversals, or blocker rows.
10. WorldGuard claims preserve non-pass and stale statuses.
11. Support rows separate user facts, source facts, generated assumptions, and unresolved gaps.
12. Validation rows are current.
13. Closure records pass, partial, blocked, or human-review with explicit boundary.

## Longform Optional Blocks

For novel, series_plan, book_plan, volume_plan, chapter_batch, chapter_draft, revision_plan, or audit artifacts, add the long-form blocks from `novel-ledger.md` instead of overloading short-story fields.

Extend `target_artifact.artifact_type` to include:

- novel;
- series_plan;
- book_plan;
- volume_plan;
- chapter_batch;
- chapter_draft;
- longform_revision_plan;
- longform_audit.

Recommended optional top-level fields:

- `longform_scope`: target book, volume, chapter ids, genre promise, POV policy, deferred scope, and claim boundary.
- `composition_plan`: the shared brief request owning the unit tree.
- `story_units`: contribution rows consumed by story contribution checks.
- `chapter_interfaces`: adjacent chapter handoffs and reader-state movement.
- `voice_style`: voice contract and continuity report refs.
- `reverse_outlines`: evidence extracted from actual prose.
- project mesh: current source surfaces for computed long-form checks.

Short-story validators must continue to accept ledgers that do not include these optional long-form blocks. Longform validators must not infer pass from missing optional blocks when the artifact type is long-form.
