# World Feasibility

Use WorldGuard for generic world claims that can be checked independently of story style. Check both individual candidates and assembled route traces.

## Candidate Checks

- Time: can the traveler arrive, visit, eat, rest, and move within the available window.
- Space: distances, walking paths, hills, stairs, accessibility, and neighborhood clustering.
- Resource: tickets, reservations, money, stamina, battery, luggage, language, payment methods.
- Access: opening hours, closure, entry rules, age rules, bag rules, safety rules.
- Weather: checked or explicitly missing weather evidence for rain, heat, cold, wind, daylight, visibility, air quality, indoor/outdoor exposure, and severe-weather advisories.
- Norms: local customs, quiet hours, dress code, child suitability, etiquette.
- Conflict: mutually exclusive reservations, transport gaps, route segment conflicts.

## Route Stress Checks

- Daily timing and transfer load.
- Meal timing and hunger risk.
- Rest spacing and fatigue risk.
- Hotel check-in, check-out, luggage, late return, and neighborhood return safety.
- Weather exposure across the whole route, including whether weather-sensitive days use forecast, historical/archive, climate/seasonal, or alert/advisory evidence appropriate to the trip date.
- Booking or queue chokepoints.
- Fallback reachability from the actual route position.

## Statuses

Use `pass`, `partial`, `gap`, `fail`, `boundary_exceeded`, `stale`, or `not_applicable`.

Missing current evidence is `gap` or `stale`, not a weak pass. A beautiful travel story cannot convert a feasibility gap into a pass.

Weather feasibility that is based only on generic seasonal language is `partial` for far-future planning and `gap` for past or near-future dated trips when daily weather affects the route.

## World Check Card

```text
world_check_id -> target_type(candidate|route|edge|hotel_strategy) -> target_id -> guards_checked -> status -> missing_slots -> counterexamples -> boundary -> next_action
```

## Weather Check Card

```text
weather_check_id -> date_relation(past|near_future|far_future|undated) -> source_class(weather_forecast|weather_historical|weather_climate|weather_alert|missing) -> covered_dates -> affected_route_nodes -> route_adjustments -> fallback_ids -> status -> boundary -> next_action
```
