## ADDED Requirements

### Requirement: Research Guard members use one executable provider
Logic Writing SHALL preserve `logicguard`, `sourceguard`, and `traceguard` as distinct semantic owners while invoking each only through the `researchguard` console and its exact current primary path. Logic Writing MUST NOT import an old member package, invoke an old module command, locate a sibling checkout, or try another member when the selected member is unavailable.

#### Scenario: LogicGuard member is available
- **WHEN** Logic Writing preflights the LogicGuard semantic owner
- **THEN** it SHALL verify `researchguard --version` and `researchguard logic --help`, bind `primary:researchguard:logic`, and run no alternate provider probe

#### Scenario: ResearchGuard console is absent
- **WHEN** the `researchguard` console cannot be resolved
- **THEN** Logic Writing SHALL return `provider_unavailable` and SHALL NOT import `logicguard`, run `python -m logicguard`, or select SourceGuard or TraceGuard

#### Scenario: Member capability times out
- **WHEN** the selected ResearchGuard member capability probe exceeds its configured bound
- **THEN** Logic Writing SHALL preserve the timeout as visible provider evidence and terminate that provider preflight without recovery through another path

### Requirement: Retired direct Guard routes have zero current authority
Current Logic Writing source, tests, models, and active change artifacts SHALL contain no executable call or current route binding for the retired LogicGuard satellite skill ids, `traceguard-library`, or the former direct member module commands.

#### Scenario: Current consumer topology is scanned
- **WHEN** the target-owned zero-residual checker scans current governed files
- **THEN** it SHALL pass only if all Guard calls resolve to the ResearchGuard console/member topology and archived history is not treated as current authority

### Requirement: The single-console topology has one source version identity
The changed provider topology SHALL be frozen as Logic Writing source version
`2.1.0`. `VERSION`, package metadata, public source badges, changelog, source
reconciliation, current OpenSpec release requirements, and the
release-retirement checklist SHALL agree on that identity before a candidate
commit is published.

#### Scenario: Candidate source is checked before installation
- **WHEN** the `2.1.0` candidate is validated on its review branch
- **THEN** source-version checks and the recompiled SkillGuard contract SHALL
  pass on the exact candidate tree
- **AND** no installed projection, tag, or GitHub Release SHALL be claimed
