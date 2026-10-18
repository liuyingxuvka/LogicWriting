# maintainer-evidence-lifecycle Specification

## Purpose

Define the current maintainer evidence boundary for the Logic Writing source repository. The target skill owns domain behavior and semantic checks; The stable release contract checks source identity, evidence freshness, staged directory parity, and release identity without creating a consumer dependency or an updater.

## Requirements

### Requirement: Target-owned validation depth
The maintainer workflow SHALL preserve Logic Writing's sole native route and SHALL execute exactly the semantic checks declared by the target contract. Generic maintenance checks MUST NOT replace target-domain criteria.

#### Scenario: Current declared checks have one owner
- **WHEN** the Logic Writing source snapshot is frozen and validated
- **THEN** every target-declared check has exactly one execution owner and no undeclared domain check is added

### Requirement: Unit-local current evidence
Reusable validation evidence SHALL be immutable, terminal, identity-exact, and local to the Logic Writing maintenance unit. Evidence from another unit, stale input, or a different execution environment MUST NOT satisfy the unit.

#### Scenario: Foreign or stale receipt is rejected
- **WHEN** a receipt's unit, owner, request, inputs, dependencies, toolchain, or environment differs from the frozen validation identity
- **THEN** the workflow reports the evidence as non-reusable and executes or blocks the exact owner instead of falling back to that receipt

### Requirement: Bounded evidence lifecycle
The maintainer workflow SHALL distinguish durable terminal producer evidence from transient runs, staging projections, caches, logs, and intermediate reports. Non-authoritative material SHALL be eligible for deterministic quarantine or removal only after current durable evidence and protected references are established.

#### Scenario: Historical run material is retired safely
- **WHEN** current terminal evidence and release references have been frozen and an exact lifecycle plan identifies unreferenced transient material
- **THEN** only the planned paths are quarantined or removed and source, business evidence, active processes, and protected release evidence remain untouched

### Requirement: Clean independent consumer
The installed Logic Writing consumer SHALL contain only the target's declared consumer projection and SHALL operate without author state, routing registries, FlowGuard author models, caches, or release scratch data.

#### Scenario: Staged consumer activation
- **WHEN** a release candidate is installed locally
- **THEN** its complete inventory matches the frozen installation projection, forbidden maintainer files are absent, and installed currentness can be checked without running a validation owner

### Requirement: Direct current authority and release parity
The repository SHALL have one stable ordinary release contract and MUST NOT use retired author wrappers as a compatibility or fallback authority. Source version `4.0.8`, installed projection, package metadata where applicable, Git commit, version tag, and GitHub Release SHALL be independently verified before release closure. This maintenance requirement does not create an automatic updater for other computers.

#### Scenario: Release identities agree
- **WHEN** the final source snapshot and single full validation receipt are current
- **THEN** the installed consumer matches the source projection and the pushed commit, version tag, and GitHub Release identify that same snapshot
