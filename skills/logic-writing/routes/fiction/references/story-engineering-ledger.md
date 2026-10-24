# Story Engineering Ledger

Use this reference when a storyline-design task needs a durable story model before outline, draft, review, revision, or closure. The ledger is the source of truth for story-engineering decisions; prose is a downstream projection of current ledger state.

## Ledger Contract

Store the ledger as a machine-readable JSON object or equivalent structured table with these top-level fields:

```json
{
  "schema_version": "storyline-design.ledger.v1",
  "project_id": "short-id",
  "ledger_version": "1",
  "currentness": {
    "created_at": "ISO-8601",
    "updated_at": "ISO-8601",
    "source_revision": "user-input-or-artifact-id",
    "stale_after": []
  },
  "target_artifact": {},
  "premise": {},
  "theme": {},
  "protagonist": {},
  "opposition": {},
  "stakes": {},
  "structure": [],
  "scenes": [],
  "character_arcs": [],
  "promises": [],
  "worldguard_claims": [],
  "support": [],
  "composition_plan": "brief-request.json"
}
```

Every row that can block downstream work uses these common fields:

- `id`: stable row id, such as `scene-003` or `promise-main-question`.
- `kind`: row family, such as `scene`, `promise`, `worldguard_claim`, or `closure`.
- `status`: one of `planned`, `draft`, `pass`, `partial`, `blocked`, `gap`, `skipped`, `stale`, `deferred`, or `human-review`.
- `owner_stage`: workflow stage that owns the row.
- `depends_on`: row ids that must remain current.
- `evidence_refs`: current evidence paths, source ids, or validation result ids.
- `notes`: short human-readable rationale.

Do not use prose paragraphs as the only place where story state lives. If a decision affects structure, scene order, promise/payoff, world consistency, or closure, record it in the ledger first.

## Target Artifact

Purpose: define what the current run is allowed to produce.

Required fields:

- `artifact_type`: premise, outline, scene_card, chapter_plan, short_story, revision_plan, audit, or full_story.
- `reader_visibility`: reader_native, planning, audit, or mixed.
- `length_scope`: requested size or scope.
- `claim_boundary`: what the output may safely claim as complete.
- `prose_allowed`: true only when the ledger and closure state support prose at the requested scope.

Closure semantics:

- `pass` means the target artifact is clear enough for downstream work.
- `blocked` means the target is contradictory or underspecified.
- `human-review` means the user must choose scope, genre, protagonist, ending class, or another material direction.

## Premise

Purpose: store the story's central setup and dramatic question.

Required fields:

- `logline`: one-sentence story engine.
- `dramatic_question`: main unresolved question.
- `starting_state`: world and character state before disruption.
- `disruption`: event or pressure that starts movement.
- `success_condition`: what resolution would count as meaningful.
- `failure_condition`: what failure would cost.
- `source`: user input, generated assumption, adapted draft, or external support.

Closure semantics:

- A complete-story request cannot proceed to full outline or prose if the premise has no dramatic question or stakes link.
- Generated assumptions must remain visible until accepted or revised.

## Theme

Purpose: record the meaning contract without forcing moralizing prose.

Required fields:

- `theme_statement`: tentative thematic claim or question.
- `counterforce`: pressure that challenges the theme.
- `embodiment_rows`: scenes, arcs, or promises that carry the theme.
- `subtlety_policy`: explicit, implicit, ambiguous, or unresolved.

Closure semantics:

- Theme may be `partial` for early planning, but final closure should show how the theme is carried by structure, arc, or payoff rows.

## Protagonist

Purpose: bind the central agent to desire, pressure, change, and consequence.

Required fields:

- `name_or_role`: stable identifier.
- `external_goal`: visible objective.
- `internal_need`: change pressure or unresolved contradiction.
- `flaw_or_limit`: behavior that creates cost.
- `agency_rule`: how the protagonist makes meaningful choices.
- `arc_start`, `arc_turn`, `arc_end`: state movement through the story.
- `linked_scenes`: scene ids where the arc changes.

Closure semantics:

- A protagonist row is not closed if the character is only described by traits and has no agency, conflict, or arc movement.

## Opposition

Purpose: record the forces that make the protagonist's path non-trivial.

Required fields:

- `opposition_type`: antagonist, institution, environment, self, relationship, mystery, or norm.
- `pressure_method`: how opposition acts.
- `escalation_path`: how pressure grows.
- `world_constraints`: rules or resources that make opposition credible.
- `linked_claims`: WorldGuard claim ids when consistency checks are needed.

Closure semantics:

- Opposition is a gap if it is only a label and does not produce scene pressure, stakes, or causal constraints.

## Stakes

Purpose: track why outcomes matter and how cost escalates.

Required fields:

- `stake_id`: stable id.
- `stake_type`: physical, emotional, relational, social, moral, resource, mystery, or world-state.
- `at_risk`: what can be lost.
- `beneficiary_or_victim`: who experiences the consequence.
- `escalation_points`: structure or scene ids where stakes change.
- `payoff_link`: promise or closure row that resolves the stake.

Closure semantics:

- Stakes are not closed if they never change, never pressure a decision, or have no payoff path.

## Structure Rows

Use `planned_unit_id` into CompositionPlan.planned_units. Kind, parent, order,
children, reader job and downstream consumers belong only to that plan;
entry/exit story state lives in FictionComposition.unit_plans. Here retain the
turning-point role, moment, pressure change, arc/promise links, evidence and
repair facts. A unit without a real function, state movement or downstream
consequence still needs repair; authoring a pass field cannot close it.

## Scene Rows

A scene annotation uses `planned_unit_id` and retains irreversible change,
conflict pressure, character desire, obstacle, turning point, promise/world-claim
links, actual draft progress and repairs. Its parent, kind, contribution and
entry/exit state are read from the shared plan. Optional/background work keeps
an explicit treatment rather than being silently counted as realized.

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
