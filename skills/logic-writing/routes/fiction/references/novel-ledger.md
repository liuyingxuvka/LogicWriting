# Novel Ledger

Use this reference when Longform Mode needs a durable model for a novel, book, volume, chapter batch, or series. The novel ledger is the source of truth for hierarchy, arcs, threads, promises, continuity, draft state, validation, and closure levels.

## Ledger Shape

Store the ledger as JSON or an equivalent structured table:

```json
{
  "schema_version": "storyline-design.novel_ledger.v1",
  "project_id": "novel-short-id",
  "target_artifact": {},
  "longform_scope": {},
  "hierarchy": {
    "books": [],
    "volumes": [],
    "chapters": [],
    "scenes": []
  },
  "story_units": [],
  "arcs": [],
  "threads": [],
  "promises": [],
  "continuity": [],
  "chapter_interfaces": [],
  "draft_state": {},
  "validation": [],
  "closure": {}
}
```

## Layer Ownership Map

The novel ledger is the root index for the layered model mesh. It should point to child evidence instead of replacing it.

- Hierarchy rows own book, volume, chapter, and scene containment.
- Story unit rows own parent contribution and downstream use.
- Promise rows own setup, payoff, inversion, abandonment, or deferral.
- `continuity` rows own character_state, relationship_state, timeline, place, object, resource, world_rule, clue_state, POV, voice, style, and canon facts.
- Chapter interface rows own adjacent handoff and reader-state movement.
- Reverse outline rows own actual drafted events and reader-state evidence.

## Target Artifact

Required fields:

- `artifact_type`: novel, series_plan, book_plan, volume_plan, chapter_batch, chapter_draft, revision_plan, or audit.
- `closure_level`: chapter, volume, book, series, or none.
- `reader_visibility`: planning, audit, reader_native, or mixed.
- `claim_boundary`: what may be claimed complete.
- `prose_allowed`: true only when the requested prose scope is supported by current model evidence.

## Longform Scope

Required fields:

- `series_id`, `book_id`, `volume_ids`, and `chapter_ids` in scope;
- `word_count_target` or `length_scope`;
- `genre_promise`;
- `pov_policy`;
- `continuity_policy`;
- `deferred_scope`: items intentionally outside current closure.

## Hierarchy Rows

Every row uses `id`, `kind`, `title`, `parent_id`, `order`, `status`, `summary`, `entry_state`, `exit_state`, `depends_on`, and `evidence_refs`.

Additional requirements:

- books list owned volume or chapter ids;
- volumes list chapter ids;
- chapters list scene ids and chapter interface ids;
- scenes link to scene contracts when scene-level checks are needed.

Allowed statuses: `planned`, `draft`, `pass`, `partial`, `blocked`, `gap`, `skipped`, `stale`, `deferred`, `scoped_out`, or `human_review`.

## Story Units

Story units are the inspectable contribution rows used by `story_contribution_check.py`.

Required fields:

- `id`, `kind`, `parent_id`, `importance`, `status`;
- `contribution`: what the unit changes in the parent;
- `downstream_use`: later units, promises, arcs, or continuity rows that depend on it;
- `terminal_treatment`: keep, revise, cut, merge, defer, scoped_out, or human_review;
- `repair_action`: required when status is orphan, duplicate, weak, unsupported, stale, blocked, or human_review.

## Arcs And Threads

Arc rows track movement:

- `id`, `arc_type`, `owner`, `scope`, `start_state`, `turning_points`, `end_state`, `linked_chapters`, `status`.

Thread rows track serial continuity:

- `id`, `thread_type`, `introduced_by`, `active_in`, `resolved_by`, `deferred_to`, `importance`, `status`.

Key or major arcs and threads cannot be open without payoff, deferral boundary, or human-review decision at book closure.

## Promises

Long-form promise rows extend the normal promise/payoff ledger.

Required fields:

- `id`, `importance`, `promise_type`, `introduced_by`, `expected_payoff`, `status`, `payoff_rows`, `deferral_level`, `claim_boundary`, and `evidence_refs`.

Additional long-form statuses:

- `volume_deferred`: open outside the current chapter but inside the current volume.
- `book_deferred`: open outside the current volume but inside the current book.
- `series_deferred`: open outside the current book and inside the series.

At book closure, key promises must be paid, inverted with setup, abandoned_with_reason, human_review, or explicitly series_deferred with boundary. Major promises may be book_deferred only if the requested closure level is lower than book closure.

## Continuity

Continuity rows track facts the reader expects to remain stable.

Required fields:

- `id`, `continuity_type`, `fact`, `scope`, `first_seen`, `last_checked`, `affected_units`, `status`, `repair_action`, and `evidence_refs`.

Continuity types include character_state, relationship_state, timeline, place, object, resource, world_rule, clue_state, POV, voice, style, and canon.

## Draft State

Required fields:

- `chapters_planned`, `chapters_drafted`, `chapters_reverse_outlined`;
- `current_revision_round`;
- `prose_claim_boundary`;
- `latest_draft_refs`;
- `stale_after`.

Draft state does not close a chapter by itself. It tells closure which prose evidence exists and whether reverse outline checks are current.

When a final manuscript is claimed, draft state or validation rows must also
name the current final artifact reference and content hash in their evidence
path. A manuscript edit after source-requirement review, reverse outlining,
promise/payoff review, voice/style review, or final semantic review stales the
affected evidence until it is rerun or explicitly scoped out.

## Validation And Closure

Validation rows record deterministic or manual checks:

- `id`, `check_name`, `surface`, `checked_ids`, `status`, `evidence_ref`, `rerun_required_when`.

Closure object required fields:

- `closure_level`, `decision`, `claim_boundary`, `blocking_rows`, `deferred_rows`, `stale_rows`, `latest_validation_refs`, `prose_allowed`.

Book or series closure cannot pass while key hierarchy, story contribution, chapter interface, source requirements, final artifact binding, artifact-bound semantic review, promise/payoff, continuity, voice/style, reverse-outline, or aggregate closure checks are missing, blocked, stale, unsupported, or hidden. Model-only book closure may pass only when the claim boundary explicitly states that final prose is not claimed.
