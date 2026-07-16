# Router

Route by what the user expects to receive at the end.

| Terminal deliverable | Final owner | Permitted child work |
| --- | --- | --- |
| Research report, briefing, evidence package, decision note, investigated answer | `investigation` | Logic/trace/document helpers as bounded adapters |
| Paper, thesis chapter, dissertation section, literature review, proposal, substantive academic revision | `academic-writing` | Bounded `investigation` gap requests plus specialist adapters |
| Short story, fiction chapter, novel, fiction outline, story audit, substantive fiction revision | `fiction-writing` | Bounded investigation and specialist adapters; fiction retains closure |
| Itinerary, destination guide, lodging strategy, route plan, traveler-fit recommendation | `travel-guide` | Bounded investigation and specialist adapters; shared reader projection is not a fiction child |
| Quick fact, grammar-only edit, casual copy | none | Exit with `trivial_or_out_of_scope` |

## Decision record

Record one `route-decision` with the request fingerprint, terminal deliverable,
one final owner, zero or more bounded child routes, material assumptions, and
status. A material request change makes the decision stale.

If the requested genre and final artifact conflict, explain the conflict and
ask one focused question. Do not run both routes in parallel and decide later.

Subject matter and presentation technique do not transfer ownership. A paper
about travel remains academic; a historically researched novel remains
fiction; a story-shaped itinerary remains travel. Shared reader projection is
a kernel with no final-success path, never a fifth route or a sibling caller.

## Bounded academic-to-investigation request

The parent supplies a stable `gap_id`, the exact claim or artifact unit, needed
source roles, required time/scope boundary, and return contract. Investigation
returns only the requested ResearchPacket slice and may report partial,
bounded, access-gap, or provider-unavailable states. It never closes the
academic artifact.

## Failure boundary

Unknown specialist availability, ambiguous ownership, or an unresolvable
terminal genre blocks activation. There is no fallback to either predecessor
skill id.
