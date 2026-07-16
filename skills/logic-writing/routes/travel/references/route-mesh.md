# Route Mesh

Use TraceGuard to represent route traces and competing route storylines, not one smooth itinerary.

## Required Route Trace Types

- `primary`: balanced recommendation.
- `comfort`: lower walking, lower transfer risk, more rest.
- `depth`: deeper match to a strong interest.
- `weather_or_closure`: indoor or alternate route when checked weather evidence, closure, ticket, or queue risk triggers.
- `lodging_sensitive`: route variant affected by hotel area, luggage, check-in, check-out, or late-night return.

For small requests, the mesh can be compact, but a final practical plan still needs at least one fallback branch for each important risk.

## Route Trace Card

```text
trace_id
route_type
day_id
traveler_fit
story_arc
candidate_node_ids
movement_edges
time_windows
world_check_ids
weakest_links
fallback_ids
gap_handoffs
feasibility_status
evidence_boundary
downgrade_reason
```

When the route is dated and weather-sensitive, route traces should link the relevant weather check or weather-source boundary through `weakest_links`, `fallback_ids`, `gap_handoffs`, or `evidence_boundary`.

## Route Node Card

```text
route_node_id -> candidate_id -> trace_id -> time_window -> role_in_day -> source_ids -> world_check_id -> fallback_ids -> risk_ids -> status
```

Within each trace, route nodes are ordered authority. `movement_edges` must have unique ids and form the exact adjacent node chain in that order. A bag of valid-looking edges is not a route.

## Trace Rules

- Preserve route branches when evidence supports more than one good path.
- Do not choose the most elegant story if it hides a live risk, hotel constraint, poor fit, or feasibility gap.
- Record weakest links: transport, opening hours, stamina, weather evidence, booking, queue, food, safety, accessibility, lodging, or luggage.
- A route node with no candidate id, trace id, or world check id is unbound and cannot appear in final output.
- A route with unresolved critical gaps should be partial or downgraded.
- Route gaps should hand off back to SourceGuard when more source evidence is needed, or WorldGuard when feasibility modeling is missing.

## Weather Branch Rules

- Weather branches need concrete triggers such as sustained rain, high heat, strong wind, poor visibility, advisory status, or missing checked weather.
- A branch must name the affected day or node and a reachable fallback, not only say "be flexible".
- Past-date retrospective guides should use historical weather when discussing what should have happened on those dates; if unavailable, they must say the weather branch is illustrative rather than checked.
