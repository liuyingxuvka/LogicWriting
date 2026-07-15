## ADDED Requirements

### Requirement: Release validation survives change archival
The repository SHALL maintain exactly one current release verification contract at a stable path outside every active or archived OpenSpec change directory. Every live release consumer SHALL bind that exact path. Change-local verification contracts SHALL remain scoped to their own active change, and archived contracts SHALL be historical evidence only; live consumers SHALL NOT search active and archived locations, use aliases, or fall back between them.

#### Scenario: An active change is archived
- **WHEN** OpenSpec moves a verified change from its active directory to the archive
- **THEN** the current release contract and every live consumer SHALL remain at the same path
- **AND** a live-source scan SHALL find no reference to the former active change contract
- **AND** archived historical files MAY preserve their original path statements without becoming current authority

#### Scenario: A live consumer references an active change contract
- **WHEN** a wrapper, test, model, TestMesh, instruction, or commitment lookup uses a path beneath `openspec/changes/<change-id>/verification-contract.yaml`
- **THEN** the post-archive release gate SHALL fail
- **AND** the consumer SHALL be repaired to use the stable current contract directly

### Requirement: Archival changes release source identity
OpenSpec archival SHALL be treated as a governed source transition that invalidates pre-archive repository-wide release confidence. After archival and before tagging, the exact archived source snapshot SHALL pass the complete repository test suite, current FlowGuard model/alignment/TestMesh checks, strict validation of all current OpenSpec authority, and public-source, privacy, and release-surface gates. A pre-archive pass SHALL NOT substitute for this post-archive evidence.

#### Scenario: Pre-archive verification is green
- **WHEN** every active-change verification owner passes
- **AND** the change is then archived
- **THEN** the release SHALL remain blocked until the post-archive full gate passes on the changed source snapshot

#### Scenario: Post-archive regression fails
- **WHEN** any complete-suite, FlowGuard, OpenSpec, privacy, public-source, or release-surface check fails after archival
- **THEN** no tag or GitHub Release SHALL be created from that snapshot
- **AND** the failure SHALL be repaired and the affected post-archive owners rerun

### Requirement: Published release identities are immutable
A published tag or GitHub Release SHALL NOT be moved, replaced, or deleted to conceal a later validation failure. A repair SHALL use a strictly higher version and SHALL identify the corrected boundary.

#### Scenario: A fresh clone exposes a missed failure
- **WHEN** a published release later fails a required fresh-clone or post-archive check
- **THEN** its tag and release SHALL remain unchanged
- **AND** the corrected snapshot SHALL be published under a higher patch version only after current full evidence passes
