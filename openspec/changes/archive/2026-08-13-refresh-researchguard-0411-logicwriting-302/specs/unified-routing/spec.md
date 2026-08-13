## MODIFIED Requirements

### Requirement: Research Guard members use one executable provider

Logic Writing SHALL preserve `logicguard`, `sourceguard`, and `traceguard` as distinct semantic owners while invoking each only through the `researchguard` console and its exact current primary path. The distribution metadata, console output, and supported provider identity SHALL all be ResearchGuard `0.4.11`. Logic Writing MUST NOT import an old member package, invoke an old module command, locate a sibling checkout, try another member when the selected member is unavailable, or execute ExperimentGuard or the ResearchGuard umbrella route.

#### Scenario: LogicGuard member is available
- **WHEN** Logic Writing preflights the LogicGuard semantic owner
- **THEN** it SHALL verify `researchguard --version` and `researchguard logic --help`, bind `primary:researchguard:logic`, and run no alternate provider probe

#### Scenario: ResearchGuard console is absent
- **WHEN** the `researchguard` console cannot be resolved
- **THEN** Logic Writing SHALL return `provider_unavailable` and SHALL NOT import `logicguard`, run `python -m logicguard`, or select SourceGuard or TraceGuard

#### Scenario: Member capability times out
- **WHEN** the selected ResearchGuard member capability probe exceeds its configured bound
- **THEN** Logic Writing SHALL preserve the timeout as visible provider evidence and terminate that provider preflight without recovery through another path

#### Scenario: Unsupported ResearchGuard version is installed
- **WHEN** the distribution metadata or console output is not exactly `0.4.11`
- **THEN** Logic Writing SHALL return a visible blocked identity result and SHALL NOT execute the selected member probe or a fallback provider

#### Scenario: Out-of-scope member is requested
- **WHEN** a caller requests `experimentguard` or the ResearchGuard umbrella `run` route
- **THEN** Logic Writing SHALL return a visible scope block and SHALL execute zero ResearchGuard commands

#### Scenario: Provider identity and member topology are current
- **WHEN** a supported direct member is selected and the installed distribution, console, and exact three-member topology all report ResearchGuard `0.4.11`
- **THEN** the provider preflight SHALL continue only to that selected member

#### Scenario: Provider failure does not trigger fallback
- **WHEN** the selected provider owner fails or times out
- **THEN** the router SHALL preserve the failure or timeout boundary and SHALL NOT retry through another member, legacy module, or umbrella command
