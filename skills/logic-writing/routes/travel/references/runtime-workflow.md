# Runtime Workflow

Use this reference for every Travel Story Planner run after the skill is triggered. The workflow has one fixed Guard Mesh route. Missing evidence causes downgrade or block; there is no selectable lighter success route.

## Claim Levels

- `initial_plan`: enough structure to compare route options, but live facts need current recheck.
- `bookable`: current source checks support reservations, timing, transport, and key risks.
- `day_of`: current checks support same-day execution, including weather, closures, transport, queues, and nearby fallbacks.

If evidence is missing for the requested level, downgrade the output instead of writing confident prose.

## Flow

1. Create exactly one `trip_context` with trip id, destination, planning timestamp, timezone, dates, day ids, overnight/nights, requested claim level, allowed claim level, and evaluation mode. The validator derives `past`, `day_of`, `near_future`, or `far_future` from the timestamp and dates.
2. Capture traveler profile, budget, interests, constraints, lodging needs, and desired claim level.
3. Read `guard-role-map.md` and keep simulation ownership explicit.
4. Use SourceGuard to build the experience candidate pool for attractions, food, hotels or lodging areas, shops, neighborhoods, activities, transport nodes, rest nodes, and fallbacks.
5. Preserve source roles and support boundaries before using any candidate in a route.
6. For dated trips, classify the weather evidence need before route finalization: forecast-first daily and hourly evidence for near-future trips, current forecast plus alert/advisory evidence for day-of readiness, observed or historical/archive weather for past trips, climate or seasonal evidence only for far-future route shape, and alert/advisory sources when rain, heat, wind, storm, thunderstorm, typhoon, air quality, safety, visibility, or transport disruption may matter.
7. Create a negative evidence ledger and fallback ledger before route finalization.
8. Use WorldGuard to check candidate feasibility: time, space, access, resources, norms, weather, safety, and conflict.
9. Use TraceGuard to build route traces: primary, comfort, depth, weather or closure, lodging-sensitive, and mid-trip replanning branches when material.
10. Use WorldGuard again to stress-test assembled day routes and movement edges.
11. Run trip-fit review for the actual traveler profile.
12. Review recommendation support: what evidence justifies this route over alternatives, and where wording must be downgraded.
13. Build traveler-native guide compiler surfaces: guide projection, travel scene contracts, experience promises, day interfaces when multi-day, local texture index, weather evidence summary, day-heading plan, and reverse-guide review plan.
14. Project routes into story-shaped traveler-facing prose and an operational appendix without exposing model-room labels. Multi-day guides need visible day or date headings with prose under each day.
15. Run reverse-guide review against the actual traveler-facing text and return to the earliest failed surface when it finds internal leakage, weak local texture, missing promise payoff, generic risks, missing weather evidence, missing day headings, or broken day handoff.
16. Use FlowGuard to check process order, stale evidence, installed-copy sync, router evidence, and final claim freshness.
17. Use the Travel-owned closure to report passed, partial, downgraded, blocked, and skipped checks.
18. Write `travel-story-planner.plan.v2`, materialize the final guide, bind its repository path and SHA-256, and run the native regression owner. A report or checkbox is not executable closure.

The current executable schema has no former-schema reader. A non-current plan is an explicit repair item.

## Date-Aware Weather And Hazard Handling

- Near-future dates: use forecast sources before historical averages. Seek daily outlook plus hourly precipitation or rain-window evidence when available; check high temperature or heat-index risk, humidity, wind, storm or thunderstorm risk, typhoon risk where regionally relevant, air quality where material, and official alerts/advisories when safety or transport could be affected.
- Day-of or near-day execution: use same-day forecast and alert/advisory sources before claiming bookable or executable timing for weather-sensitive days.
- Past dates: use historical, observed, or archive weather evidence when the guide discusses rain, heat, wind, visibility, storm, typhoon influence, alerts, or outdoor comfort. If no source can be inspected, downgrade the weather claim and say what remains unchecked.
- Far-future dates: use climate or seasonal sources for planning shape only, and require a pre-departure forecast plus alert/advisory recheck before confident execution.
- No fixed dates: use climate or seasonal evidence only as a planning boundary, not as a checked daily condition.

Weather fallback branches must be named and tied to triggers. Examples: "rain window after 15:00 moves the viewpoint to the indoor gallery", "heat index makes the park a morning-only node", "typhoon or storm advisory blocks the waterfront and shifts to hotel-nearby indoor food", or "poor air quality moves a long walk to a transit-linked museum".

## Replanning Trigger

Restart from the earliest affected stage when the user changes:

- destination, dates, budget, traveler profile, lodging area, or interests;
- claim level;
- a must-see or must-avoid location;
- current position during a trip;
- weather, closure, transport, booking, queue, luggage, or safety status.

Do not patch a story route without refreshing the affected candidates, evidence, feasibility, route traces, traveler-native guide compiler surfaces, and fit review.
