## Purpose

Provide a reproducible, evidence preserving quality benchmark that distinguishes synthetic protocol checks from real writer and independent judge execution.

## ADDED Requirements

### Requirement: The benchmark uses fixed case inputs without score fixtures
The benchmark SHALL provide twelve case inputs with frozen materials, constraints, counterexamples, rubric metadata, and repeat ordering, while never using fixture text or caller supplied scores as generated quality output.

#### Scenario: Case input is loaded
- **WHEN** a benchmark case is selected
- **THEN** the runner SHALL persist the case request and frozen material fingerprint before writer execution

#### Scenario: Fixture score is supplied
- **WHEN** a protocol fixture contains a preferred score or complete-chain output
- **THEN** the real benchmark SHALL ignore it as quality evidence

### Requirement: Missing authorized backend is visible and terminal
The runner SHALL use only the currently configured authorized execution backend and SHALL return `execution_provider_unavailable` with a not-run receipt when no backend can provide a verifiable writer/judge run.

#### Scenario: No backend is configured
- **WHEN** the runner is invoked without an authorized provider
- **THEN** it SHALL save a not-run/unavailable report and SHALL not synthesize an article, score, or pass

#### Scenario: Backend returns a real run
- **WHEN** an authorized backend produces writer and independent judge provenance
- **THEN** the runner SHALL save the actual inputs, outputs, run identities, fingerprints, timing, token/cost fields when available, blind order, and disagreement status

### Requirement: Quality comparison preserves incomplete and disagreement outcomes
The benchmark SHALL compare matched original and repaired outputs under the same independent rubric, preserve failed or missing baseline artifacts, and SHALL report `incomplete`, `tie`, or `disagreement` when a comparable pair or judge agreement is unavailable.

#### Scenario: Baseline produces no article
- **WHEN** the original path fails or returns no artifact
- **THEN** the baseline result SHALL remain a failed or unavailable run and SHALL not be counted as a quality win

#### Scenario: Two judges disagree
- **WHEN** independent judges return conflicting preferences or a located core defect
- **THEN** the pair SHALL preserve the disagreement and SHALL not be converted to pass by the runner
