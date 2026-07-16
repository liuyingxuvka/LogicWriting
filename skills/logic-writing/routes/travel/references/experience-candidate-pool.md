# Experience Candidate Pool

Use SourceGuard to build the candidate pool before route traces are assembled. The pool is universal across destinations; do not hard-code city-specific categories into this core contract.

## Candidate Classes

Use the applicable classes for the requested trip:

- `attraction`: museum, landmark, garden, temple, venue, viewpoint, event, or experience site.
- `restaurant`: meal, snack, cafe, bar, market, food hall, or reservation target.
- `hotel`: hotel, lodging area, check-in point, luggage-storage point, or stay strategy.
- `shop`: brand, local shop, department store, market, pharmacy, gear stop, or souvenir node.
- `neighborhood`: walkable area, night district, waterfront, historic zone, or shopping street.
- `activity`: tour, performance, workshop, spa, theme park, cruise, hike, or hands-on experience.
- `transport`: station, transfer, pass, shuttle, ferry, taxi zone, or last-mile movement node.
- `rest`: park, quiet cafe, hotel rest, public seating, or low-load buffer.
- `fallback`: backup option tied to a risk trigger.

## Candidate Card

```text
candidate_id
class
name_or_area
trip_role
why_worth_considering
why_may_be_bad_fit
best_for
avoid_when
source_ids
source_roles
negative_signal_ids
world_check_id
freshness
access_status
candidate_status: candidate | usable | partial | gap | rejected | fallback_only
next_action
```

## SourceGuard Rules

- A candidate is not a recommendation.
- A search hit is not a candidate until source role, locator, access status, and support boundary are recorded.
- A high rating or popularity signal is not enough; record who it is good for and who it is bad for.
- Every final route node must reference a candidate id.
- Fallback nodes must also be candidates, not ad hoc prose.
- Hotels and lodging areas are candidates when the trip is overnight, multi-day, luggage-sensitive, or route-location-sensitive.
- If a candidate lacks negative or limiting evidence, mark the candidate as `partial` or `gap` unless the claim is intentionally narrow.
- Substantive multi-day city guides need enough candidate breadth for traveler-native prose: attractions, restaurants or food areas, shops or souvenirs, hotels or lodging areas, rest nodes, transport nodes, and fallbacks.
- Food, shopping, hotel, rest, and fallback candidates should carry concrete names or areas when source evidence allows. Generic category placeholders must become search actions, downgrades, or gaps.
