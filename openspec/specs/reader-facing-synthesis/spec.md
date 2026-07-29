# reader-facing-synthesis Specification

## Purpose
TBD - created by archiving change create-logic-writing. Update Purpose after archive.
## Requirements
### Requirement: Reader-facing synthesis uses a two-room boundary
The system SHALL separate internal diagnostic material from reader-facing writing. The prose writer SHALL receive a sanitized ReaderBrief rather than the complete internal ledger.

#### Scenario: Internal ledger contains Guard terminology
- **WHEN** internal evidence includes Guard names, route ids, status fields, model ids, or gap labels
- **THEN** the ReaderBrief SHALL translate them into ordinary reader concepts
- **AND** default final prose SHALL not expose those internal labels

### Requirement: ReaderBrief carries content and boundaries
A ReaderBrief SHALL include the reader question, audience, genre, necessary concepts, principal findings or argument, evidence anchors and source roles, material limitations and alternatives, old-to-new sequence, required citations, allowed wording, and prohibited overclaim wording. It SHALL exclude execution instructions and raw status ledgers.

#### Scenario: Writer receives raw ledger only
- **WHEN** the prose writer receives only diagnostic or closure records
- **THEN** reader-facing synthesis SHALL be `blocked`
- **AND** a ReaderBrief SHALL be generated first

#### Scenario: Brief omits a material limitation
- **WHEN** a current specialist receipt narrows an important claim but the ReaderBrief omits that boundary
- **THEN** ReaderBrief validation SHALL fail
- **AND** the writer SHALL not receive the stronger claim

### Requirement: ReaderBrief content is verifier-derived
The caller MAY supply only the reader context: brief identity, question, audience, genre, purpose, and concepts. Principal findings, evidence anchors, alternatives, limitations, information sequence, citations, allowed wording, and prohibited wording SHALL be derived from an authority-validated ResearchPacket.

#### Scenario: Caller supplies a preferred finding
- **WHEN** a ReaderBrief request contains caller-authored findings, evidence anchors, limitations, citations, status, wording boundaries, or packet identity
- **THEN** the request SHALL be rejected

#### Scenario: Packet contains unsupported safe wording
- **WHEN** a packet contains a claim whose safe wording lacks current source observation, semantic-fit, or required claim-type evidence
- **THEN** that claim SHALL NOT become a principal finding
- **AND** its gap or limitation SHALL remain visible

#### Scenario: No supported principal finding remains
- **WHEN** every candidate finding is excluded by current evidence gaps
- **THEN** ReaderBrief construction SHALL return `blocked`
- **AND** SHALL NOT manufacture an empty or generic conclusion

### Requirement: ReaderBrief derivation has independent authority
The system SHALL issue a managed `reader_brief` Receipt separate from the ReaderBrief content. It SHALL bind the exact ResearchPacket, reader context, builder source, ReaderBrief output, and every consumed native receipt dependency. The Receipt fingerprint SHALL NOT be embedded in the ReaderBrief itself.

#### Scenario: Brief self-fingerprint matches but derivation receipt is absent
- **WHEN** a ReaderBrief has a valid content fingerprint but no current managed derivation Receipt
- **THEN** the prose writer and actual-text audit SHALL reject it as unauthoritative

#### Scenario: Packet changes after brief derivation
- **WHEN** the ResearchPacket fingerprint changes
- **THEN** the prior ReaderBrief derivation Receipt SHALL become stale
- **AND** downstream prose and audits SHALL not remain current

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

### Requirement: Quality is checked on actual text
Reader-facing validation SHALL inspect the actual current artifact and bind to its fingerprint. Metadata declarations such as `reader_native: true`, `status: pass`, or `transition_reviewed` SHALL NOT prove prose quality.

#### Scenario: Bad prose has passing metadata
- **WHEN** metadata reports pass
- **AND** actual text contains internal process language, unexplained concepts, mechanical enumeration, or broken handoffs
- **THEN** reader-facing validation SHALL fail or return `partial`
- **AND** closure SHALL not accept the metadata pass

#### Scenario: Artifact text is absent
- **WHEN** validation receives summaries or metadata without the actual text
- **THEN** it SHALL return `not_run` or `blocked`

### Requirement: Scope escalation is evaluated in context
The deterministic reader audit SHALL evaluate claim strength in its sentence context. It SHALL NOT reject a sentence merely because it contains a causal, universal, or predictive keyword when the sentence explicitly negates that claim, preserves an allowed qualification, or stays within the exact authority-derived wording boundary.

#### Scenario: Sentence explicitly rejects causation
- **WHEN** a supported sentence says that the evidence does not establish that one factor caused another
- **THEN** the causal verb alone SHALL NOT trigger a scope-escalation failure
- **AND** the sentence SHALL remain subject to ordinary support, citation, and reader-flow checks

#### Scenario: Sentence asserts unsupported causation
- **WHEN** a sentence asserts that one factor caused another
- **AND** the current claim boundary does not license causal wording
- **THEN** the reader audit SHALL report scope escalation

### Requirement: Internal language is prohibited by default
Default final prose SHALL NOT include Guard-family tool names, internal route names, snake-case diagnostic fields, model-card ids, workflow status labels, or instructions to internal agents. An explicit methods appendix MAY contain them.

#### Scenario: Internal term leaks into body text
- **WHEN** an ordinary article, report, or academic body contains an internal workflow term
- **THEN** the reader-facing gate SHALL fail that unit
- **AND** require translation or relocation

#### Scenario: User requests methods appendix
- **WHEN** the user explicitly requests a methods appendix
- **THEN** internal tool names MAY appear in that appendix
- **AND** the main body SHALL remain reader-facing prose

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

### Requirement: Output is genre-adaptive and artifact-first
The system SHALL produce the requested artifact genre rather than a fixed diagnostic report. Internal tables, ledgers, route summaries, and methods appendices SHALL be omitted from default delivery unless required by the genre or requested by the user.

#### Scenario: Narrative report requested
- **WHEN** the user requests a narrative report
- **THEN** final output SHALL use coherent report prose
- **AND** SHALL NOT force every evidence role into a visible table or heading

#### Scenario: Structured audit requested
- **WHEN** the user requests a structured audit
- **THEN** tables or gap matrices MAY be used where they improve comparison
- **AND** prose SHALL still explain the result in ordinary language

### Requirement: Citations and limitations survive sanitization
Reader-facing cleanup SHALL NOT remove necessary citations, source-role distinctions, uncertainty, alternatives, or material limitations.

#### Scenario: Cleanup makes a qualified claim absolute
- **WHEN** internal safe wording is qualified
- **AND** synthesis removes that qualification
- **THEN** semantic validation SHALL fail
- **AND** the stronger wording SHALL be rejected

#### Scenario: Citation is detached from its claim
- **WHEN** cleanup moves or removes a marker so it no longer resolves to the supported claim
- **THEN** citation validation SHALL fail

### Requirement: Reader-facing edits invalidate affected audits
Material style or clarity edits SHALL stale every audit whose meaning, paragraph dependency, citation placement, scope, limitation placement, or artifact identity they change.

#### Scenario: Style revision changes meaning
- **WHEN** a style revision changes claim strength, paragraph dependency, citation placement, scope, or limitation placement
- **THEN** the prior reader-facing and semantic-fit receipts SHALL become `stale`

### Requirement: Reader quality uses deterministic and judgment evidence separately
The system SHALL keep deterministic artifact checks and qualitative reader judgment as separate evidence classes; neither SHALL be represented as the other.

#### Scenario: Leak checker passes but prose remains awkward
- **WHEN** deterministic checks find no banned internal labels
- **AND** the judgment rubric finds poor conceptual progression or genre mismatch
- **THEN** reader-facing closure SHALL remain failed or partial

#### Scenario: Judgment approves prose with unresolved placeholder
- **WHEN** qualitative judgment approves text that still contains a deterministic placeholder or unresolved marker
- **THEN** deterministic failure SHALL block closure

### Requirement: ReaderBrief has a route-neutral base and route extensions
The ReaderBrief SHALL keep route-neutral reader intent, content boundaries, and composition fields in the shared base while admitting exactly one route extension owned by the selected final route. Shared validation SHALL verify extension identity and ownership but SHALL NOT reinterpret route-native semantics.

#### Scenario: Fiction receives academic citation fields as mandatory prose instructions
- **WHEN** a fiction route extension is validated
- **THEN** academic-only structure fields are neither required nor injected by the shared base

#### Scenario: Sibling extension is supplied
- **WHEN** the final owner is travel but the ReaderBrief contains a fiction extension
- **THEN** validation fails before drafting

### Requirement: Reader-facing units expose real handoffs
Every important unit SHALL receive a concrete incoming state and emit a concrete reader-state change, unresolved item, or terminal disposition.

#### Scenario: Handoff says only that the document continues
- **WHEN** a unit interface uses generic wording such as “sets up the next section” without naming the changed knowledge, pressure, choice, evidence, or question
- **THEN** reader-quality validation SHALL reject the handoff as generic

### Requirement: Explanation pressure is a reader-quality finding
The system SHALL flag prose that explains the workflow, section function, intended emotion, or intended conclusion when evidence, action, object, dialogue, sequence, or consequence should carry the meaning.

#### Scenario: Paragraph explains its own job
- **WHEN** reader-facing prose states what the paragraph, section, chapter, or day plan has accomplished instead of delivering that content
- **THEN** the artifact SHALL return to route-native projection or structural repair

### Requirement: Register ownership is explicit
Important technical, institutional, local, quoted, character, and narrator terms SHALL have a supported owner and SHALL NOT drift across voices or evidence roles without justification.

#### Scenario: All voices use the same abstract wording
- **WHEN** several speakers, sources, or narrative layers repeatedly use the same unsupported author-summary register
- **THEN** the audit SHALL report register-owner drift

### Requirement: Variation pressure is effect-aware
The system SHALL review repeated openings, information paths, paragraph functions, explanation modes, emotional temperatures, and endings, while allowing repetition that produces escalation, contrast, inversion, cost, deliberate rhythm, or changed interpretation.

#### Scenario: Repetition has no changed effect
- **WHEN** adjacent units repeat the same contribution and surface rhythm without a declared changed effect
- **THEN** the audit SHALL return the artifact to contribution, interface, or route-native revision

### Requirement: Model-artifact binding uses actual bytes
Every required planned unit, content unit, and route model row SHALL bind to current ArtifactMap unit ids and exact artifact spans with content fingerprints. The binding SHALL become stale after any affected artifact edit.

#### Scenario: Binding references an older draft
- **WHEN** the artifact fingerprint or span fingerprint differs from the current bytes
- **THEN** the binding fails and all dependent audits and judgments become stale

#### Scenario: Caller declares coverage without a span
- **WHEN** a required planned unit has only a prose label or empty coverage list
- **THEN** SharedWriting validation fails

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
