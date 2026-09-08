## MODIFIED Requirements

### Requirement: ReaderBrief carries content and boundaries

A ReaderBrief SHALL include the reader question, audience, genre, necessary
concepts, principal findings or argument, evidence anchors and source roles,
material limitations and alternatives, old-to-new sequence, required
citations, allowed wording, prohibited overclaim wording, and a hash-bound
`writer_input` view of the selected CompositionPlan. It SHALL exclude execution
instructions, raw status ledgers, private receipts, and model diagnostics from
that writer view.

#### Scenario: Writer receives raw ledger only
- **WHEN** the prose writer receives only diagnostic or closure records
- **THEN** reader-facing synthesis SHALL be `blocked`
- **AND** a ReaderBrief and controlled writer projection SHALL be generated first

#### Scenario: Brief omits a material limitation
- **WHEN** a current specialist receipt narrows an important claim but the ReaderBrief omits that boundary
- **THEN** ReaderBrief validation SHALL fail
- **AND** the writer SHALL not receive the stronger claim

#### Scenario: Route projection carries the selected reader job
- **WHEN** the selected route is academic, fiction, investigation, or travel
- **THEN** `writer_input` SHALL contain that route's reader-facing contribution, sequence, and applicable obligations
- **AND** it SHALL not contain unrelated sibling-route instructions

## ADDED Requirements

### Requirement: Editorial material dispositions preserve useful boundaries

Every native limitation and candidate content item SHALL receive a disposition
of `body`, `note`, `appendix`, `internal_only`, `implied_by_scope`, `omitted`, or
`blocked`, with materiality, reason, affected units, and native boundary
references. A material boundary that changes answer, action, scope, or claim
strength MUST remain visible in the reader artifact or in a genuinely narrowed
claim.

#### Scenario: Process-only limits are consolidated
- **WHEN** many process-only limitations affect no reader decision
- **THEN** they MAY be accounted for in one internal disposition or suitable note
- **AND** the body SHALL not grow one disclaimer per limitation

#### Scenario: Substantive boundary is omitted
- **WHEN** a limitation changes the answer, action, scope, or strength of a claim
- **THEN** `internal_only` or `omitted` SHALL be rejected

### Requirement: Whole-artifact composition precedes drafting

The selected route SHALL produce one acyclic CompositionPlan whose ordered
reader units cover required structure, content obligations, dependencies,
reader-state handoffs, positions, and applicable review obligations. A writer
MUST consume this plan and MUST NOT fall back to an implicit top-N list.

#### Scenario: Findings become one shallow card each
- **WHEN** a plan creates one paragraph for each model finding without reader or downstream justification
- **THEN** composition validation SHALL fail or require consolidation

#### Scenario: Fixed structure conflicts with route default
- **WHEN** the user supplies a required outline that differs from a route default
- **THEN** the user outline SHALL remain authoritative or a visible conflict SHALL block drafting

### Requirement: Actual text and independent execution evidence close quality

Deterministic audits SHALL rederive results from the current artifact bytes and
hash-bound maps. Qualitative judgment SHALL use actual text and an execution
record that identifies the real writer/judge contexts and inputs. Protocol
fixtures and missing provider executions SHALL never enter the real quality
success domain.

#### Scenario: Passing metadata hides stale text
- **WHEN** an audit declares pass but its artifact or input fingerprints differ from current bytes
- **THEN** the audit SHALL be rejected as stale

#### Scenario: Same context is used for writer and judge
- **WHEN** writer and judge records have different labels but the same execution context
- **THEN** independence SHALL be unverified and closure SHALL remain blocked
