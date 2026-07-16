## ADDED Requirements

### Requirement: Investigation units change reader state
Every important finding, section, and conclusion SHALL identify its incoming reader state, new contribution, and downstream consumer or terminal disposition.

#### Scenario: Fluent section changes nothing
- **WHEN** a section repeats known information without a new distinction, evidence role, limitation, or consequence
- **THEN** the actual-artifact audit SHALL mark the unit as repeated contribution

### Requirement: Investigation tracks negative evidence and recovery choices
The investigation route SHALL preserve material evidence against the preferred conclusion, observations that would change the conclusion, and a named fallback conclusion or recheck condition when discrimination remains incomplete.

#### Scenario: Preferred explanation remains uncertain
- **WHEN** available evidence cannot discriminate between two live explanations
- **THEN** both explanations SHALL remain visible
- **AND** the report SHALL state the evidence or future observation needed to choose between them

### Requirement: Investigation binds model rows to actual prose
Principal findings, critical qualifications, and alternative conclusions SHALL bind to current spans or units in the actual delivered artifact.

#### Scenario: Model limitation is absent from prose
- **WHEN** a critical model limitation has no current artifact binding
- **THEN** final investigation closure SHALL be blocked or the affected claim SHALL be downgraded
