## MODIFIED Requirements

### Requirement: Every final closure has a minimum content baseline
Every final route closure SHALL consume the shared current reader chain consisting of ReaderBrief, route composition, SharedWriting binding, route-native actual-artifact review, model-artifact binding, deterministic audit, and independent reader judgment, plus the selected route's native evidence. All shared reader evidence SHALL bind the same final owner, RouteDecision, ReaderIntent, CompositionPlan, and current artifact fingerprint. Revision provenance SHALL be required only when artifact mode is revise-existing and SHALL be explicitly not applicable for create-new artifacts.

#### Scenario: Process is green but content work did not run
- **WHEN** process and release checks pass but any required shared reader-chain evidence is missing, stale, skipped, partial, or failed
- **THEN** final closure remains blocked

#### Scenario: New academic artifact has no source document
- **WHEN** an academic artifact is created from zero
- **THEN** revision provenance is explicitly not applicable and the remaining academic and shared reader baseline determines closure

#### Scenario: Route-native review is missing
- **WHEN** shared reader checks pass but the selected route has not reviewed the current actual artifact
- **THEN** final closure remains blocked

#### Scenario: Academic artifact lacks revision provenance
- **WHEN** an academic artifact and its reader audits are current
- **AND** no current revision-provenance receipt binds every actual source and target unit
- **THEN** academic final closure SHALL NOT pass

### Requirement: Repeated no-progress loops terminate visibly
Closure SHALL derive no-progress only from consecutive current RepairResult receipts for the same selected final owner and defect lineage. A no-progress result SHALL prove that a real repair request was issued and that the artifact bytes did not change or that the blocking defect set remained materially unchanged after a current edit. Repeated closure derivation alone SHALL NOT count as repair.

#### Scenario: Same packet is rejected twice
- **WHEN** no RepairRequest and RepairResult pair exists for the repeated rejection
- **THEN** closure does not increment the no-progress count

#### Scenario: Artifact repair changes no bytes
- **WHEN** a current repair result binds identical input and output artifact fingerprints
- **THEN** one no-progress attempt is recorded

#### Scenario: Two genuine repairs make no progress
- **WHEN** two consecutive current repair results for the same defect lineage record no progress
- **THEN** closure terminates visibly as blocked and identifies the remaining defects and next human or evidence owner

## ADDED Requirements

### Requirement: Reader-chain edits propagate exact staleness
An edit to ReaderIntent, RouteDecision, route content, CompositionPlan, route extension, actual artifact bytes, ArtifactMap, or repair output SHALL stale exactly the dependent ReaderBrief, SharedWriting, deterministic audit, route-native review, ReaderJudgment, and closure evidence. Runtime logs, receipts, and progress outputs SHALL NOT stale their producers.

#### Scenario: Artifact punctuation changes inside a bound span
- **WHEN** current artifact bytes change inside a bound span
- **THEN** the ArtifactMap and every dependent reader-chain receipt become stale

#### Scenario: Unrelated release log changes
- **WHEN** a runtime progress log changes without a governed source or artifact identity change
- **THEN** reader-content evidence remains current

### Requirement: Shared evidence owners are dynamic and route bounded
Shared reader builders and validators MAY execute under the shared reader kernel, but every receipt SHALL bind the selected final owner and SHALL NOT assign Academic as the semantic owner of Investigation, Fiction, or Travel work.

#### Scenario: Travel reader audit is produced
- **WHEN** the shared deterministic auditor checks a travel artifact
- **THEN** the receipt names the travel final owner and shared producer separately

### Requirement: Current closure rejects legacy reader evidence
The current closure SHALL reject legacy ReaderBrief, SharedWriting, audit, judgment, repair, and no-progress shapes and SHALL NOT consume compatibility projections or converted receipts.

#### Scenario: Legacy audit is otherwise passing
- **WHEN** a v1 audit has a passing status but lacks current ReaderIntent, CompositionPlan, and artifact binding identities
- **THEN** closure rejects it as ineligible evidence
