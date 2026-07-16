# Source Portfolio

Use SourceGuard for source discovery planning and source-role boundaries. A broad bibliography is not enough; each source must have a role and a support boundary.

## Required Source Classes

- `official_facts`: attraction, operator, government, transit authority, museum, event, or ticket platform.
- `transport_map`: maps, routing tools, operator schedules, transfer constraints, last-service checks.
- `weather_forecast`: forecast, hourly or daily outlook, precipitation probability, rain window, heat or heat index when available, humidity, wind, thunderstorm or storm risk, visibility, air-quality forecast, and other forecast hazards for near-future dated trips.
- `weather_historical`: historical, archive, or observed weather for past dated trips, including observed precipitation, high/low temperature, wind, storm, typhoon influence, and alert/advisory aftermath when available.
- `weather_climate`: seasonal climate, rainy season, heat/cold norms, daylight norms, typhoon season norms, or long-range planning weather for far-future or undated trips.
- `weather_alert`: typhoon, storm, thunderstorm, flood, heat, wind, transport-disruption, air-quality, public-safety, or official advisory sources.
- `booking_price`: ticket, restaurant reservation, menu, price range, cancellation, queue, or capacity source.
- `traveler_experience`: blogs, forums, recent reviews, social posts, trip reports, local guides.
- `negative_experience`: complaints, bad reviews, closure reports, queue reports, scams, transport friction, poor-fit warnings.
- `accessibility_safety`: accessibility details, safety advisories, family or elderly suitability, language barriers.
- `hotel_lodging`: hotel official pages, booking rules, location maps, luggage policies, neighborhood safety, check-in/out constraints.
- `fallback_source`: nearby alternatives, indoor replacements, backup restaurants, alternate transport, or route-shortening sources.

## Source Role Rules

- Official facts can support current rules only when they are current and directly relevant.
- Traveler experience can support risk signals, fit signals, and practical friction, not official proof by itself.
- Negative reviews can identify risks, but repeated or recent independent signals are stronger than isolated complaints.
- Prices and booking availability need source date, source role, and recheck requirement.
- Weather sources need date relation, source role, coverage period, source mode, hazard coverage, and support boundary. A climate source cannot prove a past daily condition, and a historical source cannot prove a future forecast.
- Search results, snippets, and relevance are not evidence until source content is inspected.
- A source that supports a candidate does not automatically support route feasibility.
- A hotel source supports lodging strategy only within its location, access, luggage, and timing boundary.

## Source Coverage Row

Use one typed row per source. Class-keyed string arrays are former authority and are rejected.

```text
source_id -> source_class -> source_date -> coverage_period -> locator -> access_status -> content_sha256 -> can_support -> cannot_support -> freshness_status -> next_action
```

Candidates separately cite exact `source_ids` and the exact set of cited source classes in `source_roles`. Unknown ids or a mismatched role set block closure.

Missing high-value source classes must become search actions, access gaps, or claim downgrades.

## Weather Evidence Priority Rule

Known trip dates make weather a required source decision, not an optional caveat. Choose the source class by date relation:

- near-future trip dates inside a practical forecast window -> `weather_forecast` first, with daily and hourly precipitation/rain-window checks when available, high temperature or heat-index checks when relevant, wind and storm/thunderstorm checks when exposed routes matter, and `weather_alert` for heat, typhoon, storm, flood, air-quality, or transport-disruption risk;
- day-of or near-day execution -> current forecast plus official `weather_alert`/advisory checks before claiming executable weather-sensitive timing;
- past trip dates -> `weather_historical`, observed, or archive sources, including observed precipitation and hazard traces when available; do not imply a forecast is still checkable after the trip has passed;
- far-future trip dates -> `weather_climate`, with a pre-departure `weather_forecast` and `weather_alert` recheck before confident execution;
- undated planning -> `weather_climate` only supports broad seasonal planning.

For any dated or weather-sensitive route, maintain a hazard coverage row:

```text
weather_source_mode -> covered_dates -> checked_hazards(precipitation|heat|wind|storm|thunderstorm|typhoon|air_quality|alert) -> missing_or_downgraded_hazards -> affected_days -> route_adjustments -> fallback_ids -> claim_status -> recheck_note
```

If weather evidence is unavailable or cannot be inspected, record the source class and hazard as missing, downgrade any route claim that depends on outdoor comfort, visibility, severe weather, or weather-sensitive transport, and attach a named fallback instead of a generic "if it rains" caveat.

## Traveler-Experience Depth

For substantive guides, SourceGuard should search beyond official facts. Official sources support rules, hours, tickets, and access. Traveler-experience sources support fit, friction, queue patterns, practical enjoyment, and local texture. Negative-experience sources support risk triggers and fallback design.

High-value experience nodes such as attractions, restaurants, hotels or lodging areas, shops, and neighborhoods should have both a positive fit signal and a limiting or negative signal before they are used as confident guide material.
