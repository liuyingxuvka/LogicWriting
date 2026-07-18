## ADDED Requirements

### Requirement: ResearchGuard suite identity is provider evidence
Every LogicGuard, SourceGuard, or TraceGuard adapter run SHALL carry the unchanged semantic owner and a current ResearchGuard primary path, and its provider preflight SHALL identify the sole `researchguard` console and suite version. Provider availability SHALL NOT prove that native domain work ran.

#### Scenario: Console and member probe pass
- **WHEN** both the ResearchGuard version probe and the selected member capability probe pass
- **THEN** provider preflight SHALL report the console id, member id, primary path, suite version, exact commands, and a claim boundary limited to provider availability

#### Scenario: Native result is non-pass
- **WHEN** the selected member returns a failed, blocked, stale, bounded, partial, or not-run native result
- **THEN** Logic Writing SHALL preserve that result unchanged and SHALL NOT strengthen it using another ResearchGuard member or the passing provider preflight

### Requirement: Provider-root overrides cannot create a second ResearchGuard path
Logic Writing SHALL reject a provider-root override for LogicGuard, SourceGuard, or TraceGuard because the installed `researchguard` console is the sole normal execution authority.

#### Scenario: Caller supplies a member provider root
- **WHEN** a caller supplies `--provider-root` while preflighting one of the three ResearchGuard members
- **THEN** the preflight SHALL return a visible blocked result before executing any provider command
