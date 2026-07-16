## MODIFIED Requirements

### Requirement: Exactly one final owner
The system SHALL assign exactly one `final_owner` to every non-trivial run. Allowed final owners SHALL be `investigation`, `academic-writing`, `fiction-writing`, and `travel-guide`; child routes, shared kernels, and adapters SHALL NOT become co-owners.

#### Scenario: Investigation report selects investigation owner
- **WHEN** the terminal deliverable is a research report, briefing, memo, evidence audit, policy analysis, market analysis, or case investigation
- **THEN** `final_owner` SHALL be `investigation`
- **AND** no other route SHALL be registered as a final owner

#### Scenario: Academic artifact selects academic owner
- **WHEN** the terminal deliverable is a paper, thesis, dissertation, academic chapter, proposal, formal literature review, or revision of an existing academic artifact
- **THEN** `final_owner` SHALL be `academic-writing`
- **AND** `investigation` MAY be registered only as a child evidence route

#### Scenario: Fiction artifact selects fiction owner
- **WHEN** the terminal deliverable is a short story, novel, chapter, fiction outline, story audit, or substantive fiction revision
- **THEN** `final_owner` SHALL be `fiction-writing`
- **AND** source investigation MAY be registered only as a bounded child request

#### Scenario: Travel guide selects travel owner
- **WHEN** the terminal deliverable is an itinerary, destination guide, lodging strategy, route plan, or traveler-fit recommendation
- **THEN** `final_owner` SHALL be `travel-guide`
- **AND** shared narrative projection SHALL NOT transfer ownership to `fiction-writing`

#### Scenario: Multiple owner declaration is rejected
- **WHEN** a route decision declares more than one final owner
- **THEN** route validation SHALL return `blocked`
- **AND** no downstream route SHALL begin

### Requirement: Route by terminal deliverable
The system SHALL choose the final owner from the terminal deliverable, not from the first activity performed or a shared presentation technique.

#### Scenario: Academic paper begins with research
- **WHEN** a request asks for a new academic paper and the first required activity is source investigation
- **THEN** `academic-writing` SHALL remain the final owner
- **AND** `investigation` SHALL return a bounded evidence packet to that owner

#### Scenario: Investigation report includes polished writing
- **WHEN** a request asks for a general investigation report with polished prose
- **THEN** `investigation` SHALL remain the final owner
- **AND** prose polishing SHALL NOT transfer ownership to `academic-writing`

#### Scenario: Historical novel requires research
- **WHEN** a historical novel needs factual or source research before drafting
- **THEN** `fiction-writing` SHALL remain the final owner
- **AND** investigation SHALL close only its bounded evidence request

#### Scenario: Travel guide requests story-shaped prose
- **WHEN** an itinerary asks for a story-shaped traveler experience
- **THEN** `travel-guide` SHALL remain the final owner
- **AND** the route SHALL consume the shared reader-projection kernel rather than invoke `fiction-writing`

#### Scenario: Travel-industry paper is academic
- **WHEN** the subject is travel but the terminal deliverable is an academic paper
- **THEN** `academic-writing` SHALL be the final owner

## ADDED Requirements

### Requirement: Shared kernels never become final routes
The system SHALL treat reader projection, artifact identity, receipt authority, and closure composition as shared kernels with no independent terminal success path.

#### Scenario: Shared reader projection finishes
- **WHEN** shared reader projection returns a reader-native artifact
- **THEN** the selected route SHALL still perform its route-native audit and issue or deny final closure

### Requirement: WorldGuard authority is preserved
The system SHALL use WorldGuard for material event, agent, space, resource, capability, conflict, authority, and norm consistency without reimplementing those judgments in a route validator.

#### Scenario: Fictional world consistency is material
- **WHEN** a fiction or travel route depends on a material world claim
- **THEN** the route SHALL consume a current WorldGuard result or preserve a typed non-pass boundary
