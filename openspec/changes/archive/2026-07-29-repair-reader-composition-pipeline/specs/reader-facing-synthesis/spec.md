## MODIFIED Requirements

### Requirement: ReaderBrief links are internally complete
The ReaderBrief SHALL bind one current RouteDecision, ReaderIntent, route content projection, whole-artifact CompositionPlan, selected route extension, native dependency receipts, content authority fingerprints, and one final owner. Every required user-outline row, content obligation, limitation, citation duty, exact-preservation duty, planned unit, and route surface SHALL be consumed exactly as declared or receive a visible conflict or omission disposition.

#### Scenario: Required user section is not planned
- **WHEN** the ReaderIntent contains a required outline row that is absent from the CompositionPlan
- **THEN** ReaderBrief validation fails before drafting and identifies the missing outline row

#### Scenario: Material limitation has no placement
- **WHEN** a content limitation is not assigned to a planned unit that uses the affected content
- **THEN** ReaderBrief validation fails rather than allowing the limitation to be appended remotely or omitted

#### Scenario: Several findings support one section
- **WHEN** several content units jointly answer one reader question
- **THEN** they may be consumed by one planned unit without creating one paragraph per content unit

#### Scenario: Citation points to no observed anchor
- **WHEN** a citation names a source but no observed source anchor that supports its target wording
- **THEN** ReaderBrief validation SHALL fail

#### Scenario: Sequence omits a finding
- **WHEN** an eligible principal finding is absent from the declared reader sequence or appears more than once
- **THEN** ReaderBrief validation SHALL fail

### Requirement: Paragraph flow is derived from artifact units
The system SHALL build a semantic reverse outline from the current artifact units and their actual reader jobs, main points, support or action, prior dependencies, relation to the preceding unit, and downstream effect. Connector words or first sentences alone SHALL NOT establish coherence.

#### Scenario: Transition phrase hides a reasoning jump
- **WHEN** a paragraph begins with a transition phrase but does not consume the preceding unit or support a downstream unit
- **THEN** semantic judgment records a coherence defect

#### Scenario: Natural handoff has no explicit connector
- **WHEN** two adjacent units have a clear semantic dependency without a transition phrase
- **THEN** they may pass coherence review

#### Scenario: Reverse outline is caller-authored
- **WHEN** supplied reverse-outline rows do not bind current artifact locators and excerpts
- **THEN** they do not satisfy semantic judgment

#### Scenario: Referent is ambiguous
- **WHEN** a reader-facing unit relies on a pronoun or label whose referent cannot be recovered from the actual surrounding units
- **THEN** the judgment records a clarity or coherence repair

### Requirement: ReaderBrief has a route-neutral base and route extensions
The ReaderBrief SHALL keep route-neutral reader intent, content boundaries, and composition fields in the shared base while admitting exactly one route extension owned by the selected final route. Shared validation SHALL verify extension identity and ownership but SHALL NOT reinterpret route-native semantics.

#### Scenario: Fiction receives academic citation fields as mandatory prose instructions
- **WHEN** a fiction route extension is validated
- **THEN** academic-only structure fields are neither required nor injected by the shared base

#### Scenario: Sibling extension is supplied
- **WHEN** the final owner is travel but the ReaderBrief contains a fiction extension
- **THEN** validation fails before drafting

### Requirement: Model-artifact binding uses actual bytes
Every required planned unit, content unit, and route model row SHALL bind to current ArtifactMap unit ids and exact artifact spans with content fingerprints. The binding SHALL become stale after any affected artifact edit.

#### Scenario: Binding references an older draft
- **WHEN** the artifact fingerprint or span fingerprint differs from the current bytes
- **THEN** the binding fails and all dependent audits and judgments become stale

#### Scenario: Caller declares coverage without a span
- **WHEN** a required planned unit has only a prose label or empty coverage list
- **THEN** SharedWriting validation fails

## ADDED Requirements

### Requirement: Reader intent is the sole reader-contract authority
The current reader pipeline SHALL use one ReaderIntent as the authority for artifact mode, language, audience, purpose, structure, style, length, format, required content, forbidden content, and list policy. Downstream contracts SHALL bind its fingerprint rather than copying independent alternatives.

#### Scenario: Route default conflicts with user structure
- **WHEN** a route default proposes a different order from a fixed user outline
- **THEN** the user outline remains authoritative or a visible material conflict blocks drafting

### Requirement: Content authority and wording are separate
Content boundaries SHALL define safe meaning, evidence anchors, alternatives, limitations, citation obligations, prohibited overclaims, exact-preservation tokens, and genuine verbatim duties. Ordinary safe meanings SHALL permit natural paraphrase and synthesis; the runtime SHALL NOT publish an allowed-wording list for prose copying.

#### Scenario: Natural paraphrase preserves meaning
- **WHEN** the artifact expresses a safe meaning accurately without repeating source wording
- **THEN** deterministic validation does not fail merely because the original phrase is absent

#### Scenario: Required number changes
- **WHEN** a token explicitly marked for exact preservation is altered
- **THEN** deterministic audit fails with the affected content and artifact units

### Requirement: Whole-artifact composition precedes final drafting
The selected route SHALL produce a CompositionPlan that maps every required user-outline row and content obligation into ordered artifact units with parent ownership, reader job, incoming and outgoing reader state, relation to prior units, downstream consumers, presentation mode, and target extent. Unresolved material conflicts SHALL block final drafting.

#### Scenario: Findings are copied into sequential cards
- **WHEN** a plan creates one shallow planned unit for every finding without reader or downstream justification
- **THEN** composition validation fails or requires consolidation

#### Scenario: Functional list is requested
- **WHEN** the ReaderIntent or route plan marks a unit as a list, table, or operational appendix
- **THEN** that presentation mode is allowed without weakening prose requirements elsewhere

### Requirement: Reader artifacts receive a whole-artifact integration pass
After an initial complete draft and before audit, the selected route SHALL integrate the whole artifact by consolidating duplicate contributions, repairing cross-unit handoffs, relocating limitations and citations, removing internal workflow language, and enforcing reader-intent structure. Local sentence polishing alone SHALL NOT satisfy integration.

#### Scenario: Repeated conclusion survives local polish
- **WHEN** several sections restate the same contribution without changed effect
- **THEN** integration remains incomplete and the artifact cannot enter final judgment

### Requirement: Deterministic and qualitative review have separate authority
Deterministic audit SHALL verify only current bytes, structure locks, exact-preservation duties, citation placement, list zones, placeholders, workflow leakage, fragmentation metrics, and binding presence. Independent ReaderJudgment SHALL evaluate clarity, structure fidelity, coherence, naturalness, reader fit, content fidelity, genre fit, and instruction fidelity from actual locators and excerpts.

#### Scenario: Deterministic checks pass but prose is awkward
- **WHEN** all required tokens and headings are present but the artifact remains card-like or incoherent
- **THEN** ReaderJudgment records required repairs and final closure remains blocked

#### Scenario: Same actor writes and approves
- **WHEN** the producer and judge identities are the same for a required routine independent review
- **THEN** the judgment cannot issue a final pass

### Requirement: Prose zones reject pointillist output without banning functional structure
When a planned unit requires prose, deterministic and qualitative review SHALL detect bullet domination, Unicode and localized list markers, repeated label cards, one-sentence microparagraph sequences, and excessive one-line headings. Explicit list, table, scene, and appendix zones SHALL be evaluated by their own functional contracts.

#### Scenario: Chinese numbered cards replace prose
- **WHEN** a prose-required section consists primarily of short `一、二、三` cards
- **THEN** the section fails fragmentation or naturalness review

#### Scenario: Travel appendix uses bullets
- **WHEN** an operational appendix is declared as an allowed list zone
- **THEN** its bullets do not count against the narrative-body prose ratio

### Requirement: Every non-pass produces a typed repair cycle
Every blocking audit or required reader repair SHALL produce a RepairRequest bound to the current artifact, ReaderBrief, CompositionPlan, audit, judgment, target units, required changes, preservation boundary, and forbidden shortcuts. A RepairResult SHALL bind input and output artifact fingerprints, changed units, preservation checks, remaining defect identity, and progress status before affected evidence is rebuilt.

#### Scenario: Repair adds only connector words
- **WHEN** a coherence repair changes only transition phrases while the defect set remains unchanged
- **THEN** the result records no progress and does not close the artifact

#### Scenario: Repair changes current bytes
- **WHEN** a valid repair modifies the artifact
- **THEN** the old ArtifactMap, SharedWriting binding, audit, judgment, and closure become stale and are regenerated for the new bytes

### Requirement: Current reader contracts use direct replacement
The current runtime SHALL reject ReaderBrief v1, SharedWriting v1, ReaderAudit v1, ReaderJudgment v1, legacy information sequence, principal findings as layout authority, allowed wording, and legacy closure reader chains. No normal-runtime converter, alias, dual emission, or fallback SHALL be provided.

#### Scenario: Old ReaderBrief is supplied
- **WHEN** a v1 brief containing `information_sequence` or `allowed_wording` reaches a current validator
- **THEN** it fails as an unsupported contract rather than being converted or partially accepted
