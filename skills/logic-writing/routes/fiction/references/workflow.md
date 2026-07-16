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

For long-form final prose, major revision, or any prose readiness claim that depends on actual drafted text, run a model-prose binding pass after the reader-room clean pass:

1. Map important prose spans to model rows such as story units, scenes, promises, continuity, arcs, chapter interfaces, and voice/style rows.
2. Map key and major model rows back to prose evidence.
3. Record observed reader-state movement, state change, downstream use, resistance or cost, reader hypothesis movement, and register ownership notes.
4. Mark unbound prose, unrealized model rows, duplicate binding, smooth advancement without friction, premature reader-state collapse, register drift, and length outliers as drift.
5. Treat chapter length as a review trigger, not a hard failure: long prose passes only when binding rows show distinct functions and transitions.

Gate:

- `continue` when the draft is a supported projection of the model.
- `return` to outline, scenes, or ledger when prose introduces unsupported story facts, skips required payoffs, or bypasses open gaps.
- `user-decision` when prose direction depends on subjective taste not fixed by the model, such as voice, intensity, or ending tone.

## Stage 8: Review

Purpose: inspect the current artifact against the model before revision or closure.

Review for:

- ledger completeness and currentness;
- structure binding;
- scene contract coverage;
- arc and promise/payoff continuity;
- WorldGuard adapter status;
- model match: whether prose matches the current model, promises, continuity, chapter interface, and voice/style contract;
- model-prose binding: whether important prose spans bind to model rows and key or major model rows have prose evidence;
- reader-state simulation: whether the actual text changes what the reader knows, expects, doubts, fears, or reinterprets;
- resistance/friction: whether important advances carry pressure, cost, counter-interpretation, obstacle, or consequence when the model requires it;
- register ownership: whether important terms belong to the narrator, a character, a document, an institution, a profession, a local usage, or another story-world source;
- reader-room: whether normal readers see story-world prose rather than planning, audit, workflow, validation, chapter-purpose, or next-step language;
- explanation pressure: whether prose dramatizes through action, object, dialogue, silence, contradiction, and consequence instead of repeatedly explaining intended meaning;
- variation pressure: whether character voice, scene or location pressure, event function, information mode, emotional temperature, chapter rhythm, and reader-state movement show purposeful variation rather than unsupported sameness;
- skipped, stale, blocked, or human-review gates.

Gate:

- `continue` when issues are absent or minor enough for direct revision.
- `return` to the earliest failed stage when a model, mapping, closure, or prose projection gap is found.
- `user-decision` when the review finds a tradeoff that cannot be resolved from the user's stated intent.

## Stage 9: Revision

Purpose: repair the model and output together instead of patching prose alone.

When revising:

- identify the failing ledger, structure, scene, promise/payoff, WorldGuard, outline, or draft row;
- update the model first;
- refresh affected downstream artifacts;
- preserve stale evidence until refreshed;
- record any intentionally deferred issue.

Revision routing:

- Planning, audit, workflow, validation, chapter-purpose, or next-step language leaked into reader-native prose: return to Stage 7 reader-room clean pass.
- A chapter or scene repeats a previous unit's job without escalation, contrast, inversion, cost, deliberate rhythm, or new reader-state movement: return to Stage 3 story contribution and Stage 4 scene or chapter interface.
- Prose exists without model binding: cut, merge, narrow the claim, or return to Stage 2-4 to add a real model row before preserving it.
- A key or major model row lacks prose evidence: return to prose projection or downgrade the closure claim.
- Multiple spans bind to the same model function without changed reader state, resistance, cost, escalation, contrast, inversion, or downstream use: merge, cut, compress, or change one span's function.
- Evidence, discovery, emotional turn, or payoff advances too smoothly: return to scene contracts, promise/payoff, or resistance/friction review.
- Reader hypotheses collapse earlier than intended and no replacement pressure appears: return to TraceGuard reader revelation order, promise timing, or chapter interface.
- Important terminology drifts between narrator, report, profession, and character speech without ownership: return to voice/style continuity and register ownership.
- A reveal or explanation appears too early for the reader-state path: return to promise/payoff timing, chapter interface, and prose projection.
- A payoff feels sudden or unsupported: return to promises and continuity rows, then revise earlier prose if needed.
- Characters sound alike or explain too much: return to voice/style continuity, then revise dialogue and exposition.
- A chapter ending explains its function or forecasts the next chapter from an author-facing position: return to chapter interface and reader-native prose projection.
- Repetition is intentional: record the repeated element's story function and changed reader effect before preserving it.

Gate:

- `continue` when repaired rows and affected outputs are current.
- `return` to the failed stage when repair creates a new gap or invalidates downstream evidence.
- `user-decision` when repair options change the story's meaning, scope, genre, or ending.

## Stage 10: Closure

Purpose: decide what the skill can safely claim about the final output.

Closure must aggregate:

- ledger completeness;
- structure binding;
- scene coverage;
- character arc coverage;
- promise/payoff closure;
- support and premise status;
- WorldGuard adapter status;
- reader-native manuscript review when final prose is claimed;
- model-prose binding review when final long-form prose is claimed;
- variation pressure review when long-form prose is claimed;
- validation freshness;
- skipped, stale, blocked, or human-review rows.

Closure outcomes:

- `continue`: final or requested output is supported by current evidence.
- `return`: a named gap prevents the requested claim; repair the earliest failed stage.
- `user-decision`: a human choice is required before closure can be claimed.

Never let polished prose, a local scene pass, or an outline pass substitute for aggregate closure.

## Minimal Route Checklist

For a complete story, run:

1. Intake.
2. Ledger.
3. Structure.
4. Scenes.
5. WorldGuard checks when world consistency matters.
6. Outline.
7. Draft.
8. Review.
9. Revision when review returns gaps.
10. Closure.

For a partial artifact, run only the stages needed for that artifact and state the narrowed boundary. For an audit, expose the relevant ledger rows, gate outcomes, and closure gaps instead of hiding them behind reader-native prose.

## Longform Compatibility Route

When the requested artifact is a novel, book, volume, series, chapter batch, continuity repair, or chapter prose with adjacent-chapter dependency, enter Longform Mode after Stage 1 intake and use `longform-lifecycle.md`.

Longform Mode adds these required stages before ordinary outline, draft, review, revision, or closure claims:

1. Build or update the novel ledger.
2. Check hierarchy coverage for books, volumes, chapters, scenes, arcs, threads, promises, and continuity.
3. Run story contribution review so no important chapter, scene, subplot, or clue is counted without parent contribution and downstream use.
4. Bind chapter interfaces, reader-state before/after, unresolved tension, promise movement, and hook role.
5. Maintain a weakness queue for orphan, duplicate, weak, unsupported, stale, blocked, or human-review rows.
6. Use chapter prose blueprints before drafting and reverse outlines after prose exists.
7. Run voice/style continuity checks for POV, tense, narration distance, diction, dialogue, pacing, exposition, and cadence.
8. Close at the requested level only: chapter, volume, book, or series.

If any long-form surface returns a non-pass status, return to the earliest failed long-form surface before claiming a complete outline, final chapter prose, book readiness, or series closure.
