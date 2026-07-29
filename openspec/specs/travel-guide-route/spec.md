# travel-guide-route Specification

## Purpose
TBD - created by archiving change expand-logic-writing-four-routes. Update Purpose after archive.
## Requirements
### Requirement: Travel route owns deep traveler-facing guides
The `travel-guide` route SHALL own substantive itineraries, route alternatives, destination guides, lodging strategy, traveler-fit recommendations, traveler-native prose, and final-guide closure.

#### Scenario: Travel-industry paper is requested
- **WHEN** the terminal artifact is an academic analysis rather than an itinerary or traveler guide
- **THEN** `travel-guide` SHALL NOT become the final owner

### Requirement: Travel evidence is time-mode aware
Every time-sensitive source SHALL record source date, coverage period, inspection status, freshness, date relation, applicable claim level, and recheck trigger. Forecast, alert, historical, climate, and undated evidence SHALL NOT substitute for one another.

#### Scenario: Historical weather supports day-of claim
- **WHEN** historical or climate evidence is used as the only support for a day-of weather claim
- **THEN** the claim SHALL be blocked or downgraded to a planning boundary

### Requirement: Travel routes are feasible and fit the traveler
Candidate and assembled-route validation SHALL check time, space, transport, access, resources, weather, closure, pace, stamina, companions, interests, budget, rest, safety, lodging, and relevant accessibility or travel-style constraints.

#### Scenario: Attractive route exceeds available time
- **WHEN** movement and dwell-time evidence cannot fit the declared day window
- **THEN** the route SHALL be revised, shortened, or blocked

### Requirement: Negative evidence and reachable fallbacks remain visible
Every material risk, closure, weather branch, capacity limit, or rejected candidate SHALL have a disposition, and every required fallback SHALL name a concrete reachable replacement or route-shortening action.

#### Scenario: Fallback says only rest or shop
- **WHEN** a material failure branch names only a generic activity without a supported nearby candidate or shortening action
- **THEN** fallback validation SHALL remain partial or blocked

### Requirement: Travel recommendation support precedes prose
LogicGuard support review SHALL compare the recommended route with live alternatives and limitations before shared reader projection; polished prose SHALL NOT strengthen feasibility, fit, freshness, or source status.

#### Scenario: Story-shaped route hides a closure
- **WHEN** traveler-facing prose omits a current material closure, queue, transport, safety, fatigue, cost, or access limitation
- **THEN** reverse-guide review SHALL fail and return to the owning travel surface

### Requirement: Traveler-native projection uses the shared kernel
The travel route SHALL compile checked route artifacts into lived-sequence prose and an operational appendix through the shared reader-projection kernel without invoking the fiction final route.

#### Scenario: Multi-day guide has no day headings
- **WHEN** a substantive multi-day guide lacks visible day or date headings and day-to-day handoffs
- **THEN** traveler-native validation SHALL fail

### Requirement: Final travel closure binds the actual guide
The final guide SHALL be repository-contained, content-addressed, tied to the same trip id and allowed claim level, and reverse-reviewed from the delivered bytes for evidence, feasibility, fit, fallbacks, headings, weather boundaries, local texture, and reader-room leakage.

#### Scenario: Reverse review covers another guide
- **WHEN** the reverse-guide receipt names a different path, hash, or trip id
- **THEN** final travel closure SHALL fail

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
