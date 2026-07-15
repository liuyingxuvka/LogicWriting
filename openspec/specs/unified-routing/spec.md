# unified-routing Specification

## Purpose
TBD - created by archiving change create-logic-writing. Update Purpose after archive.
## Requirements
### Requirement: Exactly one final owner
The system SHALL assign exactly one `final_owner` to every non-trivial run. Allowed final owners SHALL be `investigation` and `academic-writing`; child routes and adapters SHALL NOT become co-owners.

#### Scenario: Investigation report selects investigation owner
- **WHEN** the terminal deliverable is a research report, briefing, memo, evidence audit, policy analysis, market analysis, or case investigation
- **THEN** `final_owner` SHALL be `investigation`
- **AND** `academic-writing` SHALL NOT be registered as a final owner

#### Scenario: Academic artifact selects academic owner
- **WHEN** the terminal deliverable is a paper, thesis, dissertation, academic chapter, proposal, formal literature review, or revision of an existing academic artifact
- **THEN** `final_owner` SHALL be `academic-writing`
- **AND** `investigation` MAY be registered only as a child evidence route

#### Scenario: Dual owner declaration is rejected
- **WHEN** a route decision declares both routes as final owners
- **THEN** route validation SHALL return `blocked`
- **AND** no downstream route SHALL begin

### Requirement: Route by terminal deliverable
The system SHALL choose the final owner from the terminal deliverable, not from the first activity performed.

#### Scenario: Academic paper begins with research
- **WHEN** a request asks for a new academic paper and the first required activity is source investigation
- **THEN** `academic-writing` SHALL remain the final owner
- **AND** `investigation` SHALL return a bounded evidence packet to that owner

#### Scenario: Investigation report includes polished writing
- **WHEN** a request asks for a general investigation report with polished prose
- **THEN** `investigation` SHALL remain the final owner
- **AND** prose polishing SHALL NOT transfer ownership to `academic-writing`

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
