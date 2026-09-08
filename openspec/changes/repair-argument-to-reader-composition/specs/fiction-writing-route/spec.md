## MODIFIED Requirements

### Requirement: Fiction depth is explicit
The route SHALL select a compact, full-guarded, or longform depth from artifact scope and requested claim, SHALL expose the depth-specific references required by that selection, and SHALL NOT use compact evidence to claim longform or final-manuscript closure.

#### Scenario: Short prompt requests a premise audit
- **WHEN** the artifact and claim are compact and no final prose is requested
- **THEN** compact evidence MAY satisfy the bounded planning claim
- **AND** the consumer SHALL not load longform-only references

#### Scenario: Final novel prose is requested
- **WHEN** the route claims final chapter, volume, book, or series prose
- **THEN** longform artifact, mesh, binding, continuity, semantic-review, closure, and their declared references SHALL be current

### Requirement: Fiction evidence binds real manuscript spans
Chapter interfaces, semantic review, model-prose bindings, promises, reveals, continuity, point of view, and voice observations SHALL bind existing current manuscript unit ids, locators, excerpts, and span fingerprints. Nonexistent draft references or bare chapter labels SHALL NOT count as evidence; every selected route reference required by the consumer manifest SHALL also be present.

#### Scenario: Chapter reference does not exist
- **WHEN** an interface or review points to a draft path or span absent from the current manuscript map
- **THEN** validation fails even if the JSON declares pass

#### Scenario: Required prose reference is missing in a stage
- **WHEN** final prose is selected and `prose-native-contract.md` is absent from the staged consumer
- **THEN** consumer closure fails before route success can be reported
