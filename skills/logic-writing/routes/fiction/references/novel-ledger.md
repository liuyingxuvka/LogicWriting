# Novel Ledger

Use this reference when Longform Mode needs a durable model for a novel, book, volume, chapter batch, or series. The composition plan owns the unit tree; the novel ledger owns arcs, threads, promises, continuity and draft progress.

## Unit ownership

Set `composition_plan` to the canonical brief request relative to this file.
CompositionPlan.planned_units owns book/volume/chapter/scene identity, hierarchy,
order and reader job; FictionComposition.unit_plans owns story-state transitions.
`story_units` contain `planned_unit_id`, importance, terminal treatment,
repair action and evidence references. They never copy hierarchy, contribution,
reader state, downstream use, or a validation/pass/closure declaration.
Promises, arcs, threads and continuity keep their own domain identities and
lifecycle states. Chapter interface annotations point to planned units.

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

## Story units

`story_contribution_check.py` reads parent, contribution and downstream consumers
from the canonical plan. Annotate importance, terminal treatment (keep, revise,
cut, merge, defer, scoped_out or human_review), repairs and domain evidence here.
Unknown units fail with `unit_not_in_plan:novel_ledger:<id>`.

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

When a final manuscript is claimed, the reader chain must also
name the current final artifact reference and content hash in their evidence
path. A manuscript edit after source-requirement review, reverse outlining,
promise/payoff review, voice/style review, or final reader review stales the
affected evidence until it is rerun or explicitly scoped out.

## Computed validation and closure

Do not author validation or closure fields. `longform_closure_check.py` reads
the current project mesh and computes domain surface results. The standard
reader chain checks actual manuscript bytes and derives final closure. Keep
promise/thread lifecycle, continuity facts, draft progress, scope and deferrals;
none is a substitute for the current checks or actual-span review.
