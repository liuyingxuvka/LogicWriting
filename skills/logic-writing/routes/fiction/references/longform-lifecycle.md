# Longform Lifecycle

Use this reference when a StorylineDesign task targets a novel, book, volume, series, chapter batch, continuity repair, or chapter-level prose that depends on adjacent chapters. Longform Mode is the deep tier of the universal guarded story lifecycle. It extends the normal workflow; it does not replace short-story structure, scene, promise/payoff, WorldGuard, prose-native, or closure checks.

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

## Stage 6: Prose Projection And Reverse Outline

Draft only inside the current model boundary.

For chapter prose:

1. Model-room brief: read approved chapter interface, scene cards, story contribution rows, promises, continuity, and voice/style report. This internal brief may contain chapter purpose, next-step plan, promise movement, contribution notes, variation risks, and revision logic.
2. Reader-native draft: turn the brief into story-facing prose without workflow labels, validation language, chapter-purpose statements, author forecasts, or next-step instructions.
3. Reader-room clean pass: remove reader-room contamination, rewrite author-facing explanations as story-world material, check story-world chapter ending, check explanation pressure, and check variation pressure.
4. Reverse outline: create or update a reverse outline from the actual prose, not the plan. Reverse outlines must be event-and-state evidence, not broad summaries substituted by prose/report text.
5. Model-prose binding: map actual prose spans to model rows and map key or major model rows back to prose evidence. Record observed reader-state movement, observed state delta, downstream use, resistance or cost, reader hypothesis movement, register ownership notes, variation purpose, unresolved binding drift, and length-outlier review.
6. Reader-state simulation: compare intended reader state with what the actual prose makes a normal reader know, expect, doubt, fear, or reinterpret.
7. Resistance/friction review: check whether major reveals, decisions, discoveries, and payoffs carry pressure, cost, counter-interpretation, obstacle, delay, or consequence unless the model scopes out friction for a deliberate rhythm.
8. Register ownership review: check whether important terms, professional vocabulary, document language, local usage, or narrator language have story-world ownership.
9. Compare reverse outline and model-prose binding against chapter interface, promises, contribution, continuity, variation pressure, and voice/style contract.

Reverse outline drift should note not only events, but also reader-facing problems: reader-room contamination, authorial chapter-function explanation, unsupported or premature reveal, repeated chapter contribution, weak or missing model-prose binding, unbound prose, unrealized model rows, duplicate binding, frictionless advancement, premature reader-state collapse, register drift, exposition replacing dramatized action, and character dialogue collapsing into the same author voice.

Gate:

- `continue` when prose matches the model and reverse outline evidence is current.
- `return` when prose invents unsupported facts, drops a promise, breaks a handoff, or drifts in voice.
- `narrow` when only a sample or exploratory draft is supported.

## Stage 7: Final Prose Freshness

Run this stage when the claim includes final drafted prose for a chapter, volume,
book, or series. Skip it only when the claim boundary explicitly says final prose
is not claimed.

Record:

- the source requirements or user request surface used for acceptance;
- the final artifact path, file reference, or equivalent durable artifact id;
- the final artifact `sha256` or equivalent immutable content evidence;
- the semantic story review evidence that read the same final artifact hash;
- the model-prose binding evidence that read the same final artifact hash;
- the revision action when source requirements, reverse outlines, promises,
  arcs, continuity, world rules, or voice/style do not support final closure.

When final prose is claimed, the semantic story review must include reader-native manuscript review and the closure bundle must include model-prose binding evidence. These reviews read the same final artifact as a normal reader and report reader-room contamination, author-facing chapter endings, explanation pressure, model-prose binding drift, unbound prose, unrealized model rows, duplicate binding, resistance/friction gaps, reader-state simulation gaps, register ownership drift, variation pressure, voice/style drift, unsupported or premature payoff, and repeated chapter contribution. This is semantic review, not a genre-specific required schema.

Gate:

- `continue` when source requirements, final artifact evidence, model-prose
  binding evidence, and semantic review all bind to the same current final artifact.
- `return` when file hygiene exists but semantic review is absent, stale,
  report-only, or bound to an older artifact.
- `human_review` when the remaining issue is a material creative choice such as
  intentional ambiguity, ending class, or major promise abandonment.

## Stage 8: Longform Closure

Use `references/longform-closure.md` to aggregate evidence by level:

- chapter closure checks local chapter interface, scene contracts, voice/style, promises, and reverse outline;
- volume closure checks all included chapters plus volume arcs and volume promises;
- book closure checks full book hierarchy, key promises, major arcs, continuity, source requirements, final artifact binding when final prose is claimed, and validation freshness;
- series closure checks book-level outputs, deferred series promises, continuity, and stated scope.

For final prose closure, aggregate reader-native manuscript review and variation review through the artifact-bound semantic review surface. Do not treat file hygiene, chapter count, route completion, or model-only evidence as final manuscript readiness.

Gate:

- `continue` only for the stated closure level.
- `return` to the earliest failed surface when required evidence is missing or stale.
- `human_review` when closure depends on a creative or publishing decision.

## Minimal Longform Route

For a long-form novel claim, run:

1. Longform intake.
2. Novel ledger.
3. Story contribution.
4. Chapter interface.
5. Structure, scene, promise/payoff, and WorldGuard checks where applicable.
6. Voice/style continuity.
7. Prose projection and reverse outline when prose exists.
8. Final prose freshness when final drafted prose is claimed.
9. Longform closure.

For a partial artifact, run only the required subset and state the narrowed boundary.
