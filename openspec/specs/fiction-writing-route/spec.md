# fiction-writing-route Specification

## Purpose
TBD - created by archiving change expand-logic-writing-four-routes. Update Purpose after archive.
## Requirements
### Requirement: Fiction route owns fiction artifacts
The `fiction-writing` route SHALL own story plans, short stories, chapters, novels, series structures, substantive fiction revisions, and final-manuscript closure.

#### Scenario: Historical novel opens investigation child
- **WHEN** a fiction artifact needs bounded historical or factual research
- **THEN** fiction SHALL remain the final owner
- **AND** investigation SHALL return only the requested evidence packet

### Requirement: Fiction depth is explicit
The route SHALL select a compact, full-guarded, or longform depth from artifact scope and requested claim, and SHALL NOT use compact evidence to claim longform or final-manuscript closure.

#### Scenario: Short prompt requests a premise audit
- **WHEN** the artifact and claim are compact and no final prose is requested
- **THEN** compact evidence MAY satisfy the bounded planning claim

#### Scenario: Final novel prose is requested
- **WHEN** the route claims final chapter, volume, book, or series prose
- **THEN** longform artifact, mesh, binding, continuity, semantic-review, and closure surfaces SHALL be current

### Requirement: Story units contribute and hand off reader state
Scenes, chapters, arcs, and parent structures SHALL name their story contribution, incoming state, outgoing reader state, unresolved tension, promise movement, arc movement, and downstream consumer or terminal disposition.

#### Scenario: Chapter interface is generic
- **WHEN** a chapter interface says only that the story continues or sets up the next chapter
- **THEN** chapter-interface validation SHALL fail

### Requirement: Promises and payoffs remain explicit
Material story promises SHALL be opened, escalated, paid, inverted, deliberately deferred, abandoned with reason, or marked unresolved; polished prose SHALL NOT convert an unresolved promise into a pass.

#### Scenario: Key promise disappears
- **WHEN** a key promise has no payoff, inversion, accepted deferral, or abandonment disposition at the claimed closure level
- **THEN** closure SHALL remain blocked or partial

### Requirement: World, continuity, and voice owners remain distinct
WorldGuard SHALL own material world consistency, while fiction route validators own story continuity, character/arc continuity, point of view, tense, narration distance, dialogue distinction, exposition pressure, and allowed variation.

#### Scenario: Fictional setting is automatically scoped out
- **WHEN** a fictional world claim materially affects events, resources, access, capability, conflict, authority, or norms
- **THEN** the route SHALL NOT scope out WorldGuard merely because the setting is fictional

### Requirement: Fiction final prose binds model and manuscript
The route SHALL open the real manuscript, recompute its identity, reverse-outline actual events and reader-state changes, bind important prose spans to current model rows, and reject unbound prose, unrealized rows, unsupported duplicate binding, and stale semantic review.

#### Scenario: Declared manuscript hash is forged
- **WHEN** the declared artifact hash differs from the opened manuscript bytes
- **THEN** final-prose closure SHALL fail

#### Scenario: Attractive prose lacks binding
- **WHEN** final prose is readable but important spans or model rows lack current model-prose binding
- **THEN** final-prose closure SHALL remain blocked

### Requirement: Fiction semantic judgment remains bounded
Artifact-bound semantic review SHALL assess contribution, reader-room contamination, explanation pressure, variation, voice, payoff, resistance, reader-state movement, and register while preserving explicit human-review limits.

#### Scenario: Literary beauty is claimed deterministically
- **WHEN** deterministic checks pass
- **THEN** the route SHALL NOT claim that beauty, originality, marketability, or emotional effect is objectively proven
