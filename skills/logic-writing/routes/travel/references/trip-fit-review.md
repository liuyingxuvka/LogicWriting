# Trip Fit Review

Trip Fit Review is the final human-like suitability check. It is not a fact check; it consumes candidate, source, feasibility, route trace, lodging, and story-output evidence.

## Required Dimensions

- age;
- stamina;
- companions;
- relationship or group style when relevant;
- interests;
- pace;
- rest;
- budget;
- safety;
- weather_resilience;
- fallback_fit;
- food fit;
- hotel and lodging fit for overnight trips.

Each dimension row declares `input_field` and exact current `input_values`. The validator binds them to traveler profile or trip context; changing the profile without refreshing fit rows is a failure. A child under 12 or traveler over 70 requires `child_or_elderly_protection`. A material accessibility need requires `accessibility`.

## Recommended Dimensions

- accessibility;
- language;
- queue tolerance;
- story variety;
- emotional tone;
- photo or food timing;
- children or elderly protection;
- shopping or brand interest;
- night-return comfort.

## Outcomes

- `pass`: suitable for the stated claim level.
- `downgraded`: usable only at a lower claim level or with warnings.
- `revise`: route needs repair before output.
- `human_review`: user choice is needed because multiple route values conflict.
- `blocked`: missing evidence or constraints prevent useful advice.

The review should ask: would a careful human travel advisor send this route to this traveler, with these caveats, today?
