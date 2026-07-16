# Guard Role Map

Use this map before planning routes. Travel Story Planner coordinates these surfaces; it does not collapse them into one prompt.

## Ownership

| Surface | Owner | Owns | Does Not Own |
| --- | --- | --- | --- |
| Experience candidate discovery | SourceGuard | candidate discovery, source classes, source role, source gaps, negative signals, access gaps | final route assembly or final recommendation |
| Candidate and route feasibility | WorldGuard | time, space, resource, access, weather, norm, conflict, boundary status | candidate discovery or story prose |
| Route trace assembly | TraceGuard | temporal route trace, route branches, movement edges, weakest links, fallback links, gap handoff | live fact proof or final prose |
| Recommendation support | LogicGuard | whether the final recommendation is supported by candidate, trace, feasibility, fit, and limitation evidence | source discovery, route building, or live fact checking |
| Reader projection | Logic Writing shared reader kernel | traveler-native journey sequence from checked route cards | inventing facts, hiding gaps, or validating feasibility |
| Process freshness | FlowGuard | stage order, invalidation, skipped checks, stale evidence, install sync, final claim boundary | travel domain facts |
| Travel runtime contract | Travel Story Planner | travel hard gates, validators, failure fixtures, and closure meaning | replacing Guard-family domain owners |
| Validation supervision | SkillGuard | exact declared-check identity, freshness, receipts, dependencies, and the sole enforced closure | inventing Travel semantics, failures, validators, or selectable modes |

## Required Handoffs

```text
traveler_profile
-> SourceGuard experience_candidate_pool
-> WorldGuard candidate_feasibility
-> TraceGuard route_trace_mesh
-> WorldGuard route_feasibility_stress
-> traveler_fit_review
-> LogicGuard recommendation_support
-> shared.reader_native_projection
-> FlowGuard / SkillGuard closure
```

## Handoff Rules

- SourceGuard output stays candidate-level until consumed by TraceGuard and WorldGuard.
- TraceGuard owns route order and competing route lines, but it cannot convert feasibility gaps into passes.
- WorldGuard non-pass statuses remain visible; downstream story prose may not smooth them away.
- LogicGuard support review happens before final recommendation wording, not after publishing the route.
- Shared reader projection happens last and may only use checked or downgraded route artifacts. It does not invoke the fiction route.
- Any missing or stale handoff becomes a closure blocker or downgrade.
