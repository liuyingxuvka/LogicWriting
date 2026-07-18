# predecessor-retirement Specification

## Purpose
TBD - created by archiving change expand-logic-writing-four-routes. Update Purpose after archive.
## Requirements
### Requirement: Replacement is recoverable before predecessor retirement
The system SHALL preserve source and release identities, validate the `2.1.0` source, activate a recoverable installed projection, refresh one global route, publish the GitHub release, and pass fresh-clone validation before changing predecessor visibility.

#### Scenario: Privatization is attempted before fresh-clone validation
- **WHEN** either predecessor repository is still public but replacement fresh-clone installation has not passed
- **THEN** visibility change SHALL be blocked

### Requirement: Old active skill ids have zero authority
Before predecessor visibility changes, installed `storyline-design` and `travel-story-planner` skill directories SHALL be absent from the active skill root, and the current global router SHALL resolve their supported user intents only to `logic-writing`.

#### Scenario: Old skill remains installed
- **WHEN** an old skill id still has an active installed entrypoint or current router authority
- **THEN** predecessor retirement SHALL be blocked

### Requirement: Repository privatization follows dependency order
The release workflow SHALL make `travel-story-planner` private before `storyline-design-skill`, because the former publicly depends on the latter, and SHALL run replacement health checks between the two changes.

#### Scenario: Travel repository becomes private
- **WHEN** authenticated GitHub evidence reports `travel-story-planner` as `PRIVATE` and anonymous access is non-visible
- **THEN** the workflow SHALL rerun replacement route, install, and public-release health checks before changing Storyline visibility

#### Scenario: First health check fails
- **WHEN** replacement health fails after Travel visibility changes
- **THEN** the workflow SHALL stop
- **AND** restore Travel visibility to public before retrying or ending

### Requirement: Private visibility has two-sided evidence
Each predecessor visibility change SHALL require authenticated `PRIVATE` evidence and anonymous non-visibility evidence for the exact repository, plus a current replacement health receipt.

#### Scenario: Authenticated view is private but anonymous repository remains visible
- **WHEN** the two visibility observations disagree
- **THEN** retirement SHALL remain blocked and no later repository SHALL change

### Requirement: Repository deletion remains user-owned
This change SHALL NOT delete either predecessor repository and SHALL report private visibility as the terminal repository disposition.

#### Scenario: Private repositories are healthy
- **WHEN** both predecessor repositories are private and replacement health remains current
- **THEN** the workflow SHALL record completion without issuing repository deletion commands
