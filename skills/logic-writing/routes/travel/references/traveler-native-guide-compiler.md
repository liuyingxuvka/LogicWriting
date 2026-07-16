# Traveler Native Guide Compiler

Use this reference after Guard Mesh evidence exists and before any substantive traveler-facing guide is delivered. It consumes Logic Writing's shared model-room / reader-room projection boundary, while all feasibility, fit, time, fallback, and guide fields remain travel-owned. It never invokes the fiction route.

## Two Rooms

Model room contains candidate ids, route traces, source roles, feasibility checks, evidence boundaries, validation ids, and closure rows. Traveler room contains the final guide prose a traveler can read directly.

The traveler-facing guide must not expose internal workflow labels, ids, validator wording, or skill-test language. A methods appendix may expose them only when the user explicitly asks for methods.

## Traveler Native Projection

Before final prose, create a guide projection:

```text
reader_visibility -> source_model_surfaces -> blocked_internal_terms -> traveler_facing_brief -> claim_boundary
```

The traveler-facing brief answers in ordinary language:

- what this route feels like for the traveler;
- how the day begins, builds, rests, peaks, and exits;
- what concrete food, shopping, lodging, rest, and risk choices matter;
- which claims are current, downgraded, or require recheck.
- which weather claims are checked, downgraded, or require recheck when dated routes or weather-sensitive nodes matter.

## Reader Structure Contract

The traveler-facing guide should read like a human guide, not a table dump. For multi-day artifacts, preserve a light structure:

```text
route_intro -> optional_trip_overview -> day_or_date_heading[] -> prose_body_per_day -> risk_and_fallback_notes -> source_boundary -> recheck_notes
```

Day or date headings can be simple labels such as "Day 1", "June 26", "First afternoon", or localized equivalents. They are reader anchors, not model ids. Under each heading, prose remains the main form; headings do not excuse bullet-only output.

## Travel Scene Contracts

Each important route day and important route node needs a travel scene contract:

```text
scene_id -> kind(day|node) -> entry_state -> intended_traveler_experience -> obstacle -> turn -> exit_state -> contribution -> local_texture_needs -> risk_trigger_ids -> fallback_ids -> contract_status
```

The contract passes only when the day or node changes traveler state, route feasibility, experience promise payoff, risk mitigation, rest, food, shopping, lodging, or continuity. A day or node that only adds another place name should be revised, merged, cut, or scoped out.

## Experience Promises

Guide promises behave like story promises. If the guide promises local food, couple pacing, shopping, hotel comfort, recovery, pitfall avoidance, or local texture, it must pay the promise with concrete material or narrow the claim.

Use one row per key or major promise:

```text
promise_id -> promise_text -> importance -> expected_payoff -> payoff_status -> concrete_payoff -> candidate_ids -> fallback_ids -> evidence_refs
```

Allowed payoff statuses are `paid`, `inverted`, `deferred_with_boundary`, `downgraded`, and `human_review`. Do not treat attractive prose as payoff when concrete food, shop, lodging, rest, or risk material is missing.

## Day Interfaces

Multi-day guides need adjacent day interfaces:

```text
interface_id -> previous_day -> next_day -> previous_output -> current_input -> traveler_state_before -> traveler_state_after -> unresolved_choices -> promise_movements -> status
```

Generic handoffs such as "continue the route" or "keep the day flexible" are not enough. The interface should preserve location, stamina, mood, luggage, shopping state, unresolved bookings, weather residue, checked or missing weather evidence, and open experience promises when they matter.

## Weather Evidence Summary

For a dated or weather-sensitive guide, build a weather evidence summary before final prose:

```text
weather_summary_id -> date_relation -> source_type(forecast|historical|climate|alert|missing) -> covered_dates -> affected_days -> route_adjustments -> claim_status(checked|partial|downgraded|missing) -> recheck_note
```

Extend the row with hazard detail whenever weather changes route feasibility:

```text
weather_source_mode(forecast|forecast_alert|historical_observed|archive|climate|mixed) -> checked_hazards(precipitation|heat|wind|storm|thunderstorm|typhoon|air_quality|alert) -> missing_or_downgraded_hazards -> fallback_ids
```

The traveler-facing text should translate this into ordinary language. It should not say "if it rains" as a generic caveat when the trip dates require a forecast, historical/observed check, alert/advisory check, or explicit downgrade.

## Local Texture Index

For a substantive multi-day city guide, build a local texture index with:

- food: named dishes, food types, restaurants, markets, cafes, or food areas;
- shopping: local shops, department stores, brands, markets, pharmacy or gear stops, souvenirs;
- rest: hotel buffers, quiet cafes, parks, indoor breaks, low-load segments;
- negative_signals: queues, tourist traps, price surprise, reservation friction, weak value, weather, fatigue, language, payment, or transport friction;
- named_fallbacks: nearby replacements tied to concrete triggers.

Missing texture does not become confident prose. It becomes a search action, a downgrade, or a visible gap.

## Reverse Guide Review

After final traveler-facing text exists, run a reverse guide review from the actual text:

```text
final_artifact_ref -> final_artifact_path -> final_artifact_sha256 -> observed_days -> observed_day_headings -> observed_local_food_details -> observed_shopping_details -> observed_rest_nodes -> observed_weather_evidence -> observed_weather_source_type -> observed_weather_source_mode -> observed_weather_checked_hazards -> observed_weather_missing_or_downgraded_hazards -> weather_claim_status -> weather_route_adjustments -> observed_risks -> observed_fallbacks -> internal_label_leakage -> promise_alignment_status -> continuity_status -> status
```

The final artifact path must be repository-contained and exist. Its SHA-256, generated trip id, reverse-review path, and reverse-review SHA-256 bind the same current bytes. Observed headings and named food/shop/rest details must actually occur in those bytes.

Return to the earliest affected surface when the review finds internal jargon leakage, missing promise payoff, unsupported facts, repeated day function, weak local texture, generic risk notes, missing weather evidence, missing day headings, or missing continuity.

## Output Failure Conditions

Traveler-facing guide output fails when:

- it exposes labels such as candidate pool, route trace, SourceGuard, TraceGuard, WorldGuard, Guard Mesh, validation id, or skill-test language;
- it reads mostly as bullets or cards rather than guide prose;
- it promises local food, shopping, hotels, couple pacing, recovery, or avoidance but lacks concrete payoff;
- risks lack triggers, affected traveler, mitigation, and named fallback behavior;
- multi-day plans lack day-to-day state handoff;
- multi-day traveler-facing guides lack reader-visible day or date headings;
- dated weather-sensitive guides mention weather without checked, partial, downgraded, or missing-with-boundary weather evidence;
- no reverse guide review is bound to the final text.
