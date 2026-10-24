# Travel runtime workflow

1. Record the traveler profile, planning timestamp, dates, requested claim level and source boundaries in one trip plan.
2. Preserve source roles and `checked_on` dates. A check on the planning date can support currency; an earlier check cannot authorize booking/day-of claims, and a future check date is invalid. No automatic expiry window is invented.
3. Build the candidate pool, route nodes, exact movement chain, risks, reachable fallbacks and lodging where needed. Route options belong to this trip model.
4. Reference saved WorldGuard reports with `worldguard_report`. The validator reads their canonical status; it does not call WorldGuard or TraceGuard. A failed, missing or unreadable report limits the derived level to `initial_plan`.
5. Bind fit dimensions to exact current traveler/profile values. Overall route, fit and recommendation results are derived rather than written into the plan.
6. Put `weather_evidence_summary` in `trip_context`, with the chronology-appropriate source mode, hazards, boundaries and recheck action.
7. Create one travel composition with `trip_plan`, relative to the composition file. Its route, fit, texture and fallback references must exist in that plan. The brief validates both the plan and those references.
8. Follow the normal reader/writer/artifact/review chain. Guide structure lives in the composition; evaluate the actual guide against current spans and the route-review dimensions.

`validate_travel_plan.py` reports the derived `allowed_claim_level`. Past, far-future and undated trips remain `initial_plan`; near-future booking and day-of claims also require passing domain checks, same-planning-date source checks and compatible weather evidence. A stronger requested level is an error. Do not supply a manual allowed level, world status, route feasibility result, fit result or recommendation result.
