# Architecture

Logic Writing is a thin public shell around four route-native owners and a
small neutral writing kernel. “Thin” means routing, handoff, artifact identity,
reader projection, freshness, and closure are shared; domain judgment stays
with the route or specialist that owns it.

## Four final-owner routes

Exactly one route owns every substantive terminal artifact:

| Route | Owns | May request |
| --- | --- | --- |
| `investigation` | Reports, briefings, evidence packages, decision notes, investigated answers | Specialist source, logic, trace, world, document, and PDF work |
| `academic-writing` | Papers, thesis/dissertation units, literature reviews, proposals, substantive revisions | A bounded investigation plus specialist work |
| `fiction-writing` | Story plans, short stories, chapters, novels, series structures, story audits and revisions | Bounded factual/canon research plus specialist work |
| `travel-guide` | Deep itineraries, destination guides, routes, lodging strategies, traveler-fit recommendations | Bounded investigation plus specialist work |

The router uses terminal deliverable, not topic or presentation style. Shared
projection never becomes a fifth owner. A sibling route cannot invoke another
sibling route as its final owner.

```mermaid
flowchart TD
    Q["Request"] --> D{"Terminal deliverable"}
    D --> I["investigation"]
    D --> A["academic-writing"]
    D --> F["fiction-writing"]
    D --> T["travel-guide"]
    A -. "bounded evidence gap" .-> I
    F -. "bounded evidence gap" .-> I
    T -. "bounded evidence gap" .-> I
    I & A & F & T --> S["Shared reader/artifact kernel"]
    S --> X["Current delivered bytes"]
    X --> C["Route-native audit + verifier-derived closure"]
```

## Neutral shared kernel

The shared layer owns only behavior that means the same thing in every genre:

- one route-decision identity;
- audience, purpose, incoming reader state, and artifact form;
- unit contribution and concrete incoming/outgoing reader-state interfaces;
- specific downstream consumer or terminal disposition;
- register ownership and effect-aware variation;
- model-row to exact artifact-span binding;
- internal-language and explanation-pressure review;
- actual-artifact identity, freshness, and closure composition.

One canonical composition plan supplies writing-unit identity, order and reader state.
Native ResearchGuard research folders supply source anchors and verdicts. Fiction
retains domain promises, arcs, continuity and voice. Travel retains its single
trip model, check dates, fit and reachable fallbacks.

## Route-native layers

### Investigation

Investigation moves from question and claim contract to source portfolio,
belief updates, competing conclusions, key-number discipline, native source anchors,
reader prose, actual-artifact audit, and bounded closure. Source candidates and
snippets never become observed evidence by wording alone.

### Academic writing

Academic writing inventories the real source artifact, models chapters,
sections, paragraphs, figures and tables, deepens important shallow units,
requests bounded evidence gaps, integrates citations, preserves revision
provenance, uses Documents/PDF for real files, and audits the final artifact.

### Fiction writing

Fiction selects compact, short-story, long-form, or final-manuscript depth.
It preserves contribution, turning points, scenes, promises, arcs, chapter
interfaces, continuity, voice/style, Guard handoffs, project model mesh,
real-manuscript identity and current quoted route review. Longform closure runs the
actual domain validators in process and names each failed surface.
WorldGuard owns material world consistency even when the setting is fictional.

### Travel guide

Travel starts from the traveler profile and time boundary; builds a role-based
source portfolio; reads saved WorldGuard checks for candidates and routes;
validates transport, access, weather, cost, pace, stamina, companions, lodging,
fit, safety and accessibility; preserves negative evidence and reachable
fallbacks; then projects checked route cards through the shared reader kernel.
It never calls the fiction route.

## Specialist boundary

SourceGuard, LogicGuard and TraceGuard (all through the single `researchguard`
console), WorldGuard, Documents, and PDF remain native owners. Logic Writing
reads their results as they are and never writes a result on their behalf.
Provider absence, access gaps, partial
results, stale identities, failed rendering, or human-review boundaries remain
typed non-pass states.

## FlowGuard models

This repository is maintained with FlowGuard; user writing tasks do not use it.
`.flowguard/models/` holds executable route, current-artifact, closure-provider and
unique-quote binding models. `route_and_guard_model` checks that one
current request gets exactly one final owner, material open choices stop
routing before planning, and ResearchGuard members run only through the
`researchguard` console. `reader_artifact_model` checks, for each of
the four final owners, that closure follows a quality review of the current
bytes and that broad claims require an independent context. A passing self-review
keeps an explicit risk and no broad claim. Each model explores its states, keeps known-bad variants that
must fail, and replays its traces on the real scripts (`select_route`,
`provider_preflight`, the reader chain and `derive_closure`).
`python -m flowguard map models` runs them.

Shared kernel state is limited to route decision, artifact identity, reader
projection identity, and freshness. Fiction and travel own disjoint domain
state and side effects.

## Validation ownership

OpenSpec records product obligations and acceptance checks. The release
workflow (`.github/workflows/publish-release.yml`) runs pytest, the fiction and
travel regressions, the models and the map check on the exact source commit
before it publishes. `python scripts/install_skill.py --target <dir> --check`
compares an installed copy with the source by file set and bytes.

## Reader-chain components

`reader-plan` validates intent and the canonical plan, projects writer inputs and
checks optional revision provenance. `reader-binding` partitions the current
bytes and resolves unique quotations. `reader-checks` computes the deterministic
audit and checks route/reader evidence. `reader-inputs` fills only absent derived
references after membership validation; `reader-closure` combines these results
with saved native verdicts and real domain checks. Command wrappers remain in
`reader-commands`, so pure plan and check owners do not depend on their entrypoints.

Travel's existing extension fingerprint also binds the actual trip-plan and
saved report bytes. Replacing either input stales the chain. Pure domain owners
`fiction-model` and `travel-model` keep in-process domain validation below their
route command wrappers. World reference checks read declared ids and quotations;
they never invoke WorldGuard. Known-bad checks mutate text in memory and retain
the author's real quotations, so a stale locator alone cannot manufacture success.
