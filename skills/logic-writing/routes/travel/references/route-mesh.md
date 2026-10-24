# Route options in the trip plan

`route_mesh.routes` owns the itinerary alternatives. Each route declares `trace_id`, route type, day ids, nodes, movement edges, operational steps, walking load, world-check ids, weakest links, fallback ids and an evidence boundary. The historical `trace_id` field is a route identifier; it does not imply a TraceGuard execution.

A primary route is required. Booking/day-of requests also need a comfort route. The declared movement edges must form the exact adjacent node chain, every node must bind its actual candidate/day/world check, and walking load must respect the profile. A fallback must name its replacement node and a reachable predecessor in the same route.

World checks may address a specific candidate or route, or explicitly the complete trip by its current `trip_id`. The saved report must cover the declared claim and its boundary. Temporal feasibility comes from that WorldGuard report. The validator derives overall feasibility from the referenced results; a handwritten route result is retired.

The guide composition references these actual route/node ids. Its body sections, incoming/outgoing traveler states, consumer handoffs and appendix are the sole guide structure.
