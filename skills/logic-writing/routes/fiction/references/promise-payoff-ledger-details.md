# Promise Payoff Ledger — detailed checks

## Abandoned-With-Reason Handling

Use `abandoned_with_reason` only when the story intentionally drops a promise and the dropped obligation is visible to review.

Required evidence:

- original `source_row_id` and `promise_text`;
- importance level;
- reason for abandonment;
- decision source: user, reviewer, genre convention, artifact boundary, revision plan, or human-review decision;
- affected scene, structure, arc, stakes, WorldGuard, and closure rows;
- claim boundary explaining what the final output may and may not claim.

Allowed reasons:

- out_of_scope_for_current_artifact;
- intentionally_unresolved_ending;
- genre_appropriate_ambiguity;
- superseded_by_stronger_promise;
- merged_into_other_payoff;
- removed_with_scene_cut;
- user_requested_omission;
- human_review_decision.

Blocked reasons:

- forgotten;
- no_space;
- prose_sounds_fine;
- assumed_resolved;
- left_for_later with no boundary;
- generated_assumption_without_user_or_model_support.

Abandoned key or major promises should usually require human_review unless the user explicitly requested ambiguity or narrowed scope.

## Late Key Promise Guardrails

A late key promise is a key or major promise introduced after the story has entered final attack, climax, resolution, final revision, or closure preparation.

Late key promises are risky because they can create new obligations after the story has stopped preparing payoff evidence.

Guardrail checks:

1. Identify whether the promise is key or major.
2. Identify the current workflow stage and structure part.
3. Confirm setup evidence exists before the promise becomes payoff-critical.
4. Confirm scene contracts and turning-point rows can still support the promise.
5. Confirm WorldGuard claims needed by the promise are pass, scoped out, or visible as gaps.
6. Confirm payoff can occur inside the current artifact boundary.
7. Require human_review when the promise changes genre expectation, ending class, theme, protagonist arc, or closure claim.

Allowed late key promise outcomes:

- `accept_with_setup_patch`: add earlier setup rows, update scenes, structure, support, WorldGuard claims, and validation evidence.
- `defer_with_boundary`: keep the promise open outside the current artifact and narrow the claim boundary.
- `downgrade_to_supporting`: reduce importance and record why it no longer blocks closure.
- `convert_to_inversion`: make the late promise a fair reversal using existing setup evidence.
- `reject_or_cut`: remove the promise and repair affected prose, scene, and closure rows.
- `human_review`: ask for a material story-direction choice.

Do not accept a late key promise merely because the prose sounds compelling.

## Link Checks

### Ledger Link

Every promise/payoff row must live in the story-engineering ledger or a structured equivalent.

Return to ledger when:

- promise source, expectation, payoff target, status, or evidence refs are missing;
- generated assumptions are treated as user-approved promise facts;
- closure claims are made from prose without ledger rows.

### Scene Contract Link

Promises must connect to scenes that introduce, remind, escalate, pay, invert, defer, abandon, or cut them.

Return to scenes when:

- a scene opens a promise without recording it;
- a payoff scene lacks a scene contract;
- a scene is cut without updating affected promise rows;
- prose pays a promise differently than the scene card says.

### Structure-Turning-Points Link

Key and major promises should link to structure rows or turning points that carry expectation and payoff pressure.

Return to structure when:

- a key promise has no structure role;
- midpoint, second plot point, climax, or resolution changes promise meaning without updating promise rows;
- a structure row claims closure while promise rows remain open, unsupported, stale, or human_review.

### WorldGuard Link

Promises that depend on generic world facts must link to WorldGuard claim rows.

Return to WorldGuard when:

- a payoff depends on event order, causality, capability, access, resource, conflict, norm, or authority that is not mapped;
- a non-pass WorldGuard status is converted into story pass;
- stale, forbidden, boundary, authority, or missing-handoff findings are hidden by prose.

WorldGuard evidence can support whether the world claim is consistent. It does not decide whether the promise is emotionally satisfying, thematically right, or artistically elegant.

### Workflow Gate Link

Promise/payoff review participates in every downstream gate.

Before outline:

1. Record key and major promises.
2. Assign expected payoff type and target rows or mark gap, deferred, or human_review.
3. Link promises to structure, scene, support, and WorldGuard rows where needed.

Before drafting:

1. Confirm open promises have planned payoff, inversion, abandonment, deferral, or boundary status.
2. Confirm scene contracts and structure rows can carry the promise path.
3. Do not allow prose to imply closure for unsupported promises.

Before review:

1. Compare outline or prose against promise rows.
2. Flag missing setup, unsupported payoff, unfair inversion, abandoned-without-reason, late key promise, stale evidence, or hidden WorldGuard gap.
3. Assign return_to_ledger, return_to_structure, return_to_scene, return_to_promises, return_to_worldguard, return_to_revision, or user_decision.

Before final revision or closure:

1. Recheck every key and major promise after revisions.
2. Preserve stale payoff evidence until refreshed.
3. Require human_review for material ambiguity, late key promises, or abandoned major promises when no explicit user boundary exists.
4. Close only inside the supported claim boundary.

## Minimal Promise Payoff Checklist

For each promise, answer:

1. Where was it introduced?
2. What expectation did it create?
3. How important is it?
4. What payoff type is required?
5. Which scene contracts and structure turns carry the setup and payoff?
6. Which WorldGuard claims or support rows are needed?
7. Is the current status open, setup, escalated, payoff_planned, paid, inverted, abandoned_with_reason, deferred, partial, blocked, stale, unsupported, or human_review?
8. If inverted, what setup makes the inversion fair?
9. If abandoned, what reason and decision source make abandonment acceptable?
10. If introduced late, which late-key-promise guardrail outcome applies?
11. Which evidence refs prove the current status?
12. Which workflow gate receives any non-pass outcome?

Complete-story closure requires every key and major promise to be paid, fairly inverted, abandoned with reason, explicitly deferred, or human-reviewed with a narrowed boundary. A final prose claim is not valid while a key promise is open, unsupported, stale, blocked, or silently abandoned.

## Longform Promise Handling

Long-form artifacts may defer promises across chapter, volume, book, or series boundaries, but deferral must be explicit.

Additional statuses:

- `volume_deferred`: the promise is open beyond the current chapter but inside the current volume.
- `book_deferred`: the promise is open beyond the current volume but inside the current book.
- `series_deferred`: the promise is open beyond the current book but inside the series.

Additional required fields for deferred long-form promises:

- `deferral_level`: chapter, volume, book, or series.
- `claim_boundary`: what the current artifact may and may not claim.
- `next_expected_surface`: chapter, volume, book, or series row expected to carry the payoff.
- `reader_fairness_note`: why the deferral remains legible rather than forgotten.

Book closure cannot pass with an unresolved key promise unless it is paid, fairly inverted, abandoned_with_reason, human_review, or explicitly series_deferred with a boundary. Volume closure cannot pass with an unresolved volume-level key promise unless it is paid, fairly inverted, abandoned_with_reason, human_review, or book_deferred with boundary.

Serial hooks are allowed only when they name the promise they keep open and the closure report states the level where payoff is expected.

## Payoff Support Binding

For final prose or major revision claims, key and major payoffs must bind to earlier prose support, not only to a final explanation. A payoff feels sudden when the model names setup but the actual manuscript has no prose span that prepares the reader for the turn.

Check:

- which earlier prose spans set up the payoff;
- whether the final payoff introduces a new mechanism, term, object property, relationship fact, or world rule too late;
- whether earlier support was dramatized through action, object handling, dialogue, consequence, or reader-state movement;
- whether the payoff has resistance, cost, counter-interpretation, or consequence when the model requires pressure.

If payoff support exists only in a report, ledger, or final explanatory paragraph, return to promises, continuity, scene contracts, or earlier prose revision before claiming closure.
