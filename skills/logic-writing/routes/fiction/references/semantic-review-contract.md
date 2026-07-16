# Artifact-Bound Semantic Review

Semantic review preserves AI or human literary judgment while making its
artifact scope inspectable. Deterministic validation proves identity,
coverage shape, and blocking semantics; it does not prove that the reviewer’s
literary judgment is true.

## Identity

The review must name one `project_id`, `model_revision`, evaluator identity,
review timestamp, and content-addressed manuscript reference. The checker
opens that manuscript and recomputes its SHA-256. A review of an older byte
sequence is stale even when its path is unchanged.

## Scope

Record reviewed unit ids and every required dimension:

- reader-room contamination;
- explanation pressure;
- purposeful variation;
- chapter or scene contribution;
- point of view, voice, and style continuity;
- promise, payoff, arc, and continuity realization;
- model-prose binding;
- resistance, friction, cost, and reader-state movement;
- register ownership.

Each dimension records findings, evidence anchors, status, and reviewer notes.
The review also records skipped scope with reasons, limitations, unresolved
human-review items, and its final decision.

## Closure

A passed final-prose review has no blocking finding, hidden skipped scope, or
unresolved human-review item inside the claimed boundary. A partial or blocked
review stays visible and cannot be rewritten into a pass by the closure file.
