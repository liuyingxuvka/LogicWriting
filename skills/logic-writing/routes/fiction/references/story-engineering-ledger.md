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

Detailed checks continue in [story-engineering-ledger-details](story-engineering-ledger-details.md).

## Promise And Payoff Rows

See [Promise And Payoff Rows](story-engineering-ledger-details.md#promise-and-payoff-rows).

## WorldGuard Claim Rows

See [WorldGuard Claim Rows](story-engineering-ledger-details.md#worldguard-claim-rows).

## Support Rows

See [Support Rows](story-engineering-ledger-details.md#support-rows).

## Computed checks

See [Computed checks](story-engineering-ledger-details.md#computed-checks).

## Closure

See [Closure](story-engineering-ledger-details.md#closure).

## Planning, Drafting, Review, Revision, And Closure Use

See [Planning, Drafting, Review, Revision, And Closure Use](story-engineering-ledger-details.md#planning-drafting-review-revision-and-closure-use).

## Minimal Ledger Readiness Checklist

See [Minimal Ledger Readiness Checklist](story-engineering-ledger-details.md#minimal-ledger-readiness-checklist).

## Longform Optional Blocks

See [Longform Optional Blocks](story-engineering-ledger-details.md#longform-optional-blocks).
