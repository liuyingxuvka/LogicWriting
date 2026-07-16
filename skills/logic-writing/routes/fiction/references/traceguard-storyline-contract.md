# TraceGuard Storyline Contract

Use this reference when event order, causality, investigation order, reader
revelation, hidden past, mystery, time mechanics, or competing explanations
affect a StorylineDesign claim.

## Required Tracks

When TraceGuard is material, keep these tracks separate:

- `story_world_chronology`: what really happened in the story world.
- `protagonist_investigation_order`: what the protagonist learns or does.
- `reader_revelation_order`: what the reader knows and when.

Do not collapse these tracks into chapter summaries. A mystery can be coherent
only when the true chronology, protagonist discovery, and reader revelation are
distinct and intentionally related.

## Reader Hypothesis State

For staged revelation, TraceGuard should track reader hypothesis state as a genre-neutral expectation space, not as a required suspect, clue, romance, battle, or worldbuilding table.

Check:

- what the reader can still reasonably believe after each important unit;
- what the prose has ruled out;
- whether the model intended that narrowing;
- whether early certainty is replaced by a new pressure such as proof, cost, relationship consequence, moral choice, world-rule risk, or emotional danger;
- whether the actual prose collapses expectation earlier than the model supports.

If reader expectation collapses too early without replacement pressure, return to reader revelation order, promise timing, chapter interface, or prose projection.

## Event Row Shape

Each material event should record:

- `event_id`;
- `event_layer`: story_world, investigation, reader_revelation, or competing_explanation;
- `chapter_ids` or scene ids;
- `what_happened`;
- `before`;
- `after`;
- `cause_links`;
- `effect_links`;
- `competing_explanations`;
- `status`: passed, partial, blocked, stale, or human_review.

Compact short-form traces can use fewer rows, but still need event movement
and causal/revelation order when those are material.

## Closure Use

TraceGuard evidence blocks or downgrades closure when:

- the final story mixes true chronology with reader revelation;
- a clue appears before it exists;
- the protagonist knows something the investigation track never delivered;
- a causal payoff lacks a prior cause;
- a competing explanation is introduced and never resolved or scoped;
- prose changed after trace evidence was produced.

If TraceGuard is not material, record `not_applicable_with_reason` in closure.
