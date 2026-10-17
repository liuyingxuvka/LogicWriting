## Purpose

This capability proves that a clean installed consumer contains every
route-reference and example payload required by its selected writer path.

## ADDED Requirements

### Requirement: Selected route resources are closed

The consumer projection SHALL include every manifest-declared runtime source
and fixture reference reachable from the selected route. A closure check SHALL
resolve local links and report each missing resource with its disposition.

#### Scenario: Nested fiction references are required
- **WHEN** a clean consumer selects the fiction route
- **THEN** its nested fiction references and linked example payloads SHALL be present
- **AND** a missing required file SHALL fail closure

#### Scenario: Unselected route remains unloaded
- **WHEN** a task selects travel only
- **THEN** the closure result SHALL verify travel resources without silently treating all fiction resources as required
