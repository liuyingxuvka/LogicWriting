## MODIFIED Requirements

### Requirement: Revision provenance is preserved
The academic route SHALL declare `artifact_mode`. When the mode is `revise_existing`, every materially affected source unit SHALL bind to current target unit ids and a treatment such as preserved, rewritten, moved, split, merged, or omitted, together with authorization and meaning or structure delta. When the mode is `create_new`, revision provenance SHALL be explicitly not applicable and SHALL NOT be fabricated.

#### Scenario: Existing paragraph is materially rewritten
- **WHEN** an existing thesis paragraph is revised
- **THEN** provenance binds the source unit to the current target units and records its treatment and material delta

#### Scenario: From-zero paper is drafted
- **WHEN** no source artifact exists and artifact mode is create-new
- **THEN** revision provenance is explicitly not applicable and does not block closure

#### Scenario: Style polish overwrites provenance
- **WHEN** a later edit changes a target unit after provenance was recorded
- **THEN** the affected provenance and downstream artifact evidence become stale

## ADDED Requirements

### Requirement: Academic composition is profile-aware and hierarchical
Before broad drafting or revision, the academic route SHALL select an empirical paper, conceptual argument, literature synthesis, research proposal, chapter or section, or user-defined profile and SHALL plan document, chapter, section, subsection, paragraph-group, figure, and table duties as applicable. Every important unit SHALL state its research-question contribution, incoming dependency, new claim or warrant, evidence, qualification, and downstream consumer.

#### Scenario: Literature review lists authors
- **WHEN** the planned literature review is organized only as one unit per author without a dispute, progression, comparison, or contribution relation
- **THEN** academic composition validation requires restructuring before drafting

#### Scenario: Method section is shallow
- **WHEN** a method section lists steps but does not establish why the method answers the research question or its boundary
- **THEN** the unit remains under-modeled and cannot close

### Requirement: Academic final review opens the actual artifact
Academic closure SHALL require route-native review of the current artifact hierarchy and spans for research-question recovery, central contribution, section progression, paragraph contribution, evidence and citation semantics, method depth, figure or table jobs, qualifications, implications, and reader-state handoffs.

#### Scenario: Fluent section is structurally unused
- **WHEN** a polished section does not contribute to its declared parent or downstream argument
- **THEN** route-native review records an orphan or overloaded unit and requires repair

#### Scenario: Figure is present without an argumentative job
- **WHEN** a current figure or table is not consumed by a claim, method, result, or decision unit
- **THEN** academic review does not treat its presence as successful integration

### Requirement: Academic prose may synthesize several modeled contributions
The academic route SHALL preserve model and evidence identity while allowing one paragraph group or section to synthesize several compatible content units. It SHALL NOT require safe model wording to appear verbatim unless a genuine exact-preservation duty applies.

#### Scenario: Natural synthesis preserves support
- **WHEN** a paragraph integrates several supported claims and keeps citations and qualifications correctly placed
- **THEN** it may pass without repeating the model sentences
