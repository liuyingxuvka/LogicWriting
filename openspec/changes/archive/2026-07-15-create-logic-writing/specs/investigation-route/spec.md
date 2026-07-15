## ADDED Requirements

### Requirement: Investigation begins with a claim and evidence contract
Before broad search, the investigation route SHALL record the question, scope, target audience, requested conclusion strength, time and geographic boundaries, source-access policy, critical claims, and required evidence roles.

#### Scenario: Strong causal conclusion requested
- **WHEN** the user requests a strong causal conclusion
- **THEN** the evidence contract SHALL require mechanism evidence, material alternatives, confounder review, counter or limiting evidence, and scope boundaries

#### Scenario: Material scope is unknown
- **WHEN** time, geography, population, or effect layer materially affects the conclusion and cannot be inferred safely
- **THEN** the route SHALL request clarification or mark the scope unresolved
- **AND** SHALL NOT silently broaden the scope

### Requirement: Candidate sources are not facts
A search result, SourceGuard candidate, title, snippet, bibliography entry, or utility score SHALL remain a candidate until the source is accessed or an access gap is recorded, relevant content is inspected, an anchor or normalized summary exists, its source role and support boundary are recorded, and semantic claim fit is reviewed.

#### Scenario: Search title appears relevant
- **WHEN** a search title appears to support a claim but the source content has not been inspected
- **THEN** the source status SHALL remain `candidate`
- **AND** final prose SHALL NOT present the claim as established

#### Scenario: Candidate is cited as fact
- **WHEN** final prose uses a candidate-only source as factual support
- **THEN** claim validation SHALL fail
- **AND** closure SHALL be no stronger than `partial` or `downgraded`

#### Scenario: Source is inaccessible
- **WHEN** a required source cannot be accessed
- **THEN** the route SHALL record `access_gap`
- **AND** downgrade, omit, or mark for human review every dependent claim

### Requirement: Investigation depth is obligation-driven
The route SHALL determine depth from critical claim types and evidence gaps. It SHALL NOT treat source count or a caller-declared number of rounds as proof of depth.

#### Scenario: Many sources repeat one origin
- **WHEN** several apparent sources trace to one original lineage
- **THEN** they SHALL count as one lineage for independence review
- **AND** a claim requiring independent support SHALL remain under-supported

#### Scenario: Execution claim has only announcement evidence
- **WHEN** a claim states that a policy, project, or product was implemented or produced an outcome
- **AND** available sources establish only an announcement, plan, forecast, or capacity statement
- **THEN** the route SHALL mark execution or outcome evidence as missing
- **AND** downgrade the wording

#### Scenario: Important obligations are complete
- **WHEN** every critical claim has current direct support, required provenance, meaningful counter or limiting evidence, and an explicit scope boundary
- **THEN** the route MAY stop searching
- **AND** SHALL preserve remaining non-critical gaps

### Requirement: Temporal and causal claims use TraceGuard conditionally
The route SHALL invoke TraceGuard when a material claim depends on chronology, implementation sequence, causality, counterfactual reasoning, competing storylines, or outcome transfer.

#### Scenario: Chronology has no mechanism
- **WHEN** event A occurred before outcome B
- **AND** no mechanism or link evidence connects them
- **THEN** the route SHALL NOT write that A caused B
- **AND** SHALL return a causal gap or qualified wording

#### Scenario: Competing explanations remain live
- **WHEN** two explanations remain supported after trace review
- **THEN** both SHALL remain visible in the handoff
- **AND** the route SHALL NOT choose the smoother story solely because it reads better

#### Scenario: Prediction lacks native future validation
- **WHEN** predictive wording is requested
- **AND** TraceGuard reports no current native future-holdout support
- **THEN** predictive wording SHALL be blocked or explicitly qualified

### Requirement: Investigation adjudicates important conclusions
The route SHALL use LogicGuard to compare support, warrants, assumptions, scope, rebuttals, steelman opposition, and material alternatives before issuing strong conclusion wording.

#### Scenario: Preferred conclusion has not faced opposition
- **WHEN** a central conclusion has support but no meaningful opposing or alternative case was modeled
- **THEN** the conclusion SHALL remain under-modeled
- **AND** final wording SHALL be qualified or withheld

#### Scenario: LogicGuard model is bounded
- **WHEN** the current LogicGuard receipt covers only a bounded subset
- **THEN** the report SHALL match that bounded scope
- **AND** SHALL NOT claim comprehensive or robust reasoning

### Requirement: Investigation returns a typed ResearchPacket
A completed investigation SHALL return a packet containing the source registry, evidence anchors, critical-claim and key-number ledger, support and limiting evidence, alternatives and confounders, relevant execution/effect/causal chains, source lineage and independence status, unresolved gaps, safe wording, unsafe boundaries, native receipt references, exact input manifest, and a packet fingerprint.

#### Scenario: Academic parent consumes the packet
- **WHEN** investigation was invoked by an academic parent
- **THEN** the packet SHALL contain the requested `gap_id`
- **AND** SHALL contain no academic final-closure claim
- **AND** the academic parent SHALL verify its fingerprint before use

#### Scenario: Packet omits a critical counterevidence gap
- **WHEN** a critical claim required counter or limiting evidence but the packet omits its status
- **THEN** packet validation SHALL return `partial` or `blocked`

#### Scenario: Gap is only an opaque string
- **WHEN** an unresolved gap lacks a stable identity, affected claims or sources, reader-safe wording, unsafe boundary, and next owner
- **THEN** packet validation SHALL reject it
- **AND** SHALL NOT copy the opaque code into reader-facing prose

#### Scenario: Causal claim has only a temporal receipt
- **WHEN** a causal claim has chronology evidence but no current `causal_trace` evidence for the declared mechanism and scope
- **THEN** the causal claim SHALL remain ineligible for principal-finding wording

#### Scenario: Forecast lacks prediction-boundary evidence
- **WHEN** a forecast has a source marked as validation evidence but no current `prediction_boundary` receipt for the claim scope
- **THEN** the forecast SHALL remain ineligible for principal-finding wording

### Requirement: Claim-to-source links identify observed anchors
Every supported claim SHALL map each cited source to one or more observed anchor ids and classify that link as support, limit, counterevidence, or context. A claim-level source list without anchor-level links SHALL NOT license reader-facing wording.

#### Scenario: Source belongs to claim but anchor belongs elsewhere
- **WHEN** a support link names an anchor that is absent or belongs to another source
- **THEN** claim validation SHALL fail

#### Scenario: Strong claim repeats one lineage
- **WHEN** a strong claim has several support links but fewer than two current independent lineages
- **THEN** the claim SHALL remain under-supported

### Requirement: Provider and execution failures remain visible
The route SHALL preserve `provider_unavailable`, `not_run`, `planning_only`, `access_gap`, `bounded`, `partial`, `downgraded`, `stale`, and `blocked` states.

#### Scenario: Search provider is unavailable
- **WHEN** external discovery is required but no search provider can run
- **THEN** the route SHALL return `provider_unavailable` or `planning_only`
- **AND** SHALL NOT claim that external search was executed

#### Scenario: Native receipt is bounded
- **WHEN** SourceGuard, TraceGuard, or LogicGuard returns a bounded native receipt
- **THEN** the investigation SHALL NOT use complete, comprehensive, conclusive, or fully investigated wording

### Requirement: Investigation completion is verifier-derived
The route SHALL NOT accept caller-authored `complete`, `passed`, or `closure_status` fields as authoritative completion evidence.

#### Scenario: Caller submits complete without receipts
- **WHEN** a ledger says `complete` but lacks required source, trace, or semantic-fit receipts
- **THEN** the verifier SHALL ignore the declared status
- **AND** derive `partial`, `downgraded`, or `blocked` from the actual missing evidence
