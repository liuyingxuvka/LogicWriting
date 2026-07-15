# Responsibility Map

Logic Writing coordinates specialists; it does not absorb their authority. The
tables below define who may make which kind of claim and where that claim stops.

## Component ownership

| Component | Owns | Returns to Logic Writing | Does not own or prove |
| --- | --- | --- | --- |
| Logic Writing | Public activation, terminal-deliverable routing, one-final-owner invariant, bounded handoffs, ReaderBrief construction, reader-facing integration, and final evidence aggregation | Route decision, assembled handoffs, delivered artifact, and closure constrained by current evidence | Search policy, factual truth, native argument checks, trace validity, document rendering, or PDF inspection |
| SourceGuard | Next search action, discovery policy, and evidence-depth status | Candidate and observed-source state, access limits, stopping or next-action result, and native receipt | That a candidate or snippet is factual evidence; argument licensing; final prose |
| LogicGuard | Source-library preservation, argument support, structure, citation semantics, model depth, and synthesis planning | Source/model identities, diagnostics, support and wording boundaries, plans, and native receipts | Factual truth; execution or outcome evidence; quality of the actual final prose |
| TraceGuard | Material temporal, implementation, causal, competing-story, counterfactual, perturbation, and prediction-boundary analysis | Trace identities, alternative stories, unresolved links, allowed claims, and native receipts | That chronology proves causality; general argument or document closure |
| FlowGuard | Process order, behavior/state model, freshness propagation, no-progress behavior, and closure constraints | Current process state, dependency and staleness results, counterexamples, and native receipts | Source quality, argument truth, reader clarity, or visual correctness |
| Documents | DOCX, Word, and Google Docs reading and mutation, tracked changes, comments, styles, rendering, and page inspection | File fingerprint, mutation evidence, requested markup evidence, render and page-level result | Source fit, argument support, or PDF-specific visual evidence |
| PDF | PDF text extraction, structural parsing, creation, page rendering, and visual inspection | Exact PDF fingerprint and separate extraction, render, and inspection results | Source fit, argument truth, or the correctness of an editable source document |

## Route ownership

| Situation | Parent final owner | Permitted child | What the child may close |
| --- | --- | --- | --- |
| Research report, briefing, evidence package, decision note, investigated answer | `investigation` | Specialist adapters | Only the adapter's bounded request |
| Paper, thesis/dissertation unit, literature review, proposal, substantive academic revision | `academic-writing` | Bounded `investigation` request plus specialist adapters | The exact evidence gap or adapter request, never the academic artifact |
| Quick lookup, grammar-only edit, casual copy | None | None required by Logic Writing | Nothing; use a simpler route |
| Materially ambiguous terminal deliverable | None until clarified | None | Nothing; ask one focused question |

Exactly one route owns final closure. Running two final routes in parallel and
choosing later is outside the contract.

## Evidence-domain boundaries

| Evidence domain | Typical evidence | Licensed claim | Common overclaim to reject |
| --- | --- | --- | --- |
| Source observation | Retrieved content with locator, lineage, date, coverage, and access state | The source contains the observed statement within its scope | “The search result proves the fact” |
| Claim support | Claim-to-source fit, warrant, counterevidence, scope, and alternatives | This wording is supported within the declared boundary | “The argument model proves factual truth” |
| Trace | Events, actors, order, implementation, mechanism, alternatives, and holdout limits | This temporal, implementation, causal, or forecast wording is licensed | “A came before B, so A caused B” |
| Process | State, order, dependency, freshness, and no-progress evidence | The governed workflow reached this current state | “The process passed, so every source and sentence is correct” |
| Text/content | Exact artifact text and structural parsing | The current artifact contains this content and structure | “Extracted text proves the page looks right” |
| Visual/layout | Render and page-level inspection tied to exact file identity | The inspected pages satisfy the observed visual checks | “A rendered page proves the claims are well supported” |
| Reader quality | Actual-artifact diagnostics plus separate reader judgment | The current artifact meets the stated clarity, coherence, genre, and audience boundary | “A metadata flag proves the prose is reader-native” |
| Development/release | Frozen source/tool identity and current validation receipts | This exact repository snapshot satisfied the named checks | “A release check validates a user's later-edited document” |

## Cross-route handoff

`ResearchPacket` is the default evidence handoff between routes. It must bind
the exact current sources, claim support, numbers, alternatives, gaps, allowed
wording, prohibited overclaims, and native evidence. A receiver verifies the
packet fingerprint and, for child work, the requested gap identity.

Plans, search candidates, progress logs, and caller-authored status fields do
not satisfy the handoff.

## Reader-facing handoff

`ReaderBrief` is not a research receipt. It is a sanitized writing contract
that transfers only what the writer needs to explain the subject accurately:
reader, genre, concepts, findings, evidence anchors, alternatives, limitations,
sequence, citations, and safe wording.

The final artifact must be audited separately. If it changes materially, its
dependent diagnostics and reader judgment are stale even when the underlying
ResearchPacket remains current.

## Failure ownership

| Failure | Responsible next owner | Required response |
| --- | --- | --- |
| Required source role is missing or inaccessible | Investigation with SourceGuard/LogicGuard support | Search, narrow, downgrade, omit, or expose the access gap |
| Argument, citation, or structure is unsupported | Route owner with LogicGuard | Deepen, repair, qualify, or keep the claim out |
| Causal, implementation, or forecast chain is unresolved | Route owner with TraceGuard | Preserve alternatives and narrow the wording |
| Receipt or artifact is stale | Route owner with FlowGuard state evidence | Re-run only affected owners against current inputs |
| Editable document mutation or render is unavailable | Academic route with Documents | Deliver only the bounded textual result and prohibit visual claims |
| PDF extraction/render/inspection is unavailable | Route owner with PDF | Preserve the missing evidence class; do not substitute another class |
| Final prose is unclear or exposes internal workflow language | Final route owner | Rebuild the ReaderBrief or prose, then audit the actual artifact again |

No component may convert another owner's missing, bounded, partial, stale, or
failed evidence into success.
