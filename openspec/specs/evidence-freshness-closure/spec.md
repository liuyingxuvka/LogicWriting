# evidence-freshness-closure Specification

## Purpose
Define how Logic Writing derives closure from the current actual text, keeps failures visible, and makes earlier checks stale when the text or its inputs change.
## Requirements
### Requirement: Closure status is derived from the current actual-text checks
The system SHALL derive closure from the deterministic audit, the route review and the independent ReaderJudgment of the current artifact bytes. Closure status SHALL be `passed` or `needs_repair`. Caller-authored status fields SHALL be treated as claims, not evidence.

#### Scenario: A record self-reports pass
- **WHEN** a ledger or review reports every check as passed
- **AND** the deterministic audit or the independent read of the current bytes does not pass
- **THEN** closure SHALL be `needs_repair`

### Requirement: Every final closure has a minimum content baseline
Every final route closure SHALL consume the current ReaderBrief, route composition, SharedWriting binding, route-native review, deterministic audit, independent ReaderJudgment and revision provenance, plus the selected route's native evidence, all bound to the same final owner, ReaderIntent, CompositionPlan, and current artifact fingerprint.

#### Scenario: Process is green but content work did not run
- **WHEN** process and release checks pass but any required reader-chain record is missing, stale, skipped, partial, or failed
- **THEN** final closure does not pass

#### Scenario: Route-native review is missing
- **WHEN** shared reader checks pass but the selected route has not reviewed the current actual artifact
- **THEN** final closure does not pass

#### Scenario: New artifact has no source document
- **WHEN** an artifact is created from zero
- **THEN** its revision provenance records that there is no source, and the rest of the chain determines closure

#### Scenario: Academic revision lacks provenance
- **WHEN** an academic artifact revises an existing document and no current revision provenance binds its source and target units
- **THEN** academic final closure SHALL NOT pass

### Requirement: Material changes invalidate dependent evidence
The system SHALL treat every check of an artifact, packet, model, plan or brief as belonging to the exact bytes it checked; a material change SHALL make the dependent checks stale.

#### Scenario: Final text changes after review
- **WHEN** the artifact bytes change after the ArtifactMap, audit, review or judgment was built
- **THEN** closure re-reads the bytes, reports the ArtifactMap as stale, and does not pass

#### Scenario: Source registry changes
- **WHEN** a source record, locator, role, date, lineage, or support boundary changes
- **THEN** dependent claim support, packet, prose, citation, and closure checks SHALL be rerun

#### Scenario: Runtime log changes only
- **WHEN** only a progress log or timestamp changes
- **THEN** content evidence SHALL remain current

### Requirement: Failure states propagate monotonically
A dependent final claim SHALL be no stronger than the weakest unresolved important obligation. The system SHALL NOT convert `not_run`, `stale`, `provider_unavailable`, `access_gap`, `render_not_run`, `bounded`, `downgraded`, or `blocked` into `passed`.

#### Scenario: Critical counter search is not run
- **WHEN** all other checks pass but a required counterevidence search is `not_run`
- **THEN** complete investigation closure SHALL be prohibited

#### Scenario: Optional item is skipped
- **WHEN** an optional non-critical check is skipped with a stated reason
- **THEN** closure MAY pass only when the item is outside the requested claim scope
- **AND** the skip SHALL remain visible

#### Scenario: An earlier result failed or an artifact unit disappeared
- **WHEN** a referenced result envelope failed and has no requested record
- **THEN** request loading SHALL report its first error in one plain line before a sole-object fallback
- **WHEN** a binding or review evidence names a unit absent from the current ArtifactMap
- **THEN** validation SHALL name that unit before filling any fingerprints and SHALL NOT guess replacement bindings

### Requirement: Planning artifacts cannot satisfy proof obligations
Search plans, candidates, utility scores, outlines, story plans, progress logs, and check manifests SHALL NOT satisfy factual, semantic, rendered-artifact, reader-quality, or final-closure obligations.

#### Scenario: Candidate source is used as proof
- **WHEN** a candidate-source artifact is supplied as factual evidence
- **THEN** closure SHALL reject the substitution

#### Scenario: Story plan is used as final prose audit
- **WHEN** an artifact-synthesis plan is supplied instead of an audit of actual final text
- **THEN** reader-facing and academic closure SHALL remain `not_run`

### Requirement: Native owners remain authoritative
SourceGuard SHALL own source planning and source depth; TraceGuard SHALL own temporal, causal, competing-storyline, and perturbation analysis; LogicGuard SHALL own argument, structural, citation-semantic, and model-depth judgment; WorldGuard SHALL own world consistency; Documents and PDF SHALL own file mutation and visual checks. Logic Writing SHALL consume their results as they are and SHALL NOT recreate their domain decisions.

#### Scenario: Logic Writing fabricates source qualification
- **WHEN** a source is labelled claim-usable without an observed, anchored source record
- **THEN** evidence validation SHALL return `blocked`

### Requirement: Only the final owner issues final closure
Child routes and adapters SHALL return bounded results only.

#### Scenario: Investigation child succeeds
- **WHEN** an investigation child returns a passing packet to an academic parent
- **THEN** the child SHALL close only its requested gap scope
- **AND** academic final closure SHALL remain with `academic-writing`

#### Scenario: Document render passes
- **WHEN** Documents reports a flawless current render
- **THEN** that result SHALL satisfy only document-layout obligations
- **AND** SHALL NOT satisfy argument, source, reader-facing, or academic completion obligations

### Requirement: Broad claims require broad current evidence
Words such as complete, comprehensive, deep, conclusive, robust, final, publication-ready, and submission-ready SHALL require current broad-scope results for every applicable important domain.

#### Scenario: Native result is bounded
- **WHEN** SourceGuard, TraceGuard, or LogicGuard returns a bounded result
- **THEN** broad final wording SHALL be prohibited
- **AND** final wording SHALL match the covered scope

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

### Requirement: A closure that does not pass names what remains
Every `needs_repair` closure SHALL keep the residual defects, the current safe claim, the unsafe boundary, and the final owner as the owner that repairs and reruns; broad claims SHALL NOT be allowed.

#### Scenario: Independent read reports a blocking defect
- **WHEN** the ReaderJudgment of the current bytes reports a blocking defect
- **THEN** closure is `needs_repair`, its next action is `repair_and_rerun` for the final owner, and `broad_claim_allowed` is false

### Requirement: Repair rounds stop when nothing is fixed
When the audit or the independent read reports defects, the writer SHALL revise the actual text, rebuild the ArtifactMap and rerun the audit and the read. If a revision round fixes none of the reported defects, the writer SHALL stop and return the artifact with the audit note. Repeated closure derivation SHALL NOT count as repair.

#### Scenario: Closure is derived twice on unchanged bytes
- **WHEN** closure is derived again without any change to the artifact
- **THEN** the status is unchanged and no repair is counted

### Requirement: Every route has a route-native minimum closure baseline
Final closure SHALL require the shared identity, reader projection, actual-artifact audit, and freshness surfaces plus the selected route's declared minimum domain surfaces.

#### Scenario: Shared audit passes but fiction surfaces are absent
- **WHEN** reader-language checks pass but required story contribution, promise, continuity, semantic review, or model-prose binding evidence is missing
- **THEN** fiction final closure SHALL remain blocked or explicitly partial

#### Scenario: Shared audit passes but travel surfaces are absent
- **WHEN** reader-language checks pass but required source-time, feasibility, fit, fallback, or reverse-guide evidence is missing
- **THEN** travel final closure SHALL remain blocked or explicitly downgraded

### Requirement: Final semantic review is artifact-bound and scope-visible
Judgment-based reader, academic, fiction, and travel reviews SHALL identify the exact artifact, reviewed units, rubric version, evaluator, skipped scope, limitations, blocking findings, and confidence boundary.

#### Scenario: Review praises prose without opening the final artifact
- **WHEN** a semantic review cannot resolve the delivered artifact identity or reviewed unit set
- **THEN** the review SHALL NOT contribute to final closure

### Requirement: Reader-chain edits propagate exact staleness
An edit to ReaderIntent, RouteDecision, route content, CompositionPlan, route extension, actual artifact bytes, or ArtifactMap SHALL stale exactly the dependent ReaderBrief, SharedWriting, deterministic audit, route-native review, ReaderJudgment, and closure. Runtime logs and progress outputs SHALL NOT stale their producers.

#### Scenario: Artifact punctuation changes inside a bound span
- **WHEN** current artifact bytes change inside a bound span
- **THEN** the ArtifactMap and every dependent reader-chain record become stale

### Requirement: Current closure rejects legacy reader evidence
The current closure SHALL reject legacy ReaderBrief, SharedWriting, audit, and judgment shapes and SHALL NOT consume compatibility projections.

#### Scenario: Legacy audit is otherwise passing
- **WHEN** a v1 audit has a passing status but lacks current ReaderIntent, CompositionPlan, and artifact binding identities
- **THEN** closure rejects it as ineligible evidence

### Requirement: Published release identities are immutable
A published tag or GitHub Release SHALL NOT be moved, replaced, or deleted to conceal a later validation failure. A repair SHALL use a strictly higher version.

#### Scenario: A fresh clone exposes a missed failure
- **WHEN** a published release later fails a required check
- **THEN** its tag and release SHALL remain unchanged
- **AND** the corrected source SHALL be published under a higher version only after its checks pass
