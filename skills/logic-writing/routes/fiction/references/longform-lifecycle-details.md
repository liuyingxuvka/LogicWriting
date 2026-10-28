# Longform Lifecycle — detailed checks

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
9. Compare reverse outline and SharedWriting quote binding against chapter interface, promises, contribution, continuity, variation pressure, and voice/style contract.

Reverse outline drift should note not only events, but also reader-facing problems: reader-room contamination, authorial chapter-function explanation, unsupported or premature reveal, repeated chapter contribution, weak or missing SharedWriting quote binding, unbound prose, unrealized model rows, duplicate binding, frictionless advancement, premature reader-state collapse, register drift, exposition replacing dramatized action, and character dialogue collapsing into the same author voice.

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
- the RouteReview and ReaderJudgment evidence that read the same final artifact hash;
- the SharedWriting span evidence that read the same final artifact hash;
- the revision action when source requirements, reverse outlines, promises,
  arcs, continuity, world rules, or voice/style do not support final closure.

When final prose is claimed, the RouteReview and ReaderJudgment must include reader-native manuscript review and the closure bundle must include SharedWriting span evidence. These reviews read the same final artifact as a normal reader and report reader-room contamination, author-facing chapter endings, explanation pressure, SharedWriting quote binding drift, unbound prose, unrealized model rows, duplicate binding, resistance/friction gaps, reader-state simulation gaps, register ownership drift, variation pressure, voice/style drift, unsupported or premature payoff, and repeated chapter contribution. This is reader review, not a genre-specific required schema.

Gate:

- `continue` when source requirements, final artifact evidence, SharedWriting quote
  binding evidence, and reader review all bind to the same current final artifact.
- `return` when file hygiene exists but reader review is absent, stale,
  report-only, or bound to an older artifact.
- `human_review` when the remaining issue is a material creative choice such as
  intentional ambiguity, ending class, or major promise abandonment.

## Stage 8: Longform Closure

Use `routes/fiction/references/longform-closure.md` to aggregate evidence by level:

- chapter closure checks local chapter interface, scene contracts, voice/style, promises, and reverse outline;
- volume closure checks all included chapters plus volume arcs and volume promises;
- book closure checks full book hierarchy, key promises, major arcs, continuity, source requirements, final artifact binding when final prose is claimed, and validation freshness;
- series closure checks book-level outputs, deferred series promises, continuity, and stated scope.

For final prose closure, aggregate reader-native manuscript review and variation review through the actual-span RouteReview surface. Do not treat file hygiene, chapter count, route completion, or model-only evidence as final manuscript readiness.

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
