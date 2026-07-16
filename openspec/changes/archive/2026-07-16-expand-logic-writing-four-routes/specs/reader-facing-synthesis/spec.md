## ADDED Requirements

### Requirement: ReaderBrief has a route-neutral base and route extensions
The system SHALL derive a route-neutral ReaderBrief base containing audience, purpose, incoming reader state, concepts, contribution sequence, safe boundaries, and artifact form, then attach only the selected route's extension.

#### Scenario: Fiction receives academic citation fields as mandatory prose instructions
- **WHEN** a route extension is not owned by the selected route
- **THEN** the brief builder SHALL omit it from required projection and SHALL NOT treat its absence as a gap

### Requirement: Reader-facing units expose real handoffs
Every important unit SHALL receive a concrete incoming state and emit a concrete reader-state change, unresolved item, or terminal disposition.

#### Scenario: Handoff says only that the document continues
- **WHEN** a unit interface uses generic wording such as “sets up the next section” without naming the changed knowledge, pressure, choice, evidence, or question
- **THEN** reader-quality validation SHALL reject the handoff as generic

### Requirement: Explanation pressure is a reader-quality finding
The system SHALL flag prose that explains the workflow, section function, intended emotion, or intended conclusion when evidence, action, object, dialogue, sequence, or consequence should carry the meaning.

#### Scenario: Paragraph explains its own job
- **WHEN** reader-facing prose states what the paragraph, section, chapter, or day plan has accomplished instead of delivering that content
- **THEN** the artifact SHALL return to route-native projection or structural repair

### Requirement: Register ownership is explicit
Important technical, institutional, local, quoted, character, and narrator terms SHALL have a supported owner and SHALL NOT drift across voices or evidence roles without justification.

#### Scenario: All voices use the same abstract wording
- **WHEN** several speakers, sources, or narrative layers repeatedly use the same unsupported author-summary register
- **THEN** the audit SHALL report register-owner drift

### Requirement: Variation pressure is effect-aware
The system SHALL review repeated openings, information paths, paragraph functions, explanation modes, emotional temperatures, and endings, while allowing repetition that produces escalation, contrast, inversion, cost, deliberate rhythm, or changed interpretation.

#### Scenario: Repetition has no changed effect
- **WHEN** adjacent units repeat the same contribution and surface rhythm without a declared changed effect
- **THEN** the audit SHALL return the artifact to contribution, interface, or route-native revision

### Requirement: Model-artifact binding uses actual bytes
Important planned rows and actual artifact spans SHALL be linked to the current artifact identity, and a material byte change SHALL stale affected binding and reverse-audit evidence.

#### Scenario: Binding references an older draft
- **WHEN** a passing binding receipt names a different artifact hash from the delivered file
- **THEN** the binding SHALL be stale and SHALL NOT contribute to closure
