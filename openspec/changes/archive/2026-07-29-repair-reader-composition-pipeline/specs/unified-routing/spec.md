## ADDED Requirements

### Requirement: Route decisions preserve the complete reader intent
The router SHALL preserve the user's artifact mode, language, audience, purpose, requested structure, heading policy, list policy, style, length, format, required content, forbidden content, reference examples, and unresolved material choices in one fingerprinted ReaderIntent while continuing to select the final owner only from the terminal deliverable.

#### Scenario: User supplies a fixed outline
- **WHEN** the user requests an academic artifact with locked headings and order
- **THEN** the academic route is selected and the complete fixed outline remains present in the route decision

#### Scenario: Style resembles another route
- **WHEN** a travel guide requests narrative warmth associated with fiction
- **THEN** the travel route remains the sole final owner and the style request is preserved without activating fiction

### Requirement: Material reader-intent conflicts block drafting visibly
The router and selected route SHALL resolve reader-intent precedence from explicit user requirements, route safety and evidence obligations, and route defaults in that order. A material unresolved conflict SHALL block final drafting with the conflicting fields and required decision visible.

#### Scenario: Required outline conflicts with required artifact form
- **WHEN** a locked user structure cannot satisfy a mandatory evidence or safety boundary
- **THEN** the route returns a visible reader-intent conflict instead of silently replacing the structure

### Requirement: Current request contracts reject legacy constraint baskets
The current runtime SHALL accept only the current WritingRequest and RouteDecision contracts and SHALL reject the former free-form constraints field, legacy schema versions, aliases, converters, and fallback readers.

#### Scenario: Legacy request is submitted
- **WHEN** a request relies on a v1 constraints mapping without current ReaderIntent
- **THEN** validation fails with a current-contract error and no alternate success path is attempted
