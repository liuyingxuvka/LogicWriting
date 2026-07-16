## ADDED Requirements

### Requirement: Academic sections preserve reader-state handoffs
Each important academic section SHALL record what the reader knows on entry, what changes, which question is advanced or recovered, and what the next section receives.

#### Scenario: Research question disappears after introduction
- **WHEN** a material research question is introduced but no later section answers, narrows, rejects, or explicitly defers it
- **THEN** the structural audit SHALL report an unresolved question-recovery gap

### Requirement: Academic prose is bound to modeled contribution
Important paragraphs, figures, tables, and sections SHALL bind to current contribution rows and the reverse outline of the actual artifact SHALL expose unbound prose, unrealized rows, and duplicate bindings without changed effect.

#### Scenario: Two sections realize the same contribution
- **WHEN** two sections bind the same contribution without escalation, contrast, different evidence, changed reader state, or downstream need
- **THEN** the audit SHALL require merge, differentiation, or explicit repetition rationale

### Requirement: Academic review checks explanation pressure and register ownership
The postwrite audit SHALL detect author-facing workflow explanation, premature interpretation, and specialist terms used by a narrator, quoted source, institution, or participant without a supported register owner.

#### Scenario: Method name appears before explanation
- **WHEN** a specialized method term is used before the reader receives a sufficient explanation or source-owned definition
- **THEN** the audit SHALL require earlier introduction, ordinary-language replacement, or explicit source ownership

### Requirement: Academic implications name execution friction
Actionable implications SHALL state material implementation conditions, failure modes, and fallback or recheck conditions rather than presenting an abstract recommendation as universally executable.

#### Scenario: Recommendation ignores a blocking condition
- **WHEN** a material resource, timing, institutional, or access condition can prevent the recommendation
- **THEN** the implication SHALL remain qualified and name the condition and fallback disposition
