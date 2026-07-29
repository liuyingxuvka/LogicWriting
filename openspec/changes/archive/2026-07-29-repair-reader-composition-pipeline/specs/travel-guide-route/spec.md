## ADDED Requirements

### Requirement: Travel selects a guide kind before composition
The travel route SHALL select itinerary, destination guide, lodging strategy, route plan, traveler-fit recommendation, or revision before applying structure requirements. Only a multi-day itinerary SHALL require day units; other guide kinds SHALL use their reader task and user structure.

#### Scenario: Lodging strategy is requested
- **WHEN** the terminal deliverable compares lodging options for a traveler
- **THEN** the plan uses needs, criteria, options, trade-offs, recommendation, and conditions rather than artificial day headings

#### Scenario: Fixed itinerary is revised
- **WHEN** artifact mode is revise-existing with locked day headings
- **THEN** the route preserves those headings and records source-to-target unit treatments

### Requirement: Travel separates narrative body from operational appendix
The travel CompositionPlan and ArtifactMap SHALL distinguish narrative body, operational appendix, source boundary, and recheck notes. Narrative units SHALL explain route, fit, experience, and decision progression in reader-native prose; operational units MAY use lists and tables for time, transport, booking, lodging, load, prices, risk triggers, fallbacks, and rechecks.

#### Scenario: Appendix contains bullet lists
- **WHEN** an operational appendix contains transport and booking bullets
- **THEN** the bullets are checked for completeness and actionability but are excluded from narrative-body fragmentation metrics

#### Scenario: Body is only cards
- **WHEN** the narrative body is dominated by short labeled fragments or one-sentence itinerary cards
- **THEN** travel review requires prose integration

### Requirement: Travel local texture uses current route candidates
Local names and texture SHALL be validated from current candidate names, local-language names, accepted aliases, categories, and intended sections rather than a fixed English keyword list. The route SHALL NOT invent local detail to satisfy prose quality.

#### Scenario: Chinese guide uses local-language names
- **WHEN** approved Chinese or local-language place and food names appear in their intended sections
- **THEN** they satisfy local-texture placement without requiring English category words

### Requirement: Travel risks and fallbacks form executable bindings
Every material risk and fallback SHALL bind a risk id, affected day or section, trigger, affected traveler, mitigation, reachable fallback, evidence or time mode, and current artifact span. It SHALL be possible to recover the decision relation from the body or appendix.

#### Scenario: Risk and fallback appear in unrelated locations
- **WHEN** a risk word appears in one day and an unbound fallback appears at the document end
- **THEN** the route does not treat them as a valid executable pair

### Requirement: Travel final review is guide-kind and zone aware
Travel closure SHALL review current spans for guide-kind structure, traveler fit, distinct unit responsibilities, natural handoffs, narrative-body clarity, operational completeness, body or appendix role confusion, risk and fallback decisions, source and recheck boundaries, and template or checklist prose.

#### Scenario: Destination guide passes itinerary checks only
- **WHEN** a destination guide has no day headings but satisfies its selected profile and user structure
- **THEN** it may pass without itinerary-only requirements
