## ADDED Requirements

### Requirement: Every route has a route-native minimum closure baseline
Final closure SHALL require the shared identity, reader projection, actual-artifact audit, and freshness surfaces plus the selected route's declared minimum domain surfaces.

#### Scenario: Shared audit passes but fiction surfaces are absent
- **WHEN** reader-language checks pass but required story contribution, promise, continuity, semantic review, or model-prose binding evidence is missing
- **THEN** fiction final closure SHALL remain blocked or explicitly partial

#### Scenario: Shared audit passes but travel surfaces are absent
- **WHEN** reader-language checks pass but required source-time, feasibility, fit, fallback, or reverse-guide evidence is missing
- **THEN** travel final closure SHALL remain blocked or explicitly downgraded

### Requirement: Child Guard receipts bind exact route inputs
A passing child Guard surface SHALL resolve one immutable native terminal receipt whose tool/schema version, route or check, exact input fingerprint, status, and claim boundary match the current parent request.

#### Scenario: Child status says passed without receipt
- **WHEN** a route submits inline `passed` text or an unresolvable receipt reference
- **THEN** the surface SHALL be unauthoritative and final closure SHALL not consume it

### Requirement: Parent closure consumes current child-model evidence
The FlowGuard parent mesh SHALL consume current evidence identities from routing, research, shared-reader, fiction, travel, operation/freshness, and release children before broad completion or publish claims.

#### Scenario: Fiction child changes after parent pass
- **WHEN** the fiction child boundary, input, output, state ownership, side effect, or evidence identity changes
- **THEN** the parent reattachment and affected sibling assumptions SHALL become stale

### Requirement: Final semantic review is artifact-bound and scope-visible
Judgment-based reader, academic, fiction, and travel reviews SHALL identify the exact artifact, reviewed units, rubric version, evaluator, skipped scope, limitations, blocking findings, and confidence boundary.

#### Scenario: Review praises prose without opening the final artifact
- **WHEN** a semantic review cannot resolve the delivered artifact identity or reviewed unit set
- **THEN** the review SHALL NOT contribute to final closure
