## Purpose

Defines the current ResearchGuard provider identity and the narrow set of direct members that Logic Writing may execute, while making unsupported provider requests visibly blocked and preventing stale or self-authored evidence from being treated as current.

## ADDED Requirements

### Requirement: Current provider identity is explicit

The system SHALL identify ResearchGuard version 0.5.0 as the current provider dependency and SHALL require the distribution metadata, the `researchguard` console identity, and the reported console version to agree before a member request can be considered current.

#### Scenario: Current provider identity passes

- **WHEN** a request selects a supported direct member and the installed distribution and console both report ResearchGuard 0.5.0
- **THEN** the provider preflight reports a current identity and continues only to that selected member

#### Scenario: Provider identity mismatch is visible

- **WHEN** distribution metadata, console output, or configured current version differs from 0.5.0
- **THEN** the request is blocked with an identity-mismatch reason and no member command is executed

### Requirement: The direct member set is exact

The system SHALL expose exactly three active direct ResearchGuard members—LogicGuard, SourceGuard, and TraceGuard—and SHALL reject missing, extra, duplicate, or overlapping active-member bindings.

#### Scenario: Each direct member is selected alone

- **WHEN** a request names LogicGuard, SourceGuard, or TraceGuard
- **THEN** exactly the corresponding ResearchGuard member command is selected and no other member is invoked

#### Scenario: Topology drift is rejected

- **WHEN** the active binding set is not exactly the three declared members or a member has multiple conflicting console bindings
- **THEN** topology validation fails before release or installation evidence can pass

### Requirement: ExperimentGuard and umbrella requests are out of scope

The system SHALL treat ExperimentGuard and the ResearchGuard umbrella route as unsupported in Logic Writing 4.0.0, SHALL return a visible scope-out/blocking result, and SHALL execute zero ResearchGuard provider commands for either request.

#### Scenario: ExperimentGuard is requested

- **WHEN** a caller requests ExperimentGuard through a Logic Writing provider path
- **THEN** the request is blocked as outside the current product scope and no provider command or fallback member is run

#### Scenario: Umbrella composition is requested

- **WHEN** a caller requests an umbrella ResearchGuard operation or a multi-member composition
- **THEN** the request is blocked as outside the current product scope and the system does not silently fan out to the three direct members

### Requirement: Provider evidence remains provider-owned

The system SHALL consume ResearchGuard result and receipt material through opaque, identity-bound references and SHALL only count a reference toward Logic Writing closure when provider qualification is current, the member and input match, fingerprints/locators match, and the native status is terminal and passed.

#### Scenario: Qualified current evidence contributes

- **WHEN** a direct-member result has ResearchGuard 0.5.0 qualification, matching member/input identities, matching immutable locator fingerprints, and provider-owned passed status
- **THEN** Logic Writing may bind the reference to its adapter envelope without changing native fields

#### Scenario: Self-authored or non-terminal evidence is rejected

- **WHEN** a caller supplies a self-consistent fake native receipt, a foreign member receipt, a stale qualification, or a blocked/failed/skipped/not-run/non-terminal status
- **THEN** validation rejects the reference or marks it non-contributing and never treats it as current provider evidence

### Requirement: Installed projection matches the current source

The system SHALL expose a SkillGuard-compiled consumer projection whose declared files, hashes, version, provider contract, and route behavior match the validated Logic Writing 4.0.0 source, and SHALL fail currentness checks when projection drift exists.

#### Scenario: Current installation is verified

- **WHEN** the source contract is compiled and the staged projection is activated successfully
- **THEN** installed currentness and route smoke checks pass for investigation, academic, fiction, travel, and the academic child handoff

#### Scenario: Stale installation is visible

- **WHEN** the installed projection still declares Logic Writing 3.0.1 or ResearchGuard 0.4.5, or its manifest differs from the compiled source
- **THEN** installation currentness fails and the release cannot claim synchronized installation
