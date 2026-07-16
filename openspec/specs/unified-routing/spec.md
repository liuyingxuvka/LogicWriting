# unified-routing Specification

## Purpose
TBD - created by archiving change create-logic-writing. Update Purpose after archive.
## Requirements
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

### Requirement: Mixed-route work uses bounded child requests
An academic owner SHALL invoke investigation only through a bounded evidence-gap request that identifies the gap, affected claim or artifact unit, required evidence role and strength, allowed access policy, safe interim wording, and unsafe boundary.

#### Scenario: Academic evidence gap opens a child investigation
- **WHEN** an academic artifact contains a critical unsupported claim
- **THEN** the academic route SHALL create a bounded child investigation request
- **AND** investigation SHALL return a packet tied to the same `gap_id`
- **AND** investigation SHALL NOT edit or close the academic artifact

#### Scenario: Child route attempts final closure
- **WHEN** an investigation child result claims the academic task is complete
- **THEN** the parent SHALL reject that closure claim
- **AND** preserve only the child evidence artifacts, safe wording, and unresolved gaps

### Requirement: Route decisions are fingerprinted
Every route decision SHALL bind to the current user request, terminal deliverable, scope, and acceptance criteria and SHALL become stale when any of those inputs materially changes.

#### Scenario: User changes report into a paper
- **WHEN** the requested deliverable changes from a general report to an academic paper
- **THEN** the previous route decision SHALL become `stale`
- **AND** a new decision SHALL select `academic-writing`

#### Scenario: Execution order changes without deliverable change
- **WHEN** only the order of research and drafting changes while the final deliverable remains an academic paper
- **THEN** the final owner SHALL remain `academic-writing`

### Requirement: Ambiguity remains explicit
If the terminal deliverable cannot be determined safely, the system SHALL ask one focused question or return `needs_human_review`; it SHALL NOT activate both routes as a fallback.

#### Scenario: Ambiguous research piece
- **WHEN** the user asks for a research piece without enough information to distinguish a general report from an academic artifact
- **THEN** the system SHALL request only the information needed to identify the terminal deliverable
- **AND** SHALL NOT assign two owners

### Requirement: Trivial and out-of-scope work does not activate
The system SHALL skip the unified workflow for quick factual lookups, grammar-only edits, formatting-only edits, and casual summaries with no meaningful evidence or structure risk.

#### Scenario: Grammar-only edit
- **WHEN** the user requests only grammar correction for a short paragraph
- **THEN** route selection SHALL return `skip_with_reason`
- **AND** neither route SHALL activate

#### Scenario: Source-sensitive question
- **WHEN** the user requests a source-backed answer involving contested evidence, causality, execution, or major uncertainty
- **THEN** the system SHALL activate `investigation`

### Requirement: Required specialist absence blocks domain substitution
The system SHALL preflight every required specialist and SHALL NOT implement an improvised replacement for an unavailable SourceGuard, LogicGuard, TraceGuard, FlowGuard, Documents, or PDF authority.

#### Scenario: Required provider is unavailable
- **WHEN** a selected route requires a specialist that cannot be imported or invoked with its declared capability
- **THEN** the adapter SHALL return `provider_unavailable`
- **AND** Logic Writing SHALL narrow or block the claim instead of simulating the missing specialist

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
