# evidence-freshness-closure Specification

## Purpose
TBD - created by archiving change create-logic-writing. Update Purpose after archive.
## Requirements
### Requirement: Closure status is verifier-derived
The system SHALL derive closure from current specialist receipts and artifact identities. Caller-authored status fields SHALL be treated as claims, not evidence.

#### Scenario: Ledger self-reports pass
- **WHEN** a ledger reports every check as passed
- **AND** one or more required native receipts are absent
- **THEN** final closure SHALL ignore the self-reported statuses
- **AND** return `partial`, `downgraded`, or `blocked`

### Requirement: Every final closure has a minimum content baseline
Final closure SHALL require route-specific content and reader evidence even when the caller does not request broad, comprehensive, final, or publication-ready wording. Investigation closure SHALL require current source-observation, argument-model, ReaderBrief, deterministic actual-artifact audit, and independent reader-judgment receipts. Academic closure SHALL require current argument-model, source-unit-to-target-unit revision provenance, ReaderBrief, deterministic actual-artifact audit, and independent reader-judgment receipts. Process, routing, or layout receipts SHALL NOT replace this baseline.

#### Scenario: Process is green but content work did not run
- **WHEN** routing and FlowGuard process checks pass
- **AND** the route-specific source, argument, provenance, or reader evidence is absent
- **AND** broad claim wording was not requested
- **THEN** final closure SHALL still return `blocked` or `partial`
- **AND** identify the missing content owner

#### Scenario: Academic artifact lacks revision provenance
- **WHEN** an academic artifact and its reader audits are current
- **AND** no current revision-provenance receipt binds every actual source and target unit
- **THEN** academic final closure SHALL NOT pass

### Requirement: Every receipt has exact identity
A receipt SHALL contain producer skill and native route, run id, covered obligation ids, exact input and output fingerprints, artifact fingerprint when applicable, covered scope, evidence domain, actual status, safe claim, unsafe claim boundary, sequence identity, and receipt fingerprint.

#### Scenario: Receipt lacks input fingerprint
- **WHEN** a receipt does not identify the exact source, model, packet, brief, artifact, or render it checked
- **THEN** it SHALL be rejected as unauthoritative

#### Scenario: Receipt belongs to another artifact
- **WHEN** a passing receipt was produced for a different artifact fingerprint
- **THEN** it SHALL not contribute to current closure

#### Scenario: Well-shaped receipt has no authority original
- **WHEN** caller-supplied JSON matches the Receipt schema but its exact content-addressed original, store attestation, and latest-owner pointer cannot be resolved
- **THEN** it SHALL be rejected as unauthoritative
- **AND** SHALL NOT be reconstructed, aliased, or accepted from its shape

#### Scenario: Caller tries to rewind currentness
- **WHEN** an input changed after a receipt was produced
- **AND** a caller supplies the old input fingerprint while resolving that receipt
- **THEN** currentness SHALL still be derived from the authority store's current-input projection
- **AND** the stale receipt SHALL remain stale

### Requirement: Passing receipts use managed builders
A generic passing Receipt SHALL be created only by a current managed builder that binds the exact native or Logic Writing check artifact. The builder SHALL persist the immutable original and attestation atomically before advancing the latest owner pointer.

#### Scenario: Caller authors current pass JSON
- **WHEN** a caller constructs a `current_pass` Receipt without the managed builder path
- **THEN** it SHALL NOT enter terminal authority

#### Scenario: Native adapter result is wrapped
- **WHEN** a specialist adapter result is promoted into a generic Receipt
- **THEN** the Receipt output manifest SHALL bind the exact native receipt fingerprint and exact adapter-result fingerprint
- **AND** a different native payload SHALL make the generic Receipt invalid or stale

### Requirement: Material changes invalidate dependent evidence
The system SHALL maintain explicit dependency edges between sources, packets, models, story plans, ReaderBriefs, final artifacts, renders, audits, and closures.

#### Scenario: Source registry changes
- **WHEN** a source record, locator, role, date, lineage, or support boundary changes
- **THEN** dependent claim-fit, packet, synthesis, prose, citation, and closure receipts SHALL become stale

#### Scenario: Final DOCX changes
- **WHEN** a DOCX changes after rendering or review
- **THEN** render, page-inspection, postwrite, and final-closure receipts SHALL become stale

#### Scenario: Runtime report changes only
- **WHEN** only a derived progress report, log, receipt, or timestamp changes
- **THEN** source authority SHALL NOT become stale unless that output is an explicitly declared functional input

### Requirement: Failure states propagate monotonically
A dependent final claim SHALL be no stronger than the weakest unresolved important obligation. The system SHALL NOT convert `not_run`, `stale`, `provider_unavailable`, `access_gap`, `render_not_run`, `bounded`, `downgraded`, or `blocked` into `passed`.

#### Scenario: Critical counter search is not run
- **WHEN** all other checks pass but a required counterevidence search is `not_run`
- **THEN** complete investigation closure SHALL be prohibited

#### Scenario: Optional item is skipped
- **WHEN** an optional non-critical check is skipped with a valid verifier-owned reason
- **THEN** closure MAY pass only when the item is outside the requested claim scope
- **AND** the skip SHALL remain visible

### Requirement: Planning artifacts cannot satisfy proof obligations
Search plans, candidates, utility scores, outlines, story plans, progress logs, and check manifests SHALL NOT satisfy factual, semantic, rendered-artifact, reader-quality, or final-closure obligations.

#### Scenario: Candidate source is used as proof
- **WHEN** a candidate-source artifact is supplied as factual evidence
- **THEN** closure SHALL reject the substitution

#### Scenario: Story plan is used as final prose audit
- **WHEN** an artifact-synthesis plan is supplied instead of an audit of actual final text
- **THEN** reader-facing and academic closure SHALL remain `not_run`

### Requirement: Native owners remain authoritative
SourceGuard SHALL own source planning and source-depth evidence; TraceGuard SHALL own temporal, causal, competing-storyline, and perturbation evidence; LogicGuard SHALL own argument, structural, citation-semantic, and model-depth evidence; Documents and PDF SHALL own file mutation and visual evidence; FlowGuard SHALL own process order and freshness evidence. Logic Writing SHALL consume these receipts and SHALL NOT recreate their domain decisions.

#### Scenario: FlowGuard is green but LogicGuard is not run
- **WHEN** FlowGuard reports current process evidence
- **AND** a required LogicGuard semantic audit is `not_run`
- **THEN** final content closure SHALL not pass

#### Scenario: Logic Writing fabricates source qualification
- **WHEN** Logic Writing labels a source claim-usable without a current source observation and semantic-fit receipt
- **THEN** evidence validation SHALL return `blocked`

#### Scenario: Unrelated observation receipt is reused
- **WHEN** a current SourceGuard receipt covers different observed bytes, anchors, or support boundaries than the source record that cites it
- **THEN** the source SHALL NOT become claim-usable

#### Scenario: Unrelated semantic receipt is reused
- **WHEN** a current LogicGuard receipt does not bind the exact claim, source-registry fingerprint, support links, safe wording, and unsafe boundary that cite it
- **THEN** the claim SHALL NOT contribute to a passing packet or ReaderBrief

### Requirement: Only the final owner issues final closure
Child routes and adapters SHALL issue bounded receipts only.

#### Scenario: Investigation child succeeds
- **WHEN** an investigation child returns a passing packet to an academic parent
- **THEN** the child SHALL close only its requested gap scope
- **AND** academic final closure SHALL remain with `academic-writing`

#### Scenario: Document render passes
- **WHEN** Documents reports a flawless current render
- **THEN** that receipt SHALL satisfy only document-layout obligations
- **AND** SHALL NOT satisfy argument, source, reader-facing, or academic completion obligations

### Requirement: Broad claims require broad current receipts
Words such as complete, comprehensive, deep, conclusive, robust, final, publication-ready, and submission-ready SHALL require current broad-scope native receipts for every applicable important domain.

#### Scenario: Native receipt is bounded
- **WHEN** SourceGuard, TraceGuard, or LogicGuard returns a bounded receipt
- **THEN** broad final wording SHALL be prohibited
- **AND** final wording SHALL match the covered scope

#### Scenario: All broad receipts are current
- **WHEN** every applicable important domain has a current passing broad receipt
- **AND** no critical gap, stale artifact, missing render, or unresolved owner remains
- **THEN** the final owner MAY issue broad closure for the declared scope

### Requirement: Render failures have explicit consequences
Rendering and visual inspection statuses SHALL remain separate from content extraction and SHALL constrain visual-quality claims.

#### Scenario: DOCX render is unavailable
- **WHEN** DOCX rendering cannot run solely because LibreOffice is unavailable
- **THEN** the document MAY be delivered with `render_not_run` if the Documents contract permits it
- **AND** visual-quality or submission-ready claims SHALL be prohibited

#### Scenario: PDF is extracted but not rendered
- **WHEN** PDF text extraction succeeds but current page rendering and visual inspection do not run
- **THEN** content extraction MAY be reported
- **AND** layout correctness SHALL remain `not_run`

### Requirement: Closure names residual risk and next owner
Every non-passing closure SHALL identify the failed or missing obligation, affected claim or artifact unit, current safe claim, unsafe boundary, next-action owner, and whether rerun, downgrade, omission, access, or human review is required.

#### Scenario: Access gap remains
- **WHEN** a critical source is permission-gated
- **THEN** closure SHALL identify the affected claims
- **AND** provide safe downgraded wording
- **AND** identify source access or human review as the next owner

### Requirement: Operation and release staleness remain separate
The system SHALL keep user-task artifacts in the `agent_operation` freshness plane and maintained skill, installation, and release artifacts in the `development_process` plane.

#### Scenario: User artifact changes
- **WHEN** a report or paper changes after audit
- **THEN** affected operation receipts SHALL become stale
- **AND** the installed skill and GitHub release SHALL remain current if their maintained inputs did not change

#### Scenario: Skill source changes
- **WHEN** a maintained skill, schema, model, adapter contract, or checker changes
- **THEN** only validation owners that consume the changed component and their installation or release projections SHALL become stale

### Requirement: Frozen validation materializes every governed source
The development validation plane SHALL prove that every declared authority input is present byte-for-byte in the frozen execution root, SHALL bind every command to concrete admitted-source selectors, SHALL block tracked source names that the verifier classifies as generated output, SHALL exclude ignored internal records from public-source checks, SHALL require each execution owner to create its own runtime prerequisites, SHALL NOT require repository metadata that the frozen root does not materialize, and SHALL preserve declared logical project identity without treating a random temporary directory name as authority.

#### Scenario: Authority schema name collides with generated evidence
- **WHEN** a tracked schema basename matches the verifier's receipt, cache, progress, or registry output family
- **THEN** final validation SHALL block before release
- **AND** the authority SHALL be renamed directly without a compatibility alias
- **AND** the observed collision plus the finite same-class basename family SHALL be replayed before broad confidence is restored

#### Scenario: Runtime prerequisite is not source authority
- **WHEN** a frozen check needs a generated judgment request or another runtime artifact
- **THEN** the owning command SHALL create and consume that artifact inside its own execution
- **AND** the runtime artifact SHALL NOT be declared as an initial frozen-source input

#### Scenario: Local internal records exist beside public source
- **WHEN** ignored coordination, adoption, verification-report, or verification-receipt records are present in the working tree
- **THEN** frozen materialization SHALL exclude them from the public-source snapshot
- **AND** the public documentation and privacy checks SHALL inspect only admitted source

#### Scenario: A directory shorthand produces no check identity
- **WHEN** a check-level selector such as the repository dot would resolve to an empty input hash map
- **THEN** the check SHALL declare concrete file and glob selectors for the full source surface it observes
- **AND** the frozen receipt SHALL bind a non-empty admitted-source manifest

#### Scenario: Frozen source has no Git metadata
- **WHEN** a source-surface check runs in a frozen root without `.git`, a branch name, or a commit object
- **THEN** the frozen check SHALL validate version and public-source content without claiming Git cleanliness or branch identity
- **AND** clean `main`, commit, tag, and hosted-release identity SHALL remain separate live-repository publication gates

#### Scenario: Frozen directory name differs from project identity
- **WHEN** a native project audit requires the declared `project_id` but the verifier materializes source under a random temporary directory name
- **THEN** the owning check SHALL create a temporary projection named by the unchanged declared project identity
- **AND** the projection SHALL contain only that check's declared source inputs
- **AND** the native project audit result SHALL remain the sole pass or fail authority

### Requirement: Repeated no-progress loops terminate visibly
The system SHALL detect repeated identical failed packets, gap sets, or artifact hashes and SHALL stop with a bounded blocker instead of claiming progress.

#### Scenario: Same packet is rejected twice
- **WHEN** the same packet fingerprint and gap-set fingerprint are rejected without any changed input
- **THEN** the route SHALL return `no_progress_blocked`
- **AND** identify the missing external input or human decision

#### Scenario: Artifact repair changes no bytes
- **WHEN** a repair step produces the same artifact fingerprint
- **THEN** the old audit failure SHALL remain current
- **AND** the route SHALL not count the step as progress

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
