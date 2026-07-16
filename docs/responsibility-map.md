# Responsibility Map

## Final artifact ownership

| Terminal artifact | Final owner | Bounded children cannot close |
| --- | --- | --- |
| Investigation report, briefing, evidence package, decision note, investigated answer | `investigation` | The final report |
| Paper, thesis/dissertation unit, literature review, proposal, academic revision | `academic-writing` | The academic artifact |
| Story plan, short story, fiction chapter, novel, series bible, fiction audit/revision | `fiction-writing` | The story or manuscript |
| Itinerary, destination guide, route/lodging plan, traveler-fit recommendation | `travel-guide` | The traveler-facing guide |

Quick lookups, grammar-only edits, casual copy, and lightweight attraction
lists do not activate Logic Writing. Material ambiguity blocks routing until one
focused question identifies the terminal deliverable.

## Component ownership

| Component | Owns | Does not prove |
| --- | --- | --- |
| Logic Writing shell | Activation, routing, bounded handoffs, shared writing contract, artifact identity, freshness composition, final-owner closure | Native specialist judgments or factual truth |
| Investigation | Source/claim packet, alternatives, numbers, negative evidence, bounded investigation prose | Academic, fiction, or travel closure |
| Academic writing | Scholarly structure, evidence integration, citations, revision provenance, academic artifact | Native source search or file-provider behavior |
| Fiction writing | Story contribution, promises, continuity, voice, story semantic review, model–manuscript binding | World consistency or factual research owned by specialists |
| Travel guide | Source-time mode, candidates, route feasibility, lodging, fit, negative evidence, reachable fallbacks, reverse guide | World/trace truth or live source freshness by prose alone |
| SourceGuard | Search action and evidence-depth decision | That a candidate/snippet is observed fact |
| LogicGuard | Source preservation, argument/structure/citation/model judgment | Factual truth or quality of final prose |
| TraceGuard | Temporal, causal, implementation, competing-story, counterfactual, prediction traces | General argument or artifact closure |
| WorldGuard | Event, agent, space, resource, capability, conflict, authority, and norm consistency | Story payoff, traveler fit, or factual truth outside its model |
| FlowGuard | Process/state/order/freshness/closure behavior | Source quality, reader clarity, or visual correctness |
| Documents | Editable-document reading, mutation, comments, tracked changes, rendering, page inspection | Argument support or PDF-specific evidence |
| PDF | PDF extraction, creation, rendering, visual inspection | Editable-source correctness or claim support |

## Shared writing boundary

The shared contract transfers only audience, purpose, incoming reader state,
artifact form, unit contribution, reader-state change, specific handoff,
register owner, changed effect, artifact identity, and model-span bindings. Each
route attaches only its own extension.

`ResearchPacket` remains an investigation/academic evidence handoff. Fiction
and travel do not have to pretend their story or trip models are research
packets. Travel uses shared reader projection directly and never invokes
fiction as a child route.

## Failure ownership

| Failure | Next owner | Required response |
| --- | --- | --- |
| Missing/inaccessible source role | Route owner with SourceGuard/LogicGuard | Search, narrow, downgrade, omit, or expose the gap |
| Unsupported argument, citation, or structure | Route owner with LogicGuard | Deepen, repair, qualify, or remove |
| Unresolved chronology, causality, implementation, or prediction | Route owner with TraceGuard | Preserve alternatives and narrow wording |
| Inconsistent world event/resource/access/norm | Route owner with WorldGuard | Repair model or preserve non-pass boundary |
| Story promise, continuity, voice, or binding failure | `fiction-writing` | Return to the earliest failed story surface |
| Travel feasibility, fit, time mode, or fallback failure | `travel-guide` | Repair the owning trip surface; prose cannot override it |
| Generic handoff, explanation pressure, register drift, or unbound prose | Final route with shared kernel | Repair structure/projection and audit current bytes again |
| Stale receipt or artifact hash | Owning route with FlowGuard freshness | Rerun only affected current owners |
| Missing document/PDF provider evidence | Owning route with Documents/PDF | Preserve not-run boundary; do not substitute evidence class |

No owner may convert another owner's missing, bounded, partial, stale, blocked,
or failed evidence into success.
