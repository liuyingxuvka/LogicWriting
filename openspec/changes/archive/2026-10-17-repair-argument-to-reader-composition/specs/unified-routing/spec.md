## MODIFIED Requirements

### Requirement: Exactly one final owner
The system SHALL assign exactly one `final_owner` to every non-trivial run. Allowed final owners SHALL be `investigation`, `academic-writing`, `fiction-writing`, and `travel-guide`; child routes, shared kernels, adapters, resource-closure checks, and benchmark judges SHALL NOT become co-owners.

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

#### Scenario: Resource checker completes
- **WHEN** consumer resource closure verifies a selected route stage
- **THEN** it SHALL return evidence for the selected owner and SHALL not become a final route

### Requirement: Required specialist absence blocks domain substitution
The system SHALL preflight every required specialist and SHALL NOT implement an improvised replacement for an unavailable SourceGuard, LogicGuard, TraceGuard, FlowGuard, Documents, PDF authority, or authorized writing execution backend.

#### Scenario: Required provider is unavailable
- **WHEN** a selected route requires a specialist or execution backend that cannot be imported or invoked with its declared capability
- **THEN** the adapter or benchmark runner SHALL return a visible `provider_unavailable` or `execution_provider_unavailable` result
- **AND** Logic Writing SHALL narrow or block the claim instead of simulating the missing specialist or score

### Requirement: Shared kernels never become final routes
The system SHALL treat reader projection, artifact identity, receipt authority, closure composition, consumer resource closure, and benchmark orchestration as shared kernels with no independent terminal success path.

#### Scenario: Shared reader projection finishes
- **WHEN** shared reader projection returns a reader-native artifact
- **THEN** the selected route SHALL still perform its route-native audit and issue or deny final closure

#### Scenario: Benchmark protocol fixture finishes
- **WHEN** a synthetic protocol fixture produces a complete chain
- **THEN** it SHALL remain protocol evidence and SHALL not be emitted as independent quality evidence
