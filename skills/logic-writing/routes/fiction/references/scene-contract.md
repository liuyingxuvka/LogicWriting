# Scene Contract

Use this reference when a StorylineDesign task needs to plan, audit, draft, or revise a scene. A scene contract is a model-first record of why a scene exists, what it changes, what promises it touches, what world claims it depends on, and what outcome the workflow should assign before prose is treated as ready for closure.

## Boundary

StorylineDesign owns scene purpose, scene card fields, scene function, conflict, desire, obstacle, turn, promise/payoff role, reader-facing outline notes, prose status, and revision state.

WorldGuard may review generic world claims created by the scene, such as event order, causality, agent capability, location access, resource availability, conflict, norm, and authority. Do not move scene, chapter, beat, voice, pacing, theme, or prose-quality fields into WorldGuard core files.

A scene contract does not judge whether prose is beautiful. It checks whether the scene has a current story-engineering role and enough evidence for the next workflow gate.

## Scene Card Shape

Record scene cards in the ledger `scenes` section. A drafted prose scene may point to a scene card, but prose must not be the only place where scene state lives.

```json
{
  "owner_stage": "scenes",
  "turning_point_links": [
    "turn-midpoint-001"
  ],
  "irreversible_change": "The rival learns the protagonist is pursuing the map.",
  "conflict_pressure": "The protagonist needs the map, but entering the archive exposes them to the rival.",
  "character_desire": "Find the map without revealing the investigation.",
  "obstacle": "The archive door is locked and the rival has planted a false clue.",
  "turning_point": {
    "turn_type": "reveal",
    "turn_text": "The false clue shows the rival anticipated the investigation.",
    "pressure_change": "redirects"
  },
  "promise_links": [
    {
      "promise_id": "promise-map-race",
      "role": "escalation"
    }
  ],
  "arc_links": [
    "arc-protagonist-agency"
  ],
  "stakes_links": [
    "stake-map-control"
  ],
  "worldguard_claim_links": [
    "wg-claim-archive-access"
  ],
  "support_links": [
    "support-archive-layout"
  ],
  "prose_status": "not_started",
  "evidence_status": "planned",
  "contract_outcome": "revise",
  "outcome_reason": "WorldGuard access claim is not_run and midpoint handoff needs evidence.",
  "closure_effect": "return_to_worldguard",
  "evidence_refs": [],
  "planned_unit_id": "scene-006"
}
```

Required scene card fields:

- `planned_unit_id`: the existing scene unit in the canonical composition plan.
- `kind`: `scene`.
- `owner_stage`: `scenes`.
- `parent_structure_id`: owning act, part, sequence, chapter, or movement row.
- `turning_point_links`: structure-turning-points rows the scene prepares, contains, or resolves.
- `scene_contract`: one sentence explaining why the scene exists.
- Entry state is read from the fiction unit plan.
- Exit state is read from the fiction unit plan.
- `irreversible_change`: what cannot remain unchanged after the scene.
- `conflict_pressure`: visible pressure, contradiction, obstacle, or forced tradeoff.
- `character_desire`: what the focal character wants in the scene.
- `obstacle`: what blocks or complicates the desire.
- `turning_point`: decision, reveal, reversal, consequence, discovery, commitment, or refusal.
- `promise_links`: setup, reminder, escalation, payoff, reversal, or deferral rows touched by the scene.
- `worldguard_claim_links`: generic world-claim rows needed by the scene.
- `prose_status`: not_started, sample_only, drafted, revised, or final_candidate.
- `evidence_status`: planned, pass, partial, blocked, gap, skipped, stale, or human_review.
- `contract_outcome`: keep, revise, cut, or human_review.
- `closure_effect`: continue, return_to_ledger, return_to_structure, return_to_scene, return_to_promises, return_to_worldguard, return_to_revision, user_decision, or scoped_out.

Recommended fields:

- `arc_links`: protagonist, relationship, or theme arc rows affected by the scene.
- `stakes_links`: stakes rows escalated, resolved, delayed, or reversed by the scene.
- `support_links`: user-provided facts, source facts, generated assumptions, or continuity rules used by the scene.
- `outcome_reason`: concise rationale for keep, revise, cut, or human_review.
- `evidence_refs`: validation rows, WorldGuard evidence, review notes, or prose artifact refs.

## Outcome Vocabulary

Use one of four scene contract outcomes. Do not use a polished prose impression as a substitute for these checks.

### Keep

Use `keep` when the scene should remain in the current model.

Required evidence:

- `parent_structure_id` points to a current structure or turning-point row.
- `entry_state`, `exit_state`, and `irreversible_change` show real state movement.
- `conflict_pressure`, `character_desire`, and `obstacle` create scene-level pressure.
- `turning_point` changes knowledge, choice, resource state, relationship state, world state, or pressure.
- `promise_links`, `arc_links`, `stakes_links`, or `worldguard_claim_links` justify the scene's story function.
- Required WorldGuard claims are pass, scoped out, or safely narrowed.
- `prose_status` does not claim final readiness beyond the current closure boundary.

Gate effect:

- Set `closure_effect` to `continue` only when linked ledger, structure, promise, support, and WorldGuard rows are current enough for the next workflow stage.

### Revise

Use `revise` when the scene has a valid purpose but needs model or prose repair.

Common triggers:

- The scene has a useful structural role but weak entry or exit state.
- The character desire, obstacle, conflict pressure, or turn is vague.
- The scene touches a promise but does not record setup, escalation, payoff, reversal, or deferral.
- A WorldGuard claim is not_run, gap, stale, forbidden_use, boundary_exceeded, authority_cycle, missing_handoff, or fail.
- The prose introduces unsupported facts or skips a ledger obligation.
- The scene no longer matches its parent structure or turning-point role after revision.

Gate effect:

- Return to ledger when source rows, ownership, or evidence fields are missing.
- Return to structure when the parent structure or turning-point link is wrong.
- Return to scene when scene fields need repair.
- Return to promises when setup/payoff handling is unclear.
- Return to WorldGuard when generic world claims need checking or repair.
- Return to revision when prose must be updated after model repair.

### Cut

Use `cut` when the scene should not remain in the current story model.

Common triggers:

- The scene duplicates another scene's function without adding new state movement.
- The scene has no parent structure role.
- The scene does not affect promise, stake, arc, world claim, support, or closure rows.
- The scene weakens causality or contradicts current structure without adding an intentional branch.
- The scene only provides atmosphere that can be folded into another scene or marked as optional background.

Gate effect:

- Move the scene to `skipped`, `deferred`, or `scoped_out` in the ledger.
- Update parent structure rows, promise rows, arc rows, stakes rows, and WorldGuard claim links that depended on the scene.
- Preserve a validation note explaining why it was cut, so downstream reviewers do not count it as missing by accident.

### Human Review

Use `human_review` when the scene decision depends on a material creative choice that the skill cannot safely make.

Common triggers:

- The scene could be kept or cut depending on desired pacing, tone, point of view, audience, or ending class.
- The scene chooses between multiple viable protagonist actions or moral positions.
- The scene changes genre promise, theme, relationship meaning, ambiguity level, or final interpretation.
- WorldGuard or structure repair options are all viable but lead to materially different stories.

Gate effect:

- Record the specific decision needed.
- Keep `prose_status` and closure claim boundary narrowed until the user or reviewer decides.
- Do not convert `human_review` into keep, revise, or cut without recording the decision source.

Detailed checks continue in [scene-contract-details](scene-contract-details.md).

## Contract Checks

See [Contract Checks](scene-contract-details.md#contract-checks).

## Workflow Gate Links

See [Workflow Gate Links](scene-contract-details.md#workflow-gate-links).

## Minimal Scene Review Checklist

See [Minimal Scene Review Checklist](scene-contract-details.md#minimal-scene-review-checklist).

## Longform Scene Links

See [Longform Scene Links](scene-contract-details.md#longform-scene-links).
