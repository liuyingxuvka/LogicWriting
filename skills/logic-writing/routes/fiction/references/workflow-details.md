# StorylineDesign Workflow — detailed checks

## Stage 8: Review

Purpose: inspect the current artifact against the model before revision or closure.

Review for:

- ledger completeness and currentness;
- structure binding;
- scene contract coverage;
- arc and promise/payoff continuity;
- WorldGuard adapter status;
- model match: whether prose matches the current model, promises, continuity, chapter interface, and voice/style contract;
- SharedWriting quote binding: whether important prose spans bind to model rows and key or major model rows have prose evidence;
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
- SharedWriting quote binding review when final long-form prose is claimed;
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
