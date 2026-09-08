## MODIFIED Requirements

### Requirement: Traveler-native projection uses the shared kernel
The travel route SHALL compile checked route artifacts into lived-sequence prose and an operational appendix through the shared reader-projection kernel without invoking the fiction final route, and SHALL declare the runtime references needed for that route.

#### Scenario: Multi-day guide has no day headings
- **WHEN** a substantive multi-day guide lacks visible day or date headings and day-to-day handoffs
- **THEN** traveler-native validation SHALL fail

#### Scenario: Guide runtime reference is missing
- **WHEN** a selected travel route stage lacks `traveler-native-guide-compiler.md` or another required manifest resource
- **THEN** consumer closure SHALL fail and the travel route SHALL remain unavailable

### Requirement: Travel separates narrative body from operational appendix
The travel CompositionPlan and ArtifactMap SHALL distinguish narrative body, operational appendix, source boundary, and recheck notes. Narrative units SHALL explain route, fit, experience, and decision progression in reader-native prose; operational units MAY use lists and tables for time, transport, booking, lodging, load, prices, risk triggers, fallbacks, and rechecks. Copied example guide正文 associations SHALL be resolved during consumer closure.

#### Scenario: Appendix contains bullet lists
- **WHEN** an operational appendix contains transport and booking bullets
- **THEN** the bullets are checked for completeness and actionability but are excluded from narrative-body fragmentation metrics

#### Scenario: Body is only cards
- **WHEN** the narrative body is dominated by short labeled fragments or one-sentence itinerary cards
- **THEN** travel review requires prose integration

#### Scenario: Example guide正文 is absent
- **WHEN** a copied travel example JSON points to a missing guide正文
- **THEN** consumer closure SHALL fail with the JSON path and missing正文 path
