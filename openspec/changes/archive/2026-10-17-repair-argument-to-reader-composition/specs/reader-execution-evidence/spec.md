## Purpose

This capability records whether writer and independent reader-judge actions
actually ran with the declared inputs, contexts, outputs, and execution source.

## ADDED Requirements

### Requirement: Execution records bind actual runs

Each writer or judge execution SHALL record a run id, context id, orchestrator
run, model/settings identity, input fingerprints, output fingerprint, terminal
status, provider completion reference, and an immutable record fingerprint.
The caller's proposed JSON SHALL not be accepted as proof of execution.

#### Scenario: Backend is unavailable
- **WHEN** no configured backend can execute the request
- **THEN** dispatch SHALL return `execution_provider_unavailable`
- **AND** no quality pass SHALL be issued

#### Scenario: Pair review receives two articles
- **WHEN** a blind judge compares two generated articles
- **THEN** the record SHALL bind exactly two anonymous inputs, both writer runs, the rubric, and a pair-input fingerprint
- **AND** swapping X and Y SHALL change that fingerprint

### Requirement: Independence is resolved from provenance

A judge SHALL be `verified` only when its completed execution source, input
articles, rubric, and context are independently resolved and differ from every
writer context used for the comparison. Missing or conflicting provenance
SHALL map to repair or blocked closure.

#### Scenario: Forged different ids share a context
- **WHEN** writer and judge labels differ but their resolved context is identical
- **THEN** the judge SHALL be `independence_unverified`
- **AND** ReaderJudgment SHALL not pass
