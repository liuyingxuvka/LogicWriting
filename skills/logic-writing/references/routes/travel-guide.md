# Travel-guide route

The travel route owns substantive itineraries, destination guides, route
alternatives, lodging strategy, traveler-fit recommendations, traveler-native
prose, and final-guide closure. A quick list of attractions is out of scope.

## Reader composition v2

The travel composition requires `trip_plan`, relative to its file. The brief
validates that trip model and every route, fit, texture and fallback reference.
Guide structure lives only in this composition. World, route, fit and
recommendation results and the allowed claim level are derived; source
currency uses check dates.

Select the real guide kind: itinerary, destination guide, lodging strategy,
route plan, traveler-fit recommendation, or revision. Plan narrative body
sections separately from the operational appendix, source-boundary zone, and
recheck zone. Each body section changes a traveler state and hands a concrete
choice or condition to its next consumer. Candidate lists and route nodes are
content inputs, not a paragraph template.

## Consumer resource closure

The selected travel route requires the [traveler-native guide compiler](../../routes/travel/references/traveler-native-guide-compiler.md),
[runtime workflow](../../routes/travel/references/runtime-workflow.md),
[traveler profile](../../routes/travel/references/traveler-profile.md), and
[negative-evidence and fallback contract](../../routes/travel/references/negative-evidence-and-fallback.md).

Build the guide ArtifactMap from current bytes. Review actual spans for guide
kind, traveler fit, unit responsibility and handoffs, narrative body,
operational appendix, risk/fallback, source recheck, and local texture. Facts,
prices, availability, feasibility, and fit remain owned by native evidence;
the writer owns integration and wording.

## Start with the traveler and time boundary

Record trip dates, planning timestamp, date relation, requested claim level,
locations, companions, ages, stamina, walking tolerance, accessibility needs,
interests, pace, rest, budget, safety concerns, food needs, lodging preferences,
and travel style. A missing material preference is a visible input gap.

Choose weather and hazard evidence by time mode: observed/archive evidence for
past trips, current forecast plus official alerts for near-term or day-of
travel, and climate evidence with an explicit recheck boundary for far-future
or undated plans. Weather prose cannot strengthen source freshness.

## Build evidence and feasible routes

Use SourceGuard for discovery depth and role coverage. Preserve official facts,
transport/map evidence, booking or price evidence, traveler-experience reports,
negative experience, accessibility/safety material, fallback evidence, and the
relevant weather/alert sources. Snippets and unavailable pages remain leads or
access gaps.

Create experience candidates with source roles, negative signals, and
WorldGuard checks. WorldGuard owns event, space, time, resource, access,
capability, authority, conflict, and norm feasibility through saved reports.
The trip plan owns its route options and movement sequence; temporal checks come from those saved WorldGuard reports. The route validator
checks that candidate and movement edges actually bind those native results.

Validate time, distance, transport, opening/access state, capacity, queue,
weather, closure, cost, pace, stamina, companions, interests, rest, safety,
lodging, and accessibility. A route that is attractive but infeasible does not
become feasible when rewritten smoothly.

## Compare fit, friction, and fallbacks

Bind every recommendation to candidate, route, WorldGuard, traveler-fit, and
source evidence. Preserve negative evidence and operational friction, including
fatigue, queues, transfers, cost uncertainty, reservation needs, closures, and
safety limits. Every material failure point needs the nearest reachable
fallback, the route nodes it replaces, the nodes from which it is reachable,
its own evidence, and a recheck instruction.

LogicGuard compares the recommended route with live alternatives and limits.
The travel route remains the only final owner.

Keeping the trip model as a `travel-story-planner.plan.v2` plan is optional.
When you keep one, it is the model the guide is written from: check it with
`routes/travel/scripts/validate_travel_plan.py` and pass the travel route
composition with `--composition`, so every `route_refs`, `fallback_id`,
`risk_id` and `reachable_from_route_node_ids` entry must name an id in the plan.

## Run the trip model checks

Run these from the skill root with Python 3.10 or newer; each exits 0 only
when its input passes. Put each failing check with its issue codes in the
audit note.

- `python routes/travel/scripts/validate_travel_plan.py <plan.json> --json`
  checks the optional trip plan; add `--composition <travel-composition.json>`
  to check that the composition names ids in the plan.
- `python routes/travel/scripts/validate_travel_text_outputs.py --guide <guide.md> --review <review.json> --json`
  checks the actual guide text: internal labels, bullet-only text, local
  texture, named risks and fallbacks, weather evidence and day headings.
  `--review` is the reverse guide review; a guide that mentions weather needs
  it.

## Project into traveler-native prose

Compile checked route cards through the shared reader-projection kernel. Do not
invoke the fiction route. Use lived sequence, concrete local detail, real
choices, operational cues, and specific fallbacks, followed by a compact
operational appendix when useful. The shared kernel may improve handoffs and
reader state, but it may not invent places, prices, availability, feasibility,
fit, or source status.

For each important day or section, record the incoming traveler/reader state,
contribution, changed state, unresolved constraint, exact next consumer,
register owner, changed effect of repetition, and current model-artifact span.

## Reverse-review the actual guide

Reverse review the actual guide (its ArtifactMap binds the current bytes) for
trip id, allowed claim level, evidence, day
headings, weather mode and hazards, feasibility, traveler fit, named risks,
reachable fallbacks, local texture, shopping/food/rest details when promised,
and internal workflow leakage. A missing current limitation or an observation
not present in the actual guide blocks closure.

The internal route pack under `routes/travel/` preserves the verified base,
positive, exact-negative, time-mode, feasibility, fit, fallback, and
traveler-native text families. It is not a separately installed skill.

## Independent actual-text review

One context independent of the writer may assess this route's semantic
obligations and the eight reader dimensions together. Preserve both existing
`route_review` and `ReaderJudgment`, including actual spans, reverse outline,
required dimensions, scores and their current fingerprint bindings. If a
revision round resolves none of the actual defects, stop and return the artifact
with the audit note.

## From the entrypoint

Bind the traveler profile, time/weather mode, source roles, candidates,
WorldGuard feasibility in one itinerary `trip_plan`, lodging, fit, negative evidence,
reachable fallbacks, the same trip plan and guide units, and review of the
actual guide. Use the shared reader chain for the guide's text bindings.
