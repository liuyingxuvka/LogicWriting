# Negative Evidence And Fallback

Negative evidence is a core planning surface. It is not an appendix.

## Pitfall Ledger

Use one row per material pitfall:

```text
pit_id -> node -> issue -> affected_traveler -> source_ids -> severity -> trigger_condition -> mitigation -> fallback_ids -> status
```

Common issue types:

- closure or changed opening hours;
- queue, crowding, capacity, or sellout;
- transport delay, transfer complexity, last-service risk;
- long walking, hills, stairs, heat, cold, rain, or fatigue;
- price surprise, tourist trap, menu mismatch, reservation friction;
- safety, scam, accessibility, child or elderly unsuitability;
- weak experience value relative to effort;
- language or payment friction.

Pitfalls are too generic when they only say "watch weather", "avoid queues", or "be careful". A usable pitfall needs an affected node, affected traveler, trigger condition, mitigation, named fallback ids, and status.

## Fallback Ledger

Use one row per fallback:

```text
fallback_id -> candidate_id -> replaces_route_node_ids -> reachable_from_route_node_ids -> trigger -> travel_time_delta_minutes -> cost_delta -> fit_notes -> source_ids -> world_check_id -> status -> boundary
```

Each important route node should have at least one realistic fallback in the single deep workflow. Fallbacks should be near enough to use when the traveler is already in the area, unless explicitly marked as a whole-route replacement.

Every replacement and reachable-from node must exist. At least one declared reachable-from node on the same trace must reach each replaced node through the exact directed movement-edge chain.

Fallbacks that only say "rest" or "go shopping" are not enough for traveler-native guide closure. Name the nearby area, shop, cafe, hotel buffer, indoor site, or route-shortening action whenever source support allows.

## Mid-Trip Change

When the traveler changes their mind mid-trip, preserve current location, time, stamina, weather, hunger, and transport state. Rebuild only the affected downstream route, but refresh any facts that now matter.
