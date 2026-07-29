## ADDED Requirements

### Requirement: Fiction distinguishes planning, audit, mixed, and reader-native prose
The fiction route SHALL classify the requested output room before applying prose gates. Story plans, audits, and series bibles may use functional lists and tables; only reader-native short story, chapter, novella, or novel prose SHALL require manuscript composition and prose-quality closure.

#### Scenario: Series bible uses tables
- **WHEN** the final artifact is a series bible rather than story prose
- **THEN** functional tables are allowed and manuscript-naturalness gates are not misapplied

#### Scenario: Final chapter is requested
- **WHEN** the terminal artifact is reader-native chapter prose
- **THEN** the fiction route requires story movement, manuscript binding, route-native semantic review, and repair closure

### Requirement: Fiction composition plans story movements rather than model-row paragraphs
Reader-native fiction SHALL plan complete scenes, scene groups, chapters, or other explicit units with entry and exit story state, focal desire, resistance or cost, reader-state movement, open questions, promises and reveals, voice or register ownership, rhythm role, prohibited reveals, and exact downstream consumers. Several model rows MAY contribute to one story movement.

#### Scenario: Smooth scene has no change
- **WHEN** a scene contains polished prose but no resistance, cost, discovery, choice, or state change required by its plan
- **THEN** fiction review records a route-native defect

### Requirement: Fiction evidence binds real manuscript spans
Chapter interfaces, semantic review, model-prose bindings, promises, reveals, continuity, point of view, and voice observations SHALL bind existing current manuscript unit ids, locators, excerpts, and span fingerprints. Nonexistent draft references or bare chapter labels SHALL NOT count as evidence.

#### Scenario: Chapter reference does not exist
- **WHEN** an interface or review points to a draft path or span absent from the current manuscript map
- **THEN** validation fails even if the JSON declares pass

#### Scenario: Manuscript edit moves a scene
- **WHEN** current bytes or unit boundaries change
- **THEN** affected fiction bindings and reviews become stale

### Requirement: Fiction repair returns to the semantic owner
Fiction repair SHALL route workflow leakage and card-like prose to integration, voice or register drift to voice ownership, missing resistance or state change to scene or chapter composition, promise or payoff defects to promise ownership, reveal-order defects to chapter interfaces, and world or canon conflicts to their native Guard owner.

#### Scenario: Continuity is repaired with one connector sentence
- **WHEN** two story units still lack the required state handoff after a connector sentence is added
- **THEN** the repair records no progress and the route remains open
