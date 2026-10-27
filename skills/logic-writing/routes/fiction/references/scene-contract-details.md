# Scene Contract — detailed checks

## Contract Checks

Run these checks before treating a planned or drafted scene as structurally ready.

### Function Check

Ask what the scene does for the story model.

Pass when at least one of these is true and linked to a ledger row:

- changes structure state;
- contains or prepares a turning point;
- escalates or resolves a promise;
- changes protagonist, relationship, or theme arc;
- changes stakes;
- reveals or tests a world fact;
- creates necessary support for later closure.

Fail or revise when the scene is only a prose event with no ledger function.

### State Change Check

Compare `entry_state`, `exit_state`, and `irreversible_change`.

Pass when the scene changes story state in a way later rows can depend on.

Revise when:

- entry and exit states are nearly the same;
- the irreversible change is only mood or description;
- later structure rows do not depend on the change.

Cut when the scene duplicates another scene's state change and no unique function remains.

### Conflict And Desire Check

Check `conflict_pressure`, `character_desire`, and `obstacle`.

Pass when the scene contains visible pressure and a focal desire constrained by an obstacle.

Revise when:

- the desire is generic;
- the obstacle is absent;
- the scene has conflict language but no decision pressure;
- the focal character has no agency, refusal, discovery, sacrifice, or forced reaction.

Human review when the desired pressure depends on tone, genre, intensity, or point of view.

### Turn Check

Check the `turning_point` object.

Pass when the scene includes a decision, reveal, reversal, consequence, commitment, refusal, discovery, or loss that changes the next scene or structure row.

Revise when:

- the turn is only information with no pressure change;
- the turn has no handoff to structure-turning-points rows;
- the scene contains multiple turns but none is declared as the contract-driving turn.

Cut when removing the scene does not affect any later state, promise, arc, or world claim.

### Scene Variation Check

Check whether the scene changes pressure, action strategy, information mode, or reader effect compared with nearby scenes.

Pass when repetition is purposeful or when at least one of these changes is clear:

- the dominant pressure changes, such as body, time, relationship, institution, resource, memory, moral, access, or environment pressure;
- the focal character uses a different action strategy, such as pursuit, refusal, observation, negotiation, concealment, confession, verification, retreat, or sacrifice;
- the setting changes what characters can do, know, hide, risk, or perceive;
- information arrives through a different story-world route, such as action, object, contradiction, silence, failed test, overheard speech, document, memory, physical trace, or social pressure;
- the emotional temperature, rhythm, or reader-state movement changes.

Revise when:

- the location name changes but the scene pressure remains equivalent;
- the scene repeats another scene's event function without escalation, contrast, inversion, cost, or changed reader interpretation;
- information repeatedly arrives through abstract explanation rather than dramatized scene material;
- a concrete object or setting detail is decorative and does not change pressure, action, continuity, promise, or reader state.

Human review when the repetition may be a deliberate aesthetic pattern, genre convention, ritual, refrain, or structural echo whose value depends on author intent.

### Promise And Payoff Check

Check every `promise_links` entry.

Pass when each promise role is setup, reminder, escalation, payoff, reversal, deferral, or blocker and the linked promise row is current.

Revise when:

- a scene opens a question with no expected payoff;
- a payoff appears without setup or intentional surprise support;
- a promise is deferred without a deferral reason;
- a drafted scene hides an open promise behind polished prose.

Return to promises when promise status is missing or stale.

### Structure Link Check

Check `parent_structure_id` and `turning_point_links`.

Pass when the scene's function supports the current structure row and does not contradict setup, first plot point, reaction, midpoint, attack, second plot point, climax, or resolution checks.

Revise when:

- the scene belongs to the wrong part or turning point;
- the scene changes structure without updating structure-turning-points rows;
- the scene tries to close a parent structure row by local coherence alone.

Return to structure when parent role, part, or turn handoff is unclear.

### WorldGuard Link Check

Check every `worldguard_claim_links` entry.

Pass when generic world claims needed by the scene are pass, scoped out, or explicitly narrowed.

Revise when:

- a world claim is not_run, gap, stale, forbidden_use, boundary_exceeded, authority_cycle, missing_handoff, or fail;
- the scene relies on event order, causality, capability, access, resource, conflict, norm, or authority not mapped into WorldGuard when world consistency matters;
- a WorldGuard finding is converted into story pass instead of returning to the affected row.

Return to WorldGuard when generic world-claim validation is needed. Return to ledger, structure, or scene when the problem is story ownership rather than world consistency.

### Prose Boundary Check

Check `prose_status` against current ledger and closure state.

Pass when prose is a projection of current scene, structure, promise, support, and WorldGuard evidence.

Revise when prose introduces unsupported facts, skips required payoffs, changes scene state, or hides stale evidence.

Block closure when `prose_status` is `final_candidate` but scene contract, structure, promise, WorldGuard, or validation rows are partial, blocked, gap, stale, skipped, or human_review.

## Workflow Gate Links

Before outline:

1. Every important scene has a scene card or an explicit scoped-out reason.
2. Scene cards link to parent structure and turning-point rows.
3. Promises, arcs, stakes, support, and world claims touched by the scene are visible in the ledger.

Before drafting:

1. Required scene cards are keep or revise with a narrowed drafting boundary.
2. Scene contracts have entry state, exit state, irreversible change, conflict pressure, desire, obstacle, and turn.
3. WorldGuard claims needed by scene logic are pass, scoped out, or marked as a visible gap.

Before review:

1. Compare prose against scene cards.
2. Record any invented fact, skipped turn, hidden promise, missing WorldGuard evidence, or stale support.
3. Assign keep, revise, cut, or human_review for each reviewed scene.

Before revision:

1. Update the ledger first.
2. Refresh affected structure, scene, promise, WorldGuard, validation, and closure rows.
3. Preserve stale evidence until replaced.

Before closure:

1. Every required scene has a current contract outcome.
2. No scene with revise, cut, or human_review is silently counted as closed.
3. Aggregate closure checks scene contract coverage together with ledger, structure, promise/payoff, WorldGuard, validation freshness, and reader-native projection.
4. Final prose can be claimed ready only inside the supported boundary.

## Minimal Scene Review Checklist

For each scene, answer:

1. Which ledger row owns the scene?
2. Which parent structure or turning-point row does it serve?
3. What are the entry state, exit state, and irreversible change?
4. What does the focal character want?
5. What obstacle or pressure makes the scene non-trivial?
6. What decision, reveal, reversal, consequence, or refusal turns the scene?
7. Which promises, arcs, stakes, support rows, and WorldGuard claims does it touch?
8. Does the current prose match the scene contract?
9. Is the outcome keep, revise, cut, or human_review?
10. Which workflow gate receives any non-pass outcome?

The scene is not ready for closure until these answers are current or the claim boundary explicitly says why the scene is out of scope.

## Longform Scene Links

For Longform Mode, scene cards may include these additional fields:

- Parent chapter is read from the composition plan.
- `chapter_interface_id`: adjacent chapter interface affected by the scene.
- `reader_state_delta`: what the reader learns, expects, doubts, fears, or reinterprets because of the scene.
- `serial_hook_role`: none, setup, pressure_forward, cliffhanger, quiet_bridge, payoff_delay, or volume_hook.
- `longform_closure_effect`: continue, return_to_chapter_interface, return_to_longform_ledger, return_to_voice_style, return_to_reverse_outline, or scoped_out.
- `variation_note`: optional note for scene variation pressure, repeated function, or intentional repetition with changed effect.

Promise roles may also include `serial_hook`, `volume_setup`, `book_setup`, `book_payoff`, and `series_deferral`.

A scene can pass locally but still fail long-form closure when it breaks chapter handoff, reader-state continuity, serial promise movement, voice/style continuity, or parent contribution.
