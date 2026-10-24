# Travel domain owners

| Work | Owner | Boundary |
|---|---|---|
| Source discovery and source-role coverage | SourceGuard | Keep source dates, inspected content and support boundaries visible. |
| Route options, stops, movement edges, lodging and fallback links | The trip plan | These are itinerary inputs, not a TraceGuard result. |
| Event order, time, access, space, resource and other feasibility | Saved WorldGuard reports | The travel validator reads the saved report; it does not execute WorldGuard. |
| Traveler suitability | Fit dimension rows bound to current profile values | The overall result is derived from those rows. |
| Guide structure and final prose | Travel composition and writer | Keep all body/appendix structure in the composition, with current-artifact review. |

The trip plan references saved reports through `world_feasibility.checks[].worldguard_report`. It cannot supply a passing world status. Source currency comes from `checked_on` against the planning date, never a self-authored freshness label. Textual elegance cannot improve a domain result.
