# current-researchguard-provider Specification

## Purpose
Defines how Logic Writing finds ResearchGuard, which direct members it may execute, and how unsupported provider requests stay visibly blocked.
## Requirements
### Requirement: The minimum ResearchGuard version is declared once

The system SHALL declare the minimum ResearchGuard version once, as `RESEARCHGUARD_MIN_VERSION` in `skills/logic-writing/scripts/_common.py`, and SHALL accept any ResearchGuard at or above that minimum. No prompt, schema, fixture or check SHALL require an exact ResearchGuard version.

#### Scenario: A newer ResearchGuard is installed

- **WHEN** the `researchguard` console reports a version at or above the minimum
- **THEN** the provider preflight continues to the selected member's help probe

#### Scenario: ResearchGuard is missing or too old

- **WHEN** no `researchguard` console can be found, or it reports a version below the minimum
- **THEN** the preflight returns `provider_unavailable` or `blocked` with one message that names the minimum, the version found and the install command, and runs no member command

### Requirement: The console is found in the running Python or on PATH

The system SHALL use the console recorded by the ResearchGuard distribution installed in the running Python and SHALL require that console to report the distribution's version. When the running Python has no ResearchGuard distribution, the system SHALL use the `researchguard` command on PATH.

#### Scenario: ResearchGuard lives in another environment

- **WHEN** ResearchGuard is installed with pipx or in a separate virtual environment whose console is on PATH
- **THEN** the preflight uses that console, records `console_source` as `path`, and applies the same minimum-version rule

### Requirement: The direct member set is exact

The system SHALL expose exactly three active direct ResearchGuard members, LogicGuard, SourceGuard and TraceGuard, each through one `researchguard` member command and one primary path.

#### Scenario: Each direct member is selected alone

- **WHEN** a request names LogicGuard, SourceGuard, or TraceGuard
- **THEN** exactly the corresponding ResearchGuard member command is probed and no other member is invoked

#### Scenario: Unknown provider is named

- **WHEN** a caller names a provider that is not one of the three members, a scope-out provider, WorldGuard, Documents or PDF
- **THEN** the preflight returns `blocked` and runs no command

### Requirement: ExperimentGuard and umbrella requests are out of scope

The system SHALL treat ExperimentGuard and the ResearchGuard umbrella route as unsupported in Logic Writing, SHALL return a visible scope-out result, and SHALL execute zero ResearchGuard commands for either request.

#### Scenario: ExperimentGuard is requested

- **WHEN** a caller requests ExperimentGuard through a Logic Writing provider path
- **THEN** the request is blocked as outside the current product scope and no provider command or fallback member is run

#### Scenario: Umbrella composition is requested

- **WHEN** a caller requests an umbrella ResearchGuard operation or a multi-member composition
- **THEN** the request is blocked as outside the current product scope and the system does not silently fan out to the three direct members

### Requirement: Provider results remain provider-owned

The system SHALL consume a ResearchGuard member result as it is, SHALL NOT write a result on the member's behalf, and SHALL NOT strengthen a non-pass result. A passing preflight SHALL NOT count as evidence that native domain work ran.

#### Scenario: Native result is non-pass

- **WHEN** the selected member returns a failed, blocked, stale, bounded, partial, or not-run result
- **THEN** Logic Writing reports that status unchanged and does not retry through another member

### Requirement: Provider-root overrides cannot create a second ResearchGuard path

The system SHALL reject a provider-root override for LogicGuard, SourceGuard, or TraceGuard before running any command.

#### Scenario: Caller supplies a member provider root

- **WHEN** a caller supplies `--provider-root` while preflighting one of the three ResearchGuard members
- **THEN** the preflight returns a visible blocked result before executing any provider command

### Requirement: An installed copy matches the source

The system SHALL install the skill with `scripts/install_skill.py --target <skills dir>`, which copies the runtime files and leaves out repository-only fixtures and regression runners, and `--check` SHALL report every file-set or byte difference between an installed copy and the source.

#### Scenario: Installed copy was edited

- **WHEN** an installed file differs from the source
- **THEN** `install_skill.py --check` exits 1 and names the differing file
