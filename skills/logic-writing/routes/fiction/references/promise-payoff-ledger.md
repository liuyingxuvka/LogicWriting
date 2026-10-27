# Promise Payoff Ledger

Use this reference when a StorylineDesign task needs to track a story promise from setup through payoff, reversal, deferral, abandonment, or closure. Promise records are model-first ledger rows: each record defines what the story has made the reader expect, where the expectation came from, what kind of payoff is required, how that payoff is evidenced, and whether prose is allowed to claim closure. Run promise/payoff review before prose closure and before final revision claims.

## Boundary

StorylineDesign owns literary promise semantics:

- dramatic questions, mysteries, clues, threats, desires, emotional contracts, thematic setups, relationship expectations, stakes promises, and genre promises;
- setup, reminder, escalation, payoff, inversion, reversal, deferral, abandonment, and closure status;
- reader-native outline and prose projection.

WorldGuard owns generic world-claim validation when a promise depends on event order, causality, agent capability, access, resources, conflict, norms, authority, or evidence currentness. Do not add promise, clue, theme, chapter, scene, or payoff fields to WorldGuard core models.

A polished answer in prose does not close a promise by itself. Closure requires current ledger, scene-contract, structure-turning-points, WorldGuard, validation, and workflow gate evidence for the claim being made.

## Promise Record Shape

Record promises in the ledger `promises` section. Each promise must have a stable source, expectation, payoff target, status, and evidence path.

```json
{
  "id": "promise-map-race",
  "kind": "promise",
  "promise_type": "dramatic_question",
  "source_row_id": "scene-001",
  "source_row_kind": "scene",
  "introduced_by": [
    "scene-001",
    "turn-first-plot-point"
  ],
  "promise_text": "Who will reach the missing map first?",
  "reader_expectation": "The story will answer who controls the map and what that control costs.",
  "importance": "key",
  "expected_payoff": {
    "payoff_type": "answer_and_cost",
    "target_rows": [
      "scene-010",
      "turn-climax-001",
      "resolution-main"
    ],
    "minimum_evidence": [
      "scene_contract",
      "structure_turn",
      "worldguard_claim"
    ]
  },
  "current_payoff": {
    "status": "planned",
    "payoff_rows": [],
    "payoff_text": "",
    "payoff_evidence_refs": []
  },
  "inversion": {
    "allowed": true,
    "inversion_rule": "The answer may reveal that controlling the map is a trap if setup rows make the reversal legible.",
    "requires_setup_rows": [
      "scene-003",
      "promise-map-race"
    ],
    "status": "not_used"
  },
  "abandonment": {
    "allowed": false,
    "reason_required": true,
    "abandoned_with_reason": false,
    "reason": ""
  },
  "late_key_promise": {
    "is_late_key_promise": false,
    "guardrail_status": "not_applicable",
    "human_review_required": false
  },
  "links": {
    "structure_rows": [
      "turn-first-plot-point",
      "turn-climax-001"
    ],
    "scene_rows": [
      "scene-001",
      "scene-006",
      "scene-010"
    ],
    "worldguard_claim_rows": [
      "wg-claim-map-possession"
    ],
    "support_rows": [
      "support-map-rule"
    ]
  },
  "status": "open",
  "closure_effect": "blocks_full_closure_until_paid_or_deferred",
  "evidence_refs": []
}
```

Required fields:

- `id`: stable promise id.
- `kind`: `promise`.
- `promise_type`: dramatic_question, mystery, clue, threat, desire, emotional_contract, relationship, norm, thematic_setup, stakes, genre, or support.
- `source_row_id`: first ledger row that creates the expectation.
- `source_row_kind`: premise, structure, scene, character_arc, relationship_arc, support, or user_constraint.
- `introduced_by`: row ids that make the promise visible.
- `promise_text`: concise statement of the promise.
- `reader_expectation`: what the reader is led to expect.
- `importance`: key, major, supporting, optional, or background.
- `expected_payoff`: required payoff type, target rows, and minimum evidence.
- `current_payoff`: current payoff status, payoff rows, payoff text, and evidence refs.
- `status`: open, setup, escalated, payoff_planned, paid, inverted, abandoned_with_reason, deferred, partial, blocked, stale, unsupported, or human_review.
- `closure_effect`: continue, return_to_ledger, return_to_structure, return_to_scene, return_to_promises, return_to_worldguard, return_to_revision, user_decision, or scoped_out.
- `evidence_refs`: current validation, scene, structure, WorldGuard, review, or prose evidence.

Recommended fields:

- `inversion`: whether a reversal is allowed, required setup rows, and current inversion status.
- `abandonment`: reason requirements and decision source for abandoned promises.
- `late_key_promise`: guardrail state for important promises introduced late.
- `links`: structure rows, scene rows, WorldGuard claim rows, support rows, arc rows, and closure rows affected by the promise.

## Payoff Statuses

Use exact statuses so downstream checks can reason about promise closure.

- `open`: the promise exists but has no current payoff path.
- `setup`: the promise has setup evidence but no payoff target yet.
- `escalated`: later rows increase pressure, consequence, mystery, or emotional expectation.
- `payoff_planned`: payoff target rows exist but are not validated.
- `paid`: payoff rows answer, resolve, release, transform, or intentionally satisfy the expectation.
- `inverted`: payoff reverses the expected meaning while preserving reader legibility.
- `abandoned_with_reason`: the story intentionally drops the promise and records why that is acceptable.
- `deferred`: the promise remains open outside the current artifact boundary.
- `partial`: some expectation is paid but material residue remains.
- `blocked`: the promise prevents closure until repaired.
- `stale`: payoff evidence was invalidated by a later model, scene, structure, WorldGuard, or prose change.
- `unsupported`: a payoff is asserted without setup, evidence, or authority.
- `human_review`: a user or reviewer must choose whether to pay, invert, abandon, defer, or revise the promise.

Do not treat open, payoff_planned, partial, blocked, stale, unsupported, or human_review as closure. They narrow the claim boundary until resolved.

## Payoff Types

Declare the expected payoff type so review can judge the right evidence.

- `answer`: resolves a dramatic question or mystery.
- `emotional_release`: satisfies or breaks an emotional contract.
- `consequence`: shows cost, reward, punishment, or changed stakes.
- `reveal`: discloses withheld information.
- `choice`: forces a character decision that answers the promise.
- `reversal`: changes expected meaning without invalidating setup.
- `recognition`: makes the protagonist, reader, or another character understand the promise differently.
- `deferral`: intentionally moves payoff outside the current artifact boundary.
- `absence`: intentionally withholds payoff as part of the claimed story effect.
- `answer_and_cost`: resolves the question and shows consequence.

Payoff type is not prose decoration. It defines the evidence required before outline, draft, revision, or closure can claim the promise is handled.

## Inversion Rules

Use inversion when the story pays a promise by reversing or transforming the expected meaning.

Inversion is allowed only when:

- the original promise is explicit enough to be inspected;
- setup rows contain clues, pressure, irony, theme, contradiction, or world evidence that makes the reversal fair;
- the inversion row names what expectation is reversed;
- the payoff rows show a changed meaning, not a missing answer;
- affected scene, structure, promise, WorldGuard, and closure rows are refreshed.

Inversion is not allowed when:

- the promised answer is simply absent;
- the reversal depends on facts not present in ledger, support, scene, or WorldGuard rows;
- the inversion contradicts current world evidence without repair;
- the inversion changes the story's genre promise, ending class, theme, or protagonist arc without human_review.

Required inversion fields:

- `inversion_rule`: why reversal is fair.
- `requires_setup_rows`: setup evidence that licenses the inversion.
- `inverted_expectation`: what the reader expected.
- `actual_payoff`: what the story delivers instead.
- `affected_rows`: scenes, structure turns, promises, world claims, and closure rows that must be refreshed.
- `status`: not_used, planned, supported, unsupported, blocked, stale, or human_review.

Detailed checks continue in [promise-payoff-ledger-details](promise-payoff-ledger-details.md).

## Abandoned-With-Reason Handling

See [Abandoned-With-Reason Handling](promise-payoff-ledger-details.md#abandoned-with-reason-handling).

## Late Key Promise Guardrails

See [Late Key Promise Guardrails](promise-payoff-ledger-details.md#late-key-promise-guardrails).

## Link Checks

See [Link Checks](promise-payoff-ledger-details.md#link-checks).

## Minimal Promise Payoff Checklist

See [Minimal Promise Payoff Checklist](promise-payoff-ledger-details.md#minimal-promise-payoff-checklist).

## Longform Promise Handling

See [Longform Promise Handling](promise-payoff-ledger-details.md#longform-promise-handling).

## Payoff Support Binding

See [Payoff Support Binding](promise-payoff-ledger-details.md#payoff-support-binding).
