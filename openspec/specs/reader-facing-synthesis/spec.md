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
Every principal finding SHALL identify its claims and at least one evidence anchor. Every evidence anchor SHALL identify one source anchor, locator, reader-readable source role, supported wording, and boundary. Every supporting anchor SHALL have a stable citation marker, and every limitation, alternative, sequence item, and citation SHALL resolve to an existing target.

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
The system SHALL derive a reverse outline from the actual text and SHALL review paragraph purpose, previous information carried forward, new information introduced, claim and support, unresolved tension, referent clarity, next-paragraph handoff, repetition, and unsupported jumps for important paragraph pairs.

#### Scenario: Transition phrase hides a reasoning jump
- **WHEN** a paragraph contains a transition phrase
- **AND** the next paragraph introduces an unsupported concept, scope shift, or causal jump
- **THEN** flow validation SHALL fail
- **AND** SHALL NOT treat the phrase as sufficient evidence

#### Scenario: Reverse outline is caller-authored
- **WHEN** a reverse outline is not derived from the current artifact fingerprint
- **THEN** it SHALL be rejected as stale or unauthoritative

#### Scenario: Referent is ambiguous
- **WHEN** an important pronoun, acronym, concept, or comparison lacks a clear prior referent
- **THEN** the affected unit SHALL fail reader-flow review
- **AND** the writer SHALL repair the concept introduction or reference

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
The system SHALL derive a route-neutral ReaderBrief base containing audience, purpose, incoming reader state, concepts, contribution sequence, safe boundaries, and artifact form, then attach only the selected route's extension.

#### Scenario: Fiction receives academic citation fields as mandatory prose instructions
- **WHEN** a route extension is not owned by the selected route
- **THEN** the brief builder SHALL omit it from required projection and SHALL NOT treat its absence as a gap

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
Important planned rows and actual artifact spans SHALL be linked to the current artifact identity, and a material byte change SHALL stale affected binding and reverse-audit evidence.

#### Scenario: Binding references an older draft
- **WHEN** a passing binding receipt names a different artifact hash from the delivered file
- **THEN** the binding SHALL be stale and SHALL NOT contribute to closure
