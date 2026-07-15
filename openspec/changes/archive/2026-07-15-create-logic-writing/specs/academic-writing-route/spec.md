## ADDED Requirements

### Requirement: Academic route owns academic final artifacts
The academic-writing route SHALL be the sole final owner for new or revised papers, theses, dissertations, academic chapters, proposals, and formal literature reviews.

#### Scenario: From-zero paper
- **WHEN** the user requests a new source-backed academic paper
- **THEN** academic writing SHALL own artifact planning, prose, postwrite review, and final closure
- **AND** investigation SHALL remain a child evidence function

#### Scenario: Existing thesis revision
- **WHEN** the user supplies an existing thesis or paper for substantive revision
- **THEN** academic writing SHALL own revision scope, provenance, structure, prose integration, and final document claims

### Requirement: Evidence gaps use bounded investigation handoffs
The academic route SHALL NOT invent sources or evidence to complete an argument and SHALL create a typed bounded child request for material gaps.

#### Scenario: Critical paragraph lacks support
- **WHEN** a critical academic claim lacks sufficient support
- **THEN** the route SHALL create an investigation gap request
- **AND** use safe interim wording, omit the claim, or block the affected unit until a current packet returns

#### Scenario: Child packet remains incomplete
- **WHEN** investigation returns `partial`, `access_gap`, `bounded`, `provider_unavailable`, or `stale`
- **THEN** academic writing SHALL preserve that state
- **AND** downgrade, omit, or mark the affected claim for human review

### Requirement: Academic structure is modeled before broad drafting or revision
For non-trivial artifacts, the route SHALL obtain or create an artifact-unit inventory, model-card coverage, structural contribution map, parent-goal relationship, downstream-consumer relationship, conclusion-recovery status, and same-level progression when applicable.

#### Scenario: Coherent but structurally unused section
- **WHEN** a section reads clearly but has no parent contribution, downstream consumer, or explicit final treatment
- **THEN** it SHALL be structurally unresolved
- **AND** SHALL be revised, reduced, moved, appended, omitted, or sent for human review

#### Scenario: Literature review is only a list
- **WHEN** adjacent review units do not extend, narrow, contrast, depend on, or expose limits in one another
- **THEN** the route SHALL mark missing progression or explicit parallel background
- **AND** SHALL NOT claim deep literature-review structure

### Requirement: Important shallow units are deepened before final prose
High-importance academic units SHALL NOT remain shallow leaves when they carry material reasoning.

#### Scenario: Method section lists steps only
- **WHEN** a core method unit lacks design need, selected choice, rejected alternative, implementation consequence, validation consequence, or limitation
- **THEN** the unit SHALL be marked under-modeled
- **AND** high-quality final closure SHALL be blocked or downgraded

#### Scenario: Deepening stops for missing project material
- **WHEN** model deepening identifies unavailable standards, datasets, metrics, figure provenance, or project records
- **THEN** the route SHALL record a terminal evidence gap and safe wording
- **AND** SHALL NOT invent the missing support

### Requirement: Existing document work uses the Documents adapter
When the target is DOCX, Word, Google Docs, tracked changes, comments, or document-layout output, the academic route SHALL delegate file mutation and visual QA to Documents.

#### Scenario: DOCX revision with tracked changes
- **WHEN** the user requests real tracked changes
- **THEN** Documents SHALL own OOXML redline creation and structural verification
- **AND** academic writing SHALL own revision content and provenance decisions

#### Scenario: LibreOffice is unavailable
- **WHEN** Documents cannot render solely because LibreOffice is unavailable
- **THEN** the document MAY be delivered only with `render_not_run`
- **AND** the final claim SHALL disclose that visual QA was not completed
- **AND** SHALL NOT say the document was visually verified

#### Scenario: Rendering fails for another reason
- **WHEN** DOCX rendering fails for a reason other than missing LibreOffice
- **THEN** delivery SHALL remain blocked until rendering is repaired or the user explicitly narrows the requested claim

### Requirement: PDF work uses the PDF adapter
When PDF content or layout is material, the route SHALL delegate extraction, rendering, creation, and visual QA to PDF and SHALL keep text and layout evidence distinct.

#### Scenario: PDF text is extracted without rendering
- **WHEN** text extraction succeeds but page rendering and inspection do not run
- **THEN** content extraction MAY be reported
- **AND** layout-correctness claims SHALL remain `not_run`

#### Scenario: PDF changes after page inspection
- **WHEN** the PDF bytes change after a visual inspection receipt
- **THEN** that receipt SHALL become `stale`
- **AND** the current pages SHALL be rendered and inspected again before visual closure

### Requirement: Citations bind to actual academic claims
Every important source-backed academic claim SHALL resolve to a current source entry, locator, source role, and semantic support boundary.

#### Scenario: Marker exists but source does not support wording
- **WHEN** a citation marker resolves structurally but the source cannot support the claim's scope, causality, tense, execution status, or conclusion strength
- **THEN** semantic source fit SHALL fail
- **AND** the claim SHALL be revised, downgraded, omitted, or sent for review

#### Scenario: Bibliography-only support
- **WHEN** an important claim appears in text but its source appears only in the bibliography
- **THEN** academic source closure SHALL remain incomplete

### Requirement: Revision provenance is preserved
Substantive revision SHALL distinguish added, rewritten, moved, deleted or omitted, source-gap, trace-gap, and human-review treatments and SHALL bind them to the current artifact.

#### Scenario: Existing paragraph is materially rewritten
- **WHEN** an original paragraph is changed to repair logic, evidence, scope, or handoff
- **THEN** the revision record SHALL classify it as rewritten rather than newly added

#### Scenario: Style polish overwrites provenance
- **WHEN** a later style pass changes a previously classified revision without updating the provenance record
- **THEN** the provenance receipt SHALL become `stale`

### Requirement: Final academic closure binds the actual artifact
Structure, citation, reader-facing, document, and postwrite receipts SHALL bind to the fingerprint of the final current artifact.

#### Scenario: Final prose changes after audit
- **WHEN** a material paragraph, heading, source marker, figure or table reference, or conclusion changes after audit
- **THEN** affected receipts SHALL become `stale`
- **AND** required audits SHALL rerun before final closure

#### Scenario: ResearchPacket changes
- **WHEN** the artifact consumes a revised investigation packet
- **THEN** every dependent claim, citation, paragraph, and closure receipt SHALL be reevaluated against the new packet fingerprint

### Requirement: Only academic writing issues academic final closure
No child investigation, LogicGuard synthesis result, Documents render, PDF render, or FlowGuard process result SHALL independently close an academic artifact.

#### Scenario: Child routes pass but postwrite audit is missing
- **WHEN** investigation, LogicGuard modeling, and document rendering pass
- **AND** the actual final prose has no current postwrite audit
- **THEN** academic final closure SHALL remain `partial` or `blocked`
