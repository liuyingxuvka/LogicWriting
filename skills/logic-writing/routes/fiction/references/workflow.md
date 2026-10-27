# StorylineDesign Workflow

Use this reference when a storyline-design task needs the end-to-end route from raw story input to story-facing output. The workflow is model-first: build or repair the story design model before complete prose, and keep every gate outcome explicit.

## Gate Vocabulary

Every stage ends in one of these gate outcomes.

- `continue`: required inputs and checks are sufficient for the next stage.
- `return`: the stage found a repairable gap; go back to the named earlier stage and update the model or ledger before proceeding.
- `user-decision`: the skill cannot safely choose between material story directions or scope tradeoffs; ask the user for the specific choice, then resume at the named stage.

Do not treat `return` or `user-decision` as success. They narrow or pause the claim boundary until the gap is resolved.

## Stage 1: Intake

Purpose: turn the user's request into a bounded story-design job.

Capture:

- requested artifact: premise, audit, outline, scene card, chapter plan, short story, revision plan, or full story;
- audience, genre, tone, length, format, and constraints;
- supplied material: idea, draft, outline, world notes, character notes, or prior story model;
- requested visibility: reader-native output, planning artifact, audit report, or mixed;
- any non-negotiable canon, source, safety, or style boundary.

Output-room rule:

- `planning` may expose model-room language such as chapter purpose, next-step plan, contribution notes, and revision logic.
- `audit` may expose review language, findings, and gate outcomes.
- `mixed` must clearly separate reader-facing prose from author-facing planning or audit notes.
- `reader-native` must contain only story-facing language unless the fictional form itself justifies meta language. Reader-native output must not expose planning language, review language, workflow labels, validation status, chapter-purpose statements, or author-facing next-step instructions.

Gate:

- `continue` when the requested artifact and minimum constraints are clear enough to build a model.
- `return` to intake when a supplied draft or outline conflicts with the stated request.
- `user-decision` when multiple story premises, endings, protagonists, genres, or output scopes are plausible and the choice would materially change the result.

## Stage 2: Story Engineering Ledger

Purpose: create the durable model surface that later checks can inspect.

Create or update ledger rows for:

- premise and target artifact;
- world boundary and canon constraints;
- major structure units such as acts, chapters, sequences, or movements;
- scenes and scene contracts;
- character arcs and relationship arcs;
- promises, questions, mysteries, emotional contracts, and payoff obligations;
- source, premise, or user-provided support;
- WorldGuard adapter mappings for world consistency checks;
- validation state, skipped checks, stale evidence, human-review items, and closure state.

Gate:

- `continue` when every important story obligation has a ledger row or an explicit out-of-scope note.
- `return` to intake when the target artifact cannot be represented in the ledger without changing the request.
- `user-decision` when the ledger exposes a major unresolved creative choice, such as which promise to prioritize or which ending class to pursue.

## Stage 3: Structure

Purpose: bind the ledger to a coherent story shape before scene work.

Check:

- the opening state, disruption, escalation, turn, crisis, climax, and resolution are represented at the requested granularity;
- each major structure unit has a function, tension movement, and dependency on prior units;
- no major promise or arc is orphaned from the structure;
- intentional ambiguity is labeled as intentional, not hidden missing work.

Gate:

- `continue` when the structure can carry the requested artifact.
- `return` to the ledger when structure rows are missing, duplicated, unsupported, or detached from promises and arcs.
- `user-decision` when two or more viable structures would lead to materially different stories.

## Stage 4: Scenes

Purpose: make scene-level commitments before outline or prose projection.

For each important scene, record:

- scene id and parent structure unit;
- entry state, exit state, and irreversible change;
- visible conflict or pressure;
- character desire and obstacle;
- promise, payoff, clue, reveal, or setup touched by the scene;
- required world facts or continuity claims;
- whether the scene is required, optional, deferred, or replaced.

Gate:

- `continue` when important scenes have scene contracts and parent structure links.
- `return` to structure or ledger when scenes do not change state, duplicate the same function, or fail to serve promises, arcs, or world constraints.
- `user-decision` when scene selection depends on an unresolved creative priority such as pacing, point of view, or ending emphasis.

## Stage 5: WorldGuard Checks

Purpose: validate story-world consistency without moving literary fields into WorldGuard core.

Translate only generic world claims through the adapter layer:

- event order and causality;
- agents, roles, capabilities, and motivations;
- spaces, resources, constraints, and access;
- conflicts, norms, promises, and consequences where they affect world consistency.

Preserve WorldGuard results as downstream evidence. A non-pass, stale, forbidden-use, or boundary-exceeded finding must remain visible as a gap or narrowed claim boundary. Do not rewrite WorldGuard schemas to hold chapters, scenes, theme, arcs, or prose style.

Gate:

- `continue` when required world claims are pass, explicitly scoped out, or safely narrowed.
- `return` to ledger, structure, or scenes when a world claim is inconsistent, stale, unsupported, or mapped from the wrong literary row.
- `user-decision` when a world inconsistency can be repaired in multiple story-significant ways.

## Stage 6: Outline

Purpose: project the validated model into reader-native planning language.

The outline should express:

- premise and dramatic question;
- structure beats or chapter sequence;
- scene order and scene purpose;
- character arc movement;
- promise/payoff path;
- known limitation or deferred branch, if any.

Gate:

- `continue` when the outline faithfully projects the current model and does not hide known gaps.
- `return` to scenes, structure, or ledger when the outline invents unsupported events, skips required payoffs, or conflicts with the model.
- `user-decision` when the outline exposes a creative choice the user should make before drafting.

## Stage 7: Draft

Purpose: produce prose only within the supported claim boundary.

Complete-story prose is allowed only after ledger, structure, scene, promise/payoff, WorldGuard, and closure preparation are complete enough for the requested output. Partial prose, such as a sample scene or style test, may be produced earlier only when labeled as partial and not presented as final story closure.

For any reader-native prose claim, drafting is not complete when model-supported prose exists. Run a reader-room clean pass before Stage 8 review:

1. Remove or rewrite reader-room contamination such as planning language, audit language, workflow labels, validation status, author-facing chapter-purpose statements, and next-step instructions.
2. Replace chapter-purpose explanation with story-world action, object, reaction, choice, pressure, sensory image, unresolved fact, or consequence.
3. Replace author forecast with in-scene pressure.
4. Check whether chapter endings remain inside the story world.
5. Check explanation pressure: whether exposition is doing work that action, object, dialogue, silence, contradiction, or consequence should do.
6. Check variation pressure: whether adjacent or clustered prose repeats the same voice, event function, scene pressure, reveal method, emotional temperature, or ending rhythm without purposeful effect.
7. Mark unresolved drift and return to the earliest failed stage.

For long-form final prose, major revision, or any prose readiness claim that depends on actual drafted text, run a SharedWriting binding validation after the reader-room clean pass:

1. Map important prose spans to model rows such as story units, scenes, promises, continuity, arcs, chapter interfaces, and voice/style rows.
2. Map key and major model rows back to prose evidence.
3. Record observed reader-state movement, state change, downstream use, resistance or cost, reader hypothesis movement, and register ownership notes.
4. Mark unbound prose, unrealized model rows, duplicate binding, smooth advancement without friction, premature reader-state collapse, register drift, and length outliers as drift.
5. Treat chapter length as a review trigger, not a hard failure: long prose passes only when binding rows show distinct functions and transitions.

Gate:

- `continue` when the draft is a supported projection of the model.
- `return` to outline, scenes, or ledger when prose introduces unsupported story facts, skips required payoffs, or bypasses open gaps.
- `user-decision` when prose direction depends on subjective taste not fixed by the model, such as voice, intensity, or ending tone.

Detailed checks continue in [workflow-details](workflow-details.md).

## Stage 8: Review

See [Stage 8: Review](workflow-details.md#stage-8-review).

## Stage 9: Revision

See [Stage 9: Revision](workflow-details.md#stage-9-revision).

## Stage 10: Closure

See [Stage 10: Closure](workflow-details.md#stage-10-closure).

## Minimal Route Checklist

See [Minimal Route Checklist](workflow-details.md#minimal-route-checklist).

## Longform Compatibility Route

See [Longform Compatibility Route](workflow-details.md#longform-compatibility-route).
