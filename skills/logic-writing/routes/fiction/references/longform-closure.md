# Longform Closure

Use this reference when Longform Mode needs to claim that a chapter, volume, book, or series is ready, partial, blocked, downgraded, or awaiting human review. Long-form closure aggregates short-form evidence and long-form-specific surfaces.

## Closure Levels

- `chapter`: one chapter and its immediate handoffs.
- `volume`: a group of chapters with a local arc or release unit.
- `book`: the whole book-level promise, arc, hierarchy, and continuity scope.
- `series`: multiple books and deferred series promises.

Passing a lower level does not pass a higher level.

## Closure Bundle Shape

```json
{
  "schema_version": "storyline-design.longform_closure.v1",
  "project_id": "novel-short-id",
  "closure_id": "closure-book-01",
  "closure_level": "book",
  "claim_boundary": "Book 1 outline and chapter interface plan are supported; final prose is not claimed.",
  "required_surfaces": [],
  "child_reports": [],
  "deferred_items": [],
  "blocking_items": [],
  "stale_items": [],
  "decision": "passed",
  "next_actions": []
}
```

Required fields:

- `schema_version`;
- `project_id`;
- `closure_id`;
- `closure_level`;
- `claim_boundary`;
- `required_surfaces`;
- `child_reports`;
- `deferred_items`;
- `blocking_items`;
- `stale_items`;
- `decision`;
- `next_actions`.

Allowed decisions: passed, partial, blocked, downgraded, or human_review.

## Required Surfaces

Every long-form closure level also carries universal Guard surfaces unless the claim boundary records a current reason:

- `flowguard_process`;
- `traceguard_storyline`;
- `worldguard_story_claims`;
- `logicguard_theme_support`;
- `sourceguard_canon_support`.

Use `not_applicable_with_reason` only when the reason is visible and does not hide a material story-world, theme, source, or process claim.

For chapter closure, require:

- novel ledger;
- story contribution;
- chapter interface;
- scene contracts when scenes are in scope;
- promise/payoff;
- voice/style report;
- reverse outline when prose exists;
- WorldGuard adapter evidence when world consistency matters.

For volume closure, also require:

- all in-scope chapter closure reports;
- volume arcs and volume promises;
- volume-level deferred item boundaries.

For book closure, also require:

- book hierarchy completeness;
- source requirement coverage when the claim answers a user-provided book request;
- final artifact path/hash and artifact-bound semantic review when final prose is claimed;
- key and major promises;
- major character and relationship arcs;
- continuity rows;
- stale evidence review;
- aggregate validation evidence.

For series closure, also require:

- book-level child reports;
- series-level promises and deferred items;
- continuity across books;
- explicit boundary for unresolved future-book material.

## Surface Status

Each `required_surfaces` item should include:

- `surface`: novel_ledger, story_contribution, chapter_interface, scene_contract, promise_payoff, worldguard, voice_style, reverse_outline, shortform_closure, or installed_parity;
- `status`: passed, partial, blocked, skipped, stale, unsupported, not_run, scoped_out, or human_review;
- `evidence_ref`;
- `blocks_closure`: true or false;
- `next_action`.

Closure fails or downgrades when a required surface is blocked, stale, unsupported, not_run, or human_review and no explicit boundary allows it.

For final-prose book or series closure, also include these surfaces:

- `source_requirements`: original user request, source brief, or accepted requirement matrix used to judge the manuscript.
- `final_artifact`: the actual manuscript artifact, with current file/path evidence and `sha256` or equivalent immutable content evidence.
- `artifact_bound_review`: the semantic StorylineDesign review that read the final artifact and cites the same `sha256` evidence as `final_artifact`.
- `model_prose_binding`: the structured evidence surface that maps important prose spans to model rows and key or major model rows back to prose evidence, with the same `sha256` evidence as `final_artifact`.

File hygiene, route completion, chapter count, binding claims without prose refs, or report text cannot replace `artifact_bound_review` or `model_prose_binding`. If the manuscript changes after review or binding, the affected evidence is stale until refreshed against the current artifact.

When final prose is claimed, `artifact_bound_review` must include reader-native manuscript review. The review reads the same final artifact as a normal reader and reports:

- reader-room contamination;
- author-facing chapter endings;
- explanation pressure;
- variation pressure;
- repeated chapter contribution;
- voice/style drift and weak character voice distinction;
- unsupported or premature payoff.
- weak or missing model-prose binding;
- unbound prose spans;
- unrealized key or major model rows;
- duplicate binding without changed reader state, resistance, cost, escalation, contrast, inversion, rhythm, or downstream use;
- resistance/friction gaps;
- reader-state simulation gaps;
- register ownership drift.

This is semantic review, not a genre-specific required schema. Do not require fixed profession, plot, clue, suspect, location, object, motif, romance, battle, or worldbuilding tables unless the user's story itself requires them. Repetition may pass when the review records its deliberate escalation, contrast, inversion, cost, rhythm, or changed reader interpretation.

## Child Reports

Child reports summarize lower-level closure:

- chapter reports under volume closure;
- volume or chapter reports under book closure;
- book reports under series closure.

Each child report must include `id`, `level`, `status`, `evidence_ref`, and `blocks_parent`.

Do not count a missing child report as pass.

## Native Validator Ownership

Native validator ownership stays with local structured evidence. `novel_ledger`, `story_contribution`, `chapter_interface`, `promise_payoff`, `voice_style`, and `reverse_outline` surfaces must be backed by their native validators or equivalent structured checks. Broad markdown reviews, prose summaries, or AI self-reports cannot substitute for local structured evidence. A reverse outline cannot pass as a novel ledger, chapter interface bundle, promise/payoff ledger, or voice/style report.

Book or series closure must preserve missing object, character_state, timeline, world_rule, or clue_state rows as blocking or downgraded gaps unless the claim boundary explicitly scopes them out.

## Gap Reporting

Use `blocking_items` for gaps that prevent the requested claim:

- unresolved key or major promises;
- orphan or duplicate major story units;
- missing chapter interface;
- missing reverse outline for drafted prose;
- missing source requirements for a final book request;
- missing final artifact path/hash when final prose is claimed;
- semantic review bound to a different or older final artifact hash;
- final prose semantic review missing reader-native manuscript review or variation review;
- final prose missing model-prose binding evidence bound to the current artifact hash;
- unresolved unbound prose, unrealized model row, duplicate binding, resistance/friction, reader-state simulation, or register ownership drift;
- unresolved reader-room contamination, explanation pressure, variation pressure, or same-author voice drift;
- unresolved voice/style drift;
- stale continuity evidence;
- non-pass WorldGuard claims that matter to story logic;
- skipped validators without accepted scope boundary.

Use `deferred_items` only when the closure level allows deferral and the claim boundary names where the item will be resolved.

## Minimal Longform Closure Checklist

Before claiming closure, answer:

1. What level is being closed?
2. Which surfaces are required for that level?
3. Which child reports are present and current?
4. Are key and major promises paid, fairly inverted, abandoned_with_reason, deferred with boundary, or human-reviewed?
5. Are chapter interfaces real and current?
6. Are reverse outlines present when prose exists?
7. Is voice/style continuity current?
8. Are continuity and WorldGuard gaps visible?
9. Are skipped, stale, blocked, unsupported, or human-review items preserved?
10. Is the final decision passed, partial, blocked, downgraded, or human_review with exact next actions?
