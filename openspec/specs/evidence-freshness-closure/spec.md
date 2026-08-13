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

### Requirement: ResearchGuard suite identity is provider evidence
Every LogicGuard, SourceGuard, or TraceGuard adapter run SHALL carry the unchanged semantic owner and a current ResearchGuard primary path, and its provider preflight SHALL identify the sole `researchguard` console and exact `0.4.11` suite version. Provider availability SHALL NOT prove that native domain work ran.

#### Scenario: Console and member probe pass
- **WHEN** both the ResearchGuard version probe and the selected member capability probe pass
- **THEN** provider preflight SHALL report the console id, member id, primary path, suite version, exact commands, and a claim boundary limited to provider availability

#### Scenario: Native provider evidence is opaque
- **WHEN** Logic Writing consumes a ResearchGuard result or receipt
- **THEN** it SHALL preserve the provider-owned bytes/locator/fingerprint and qualification status as an opaque reference, and SHALL NOT manufacture or reinterpret a ResearchGuard native receipt

#### Scenario: Native result is non-pass
- **WHEN** the selected member returns a failed, blocked, stale, bounded, partial, or not-run native result
- **THEN** Logic Writing SHALL preserve that result unchanged and SHALL NOT strengthen it using another ResearchGuard member or the passing provider preflight

### Requirement: Provider-root overrides cannot create a second ResearchGuard path
Logic Writing SHALL reject a provider-root override for LogicGuard, SourceGuard, or TraceGuard because the installed `researchguard` console is the sole normal execution authority.

#### Scenario: Caller supplies a member provider root
- **WHEN** a caller supplies `--provider-root` while preflighting one of the three ResearchGuard members
- **THEN** the preflight SHALL return a visible blocked result before executing any provider command
