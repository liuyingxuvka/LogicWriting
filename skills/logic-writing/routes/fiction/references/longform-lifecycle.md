# Longform Lifecycle

Use this reference when a StorylineDesign task targets a novel, book, volume, series, chapter batch, continuity repair, or chapter-level prose that depends on adjacent chapters. Longform Mode is the deep tier of the story lifecycle. It extends the normal workflow; it does not replace short-story structure, scene, promise/payoff, WorldGuard, prose-native, or closure checks.

## Longform Gate Vocabulary

Each stage ends in one of these outcomes:

- `continue`: evidence is current enough for the next stage.
- `return`: a repairable gap sends the run back to the named earlier surface.
- `user-decision`: a material creative or scope choice is required.
- `narrow`: the output is allowed only as a smaller artifact, such as chapter notes, sample prose, or an audit.

Do not treat a local chapter pass as book or series pass. Long-form closure is level-specific.

## Stage 1: Longform Intake

Capture:

- target level: chapter, chapter_batch, volume, book, series, revision_plan, audit, or prose_sample;
- form constraints: genre, audience, tense, POV, narration distance, length target, release cadence, and language;
- supplied material: premise, outline, draft chapters, world notes, character notes, previous ledgers, or canon;
- requested output visibility: planning, audit, reader_native, or mixed;
- claim boundary: what may be claimed complete now, and what remains outside scope.

Reader-native boundary:

- `planning` output may contain chapter purpose, next-step plan, contribution notes, and revision logic.
- `audit` output may contain review language and gate findings.
- `mixed` output must clearly label which parts are story prose and which parts are author-facing notes.
- `reader_native` output must not contain author-facing planning, audit, workflow, validation, chapter-purpose, or next-step language unless the fictional form itself justifies it.

Gate:

- `continue` when the target level and claim boundary are explicit.
- `return` when the supplied material contradicts the target.
- `user-decision` when multiple book arcs, protagonists, endings, or POV policies would materially change the novel.

## Stage 2: Novel Ledger

Create or update `references/novel-ledger.md` fields for:

- book, volume, chapter, and scene hierarchy;
- arcs, threads, promises, clues, mysteries, stakes, and continuity records;
- draft state, revision state, validation state, and closure state;
- short-form ledger rows when scene-level checks are needed.

The novel ledger is the root index for the layered model mesh. It points to child surfaces rather than substituting for them. Continuity rows must keep object location and condition, character knowledge, timeline mechanics, world rules, relationship state, clue state, and voice/style state inspectable.

Gate:

- `continue` when every important long-form unit has a ledger row or scoped-out reason.
- `return` when hierarchy, thread, promise, continuity, or closure fields are missing.
- `narrow` when only an early outline or diagnosis is supported.

## Stage 3: Story Contribution

Use `references/story-contribution-contract.md` to check each important story unit.

For every book, volume, chapter, scene, arc, thread, promise, and continuity row, identify:

- parent contribution;
- downstream use;
- terminal treatment if removed, deferred, merged, or intentionally unresolved;
- repair action for orphan, duplicate, weak, unsupported, or stale units.

Run contribution review twice when prose exists:

1. Before drafting, confirm why the unit deserves to exist in the parent.
2. After drafting, confirm what the actual prose changed for the reader, not only what the outline intended.

Post-draft contribution review must catch variation pressure: repeated unit function without escalation, contrast, inversion, cost, deliberate rhythm, or new reader-state movement.

Gate:

- `continue` when important units have parent contribution and downstream use.
- `return` when a chapter, scene, arc, thread, or promise is orphaned, duplicated, unsupported, or counted only because it exists.
- `user-decision` when removing or merging a unit changes meaning, pacing, or genre promise.

## Stage 4: Chapter Interface

Use `references/chapter-interface-prose-blueprint.md` to bind chapter-to-chapter movement.

For each chapter in scope, record:

- previous chapter output and current chapter input;
- reader-state before and after;
- unresolved tension carried forward;
- promise movement, arc movement, and hook role;
- prose blueprint and reverse outline evidence when prose exists.

Chapter interface also owns the story-world chapter ending boundary. A chapter handoff may describe what the next chapter inherits, but reader-native prose endings must land inside the story world through action, object, reaction, choice, new pressure, sensory image, unresolved fact, or consequence. Do not end reader-native prose by explaining the chapter's function or forecasting the next chapter from an author-facing position.

When adjacent chapters repeat opening movement, evidence path, explanation mode, emotional temperature, or ending rhythm, record the repetition as variation pressure unless it has a deliberate effect.

Gate:

- `continue` when adjacent handoffs are concrete and reader state changes are inspectable.
- `return` when handoffs are generic placeholders, missing, or contradicted by prose.
- `narrow` when a standalone chapter sample is allowed but not chapter-sequence closure.

## Stage 5: Voice And Style Continuity

Use `references/voice-style-continuity.md` to preserve narrative voice across chapters.

Check:

- POV policy, tense, narration distance, diction, sentence rhythm, dialogue style, exposition policy, pacing, and emotional temperature;
- allowed variation by character, chapter, timeline, or register;
- drift status and repair action.

Voice/style continuity includes character voice distinction and explanation pressure. Characters may share profession, family, institution, culture, period, or genre register, but major voices still need character-specific pressure, knowledge boundary, desire, fear, evasion, status, or self-protection. Repeated abstract author-like summary across characters is drift.

Gate:

- `continue` when no blocking continuity drift remains for the requested claim.
- `return` when unresolved POV, tense, style, dialogue, pacing, or exposition drift blocks the claim.
- `human_review` when voice choice is subjective and materially changes the book.

Detailed checks continue in [longform-lifecycle-details](longform-lifecycle-details.md).

## Stage 6: Prose Projection And Reverse Outline

See [Stage 6: Prose Projection And Reverse Outline](longform-lifecycle-details.md#stage-6-prose-projection-and-reverse-outline).

## Stage 7: Final Prose Freshness

See [Stage 7: Final Prose Freshness](longform-lifecycle-details.md#stage-7-final-prose-freshness).

## Stage 8: Longform Closure

See [Stage 8: Longform Closure](longform-lifecycle-details.md#stage-8-longform-closure).

## Minimal Longform Route

See [Minimal Longform Route](longform-lifecycle-details.md#minimal-longform-route).
