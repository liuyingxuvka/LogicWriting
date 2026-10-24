# Investigation route

The investigation route turns a difficult question into a source-grounded
report or a bounded return to the parent’s content boundaries.

## Reader composition v2

For a final report, choose an investigation profile and author the report's
whole CompositionPlan. Place the bounded answer, evidence strength, live
alternatives, unresolved discriminators, limitations, and fallback or recheck
conditions into reader-facing units. Evidence-discovery order is never the
report outline, and one finding is never automatically one paragraph.

After drafting, review actual report spans for the recoverable question,
bounded answer, evidence strength, negative evidence, alternatives, conditions,
limitations, fallback/recheck instruction, and conclusion scope. A research
result or argument model cannot pass this postwrite gate for the report.

## 1. Contract

State the reader's decision or question, critical claims, geographic and time
scope, required source roles, important numbers, confidence language, and a
stopping rule. Separate factual, interpretive, causal, execution, and forecast
obligations.

Create a compact claim-and-evidence contract before broad search. For every
critical claim or number, record why it matters, its required evidence roles,
time and geographic boundary, acceptable strength, unsafe overclaim, and what
would change the conclusion. The stopping rule is evidence-based: a fixed
number of searches or sources is not depth.

Lay out the reasoning space before committing to one storyline. Depending on
the question, include competing branches, expert stances, alternative models,
counterarguments, and the observations that distinguish them. This is a map of
what must be investigated, not a license to manufacture balance where evidence
is one-sided.

## 2. Discover and preserve evidence

Use SourceGuard for discovery planning, source-depth decisions, and ownership
of sources and anchors. Use LogicGuard when live competing conclusions remain,
many critical assertions need modeling, or the user requests an argument graph.
Otherwise SourceGuard observations and brief content boundaries suffice. Use
LogicGuard's source library only when building those deeper models.
Every source record keeps locator, source date, coverage period, access state,
lineage, independence, role, and what it can and cannot support.

Candidates and snippets are leads, not factual evidence. Several pages that
repeat one origin count as one lineage. Announcements support announced intent;
they do not by themselves prove execution or effect.

Use SourceGuard to build a source portfolio by evidence role rather than accumulating links. A
material conclusion may need, for example, an official or primary record for
the act, implementation evidence for what happened, outcome data for effects,
a method source for measurement, and critique or counterevidence for the main
alternative. Record access failures and permission gates instead of treating a
search-result description as observed content.

After each meaningful round, update the belief state: what became observed,
which claim changed, which branch weakened or strengthened, which important
gap remains, and which next action has the highest expected value. Stop, narrow,
or redirect when the remaining gap cannot justify another broad round.

## 3. Deepen only where the claim demands it

Use LogicGuard to compare conclusions, warrants, assumptions, rebuttals, and
scope. Use TraceGuard when chronology, implementation, causality,
counterfactuals, competing stories, or forecasts are material. Chronology alone
does not establish mechanism or cause.

Continue until every critical claim has usable support, material counter- or
limiting evidence, provenance, and a scope boundary—or until a typed terminal
gap shows why it cannot.

Keep a key-claim and key-number ledger. Each important number includes the
measure, unit, population, period, geography, denominator or baseline,
calculation or rounding rule, source anchor, and allowed wording. Numbers from
different definitions or periods do not become comparable merely because they
share a label.

For causal, execution, or outcome claims, distinguish at least:

- chronology: what happened and in what order;
- mechanism: how one event could influence another;
- implementation: whether the stated action was actually carried out;
- exposure or reach: who or what was affected;
- observed outcome: what changed, relative to which baseline;
- competing explanation and boundary conditions;
- forecast validation or holdout evidence when making predictions.

Use native LogicGuard conclusion competition before strong synthesis. Compare
the leading conclusion with live alternatives under the same evidence and scope;
preserve the returned wording license. Retain a rival when the available
evidence cannot discriminate, rather than choosing the smoother story.

## 4. Return a bounded investigation

The piece has one evidence model: its ReaderBrief `content_boundaries`. Return
content units, evidence anchors, alternatives and limitations with their stable
ids, plus the ResearchGuard research folder for native sources and conclusions.
A parent route incorporates these rows unchanged and retains final ownership.
Name the requested gap and the remaining uncertainty; do not create a second
registry or a separate writing plan.

Set `research_folder` in the brief request. The source model owns anchor ids,
source ids and locators; matching handwritten relation, summary and boundary
remain author-owned. Conflicting ownership fails `anchor_conflict:<id>` instead
of silently replacing the native source. Candidates, access gaps and bounded
results stay visible and cannot become factual support through smooth prose.

Save `researchguard status <folder> --json --output research-status.json` and list
that one `researchguard` provider report for closure. Its `verdict` must preserve
errors, the search stop decision, root wording license and live hypotheses.
Opposite native/brief alternative dispositions fail
`alternative_status_conflict:<id>`. `contested` remains `research:contested` risk;
it is not a new blocking rule. A sufficient search decision alone does not
license assert wording, including a source-only result with no root license.

## 5. Write for the reader

Build a ReaderBrief, then produce the requested genre. A narrative report should
read as a coherent explanation, not as an 18-stage workflow dump. Use tables
only when comparison is genuinely clearer. Keep citations and material limits
near the claims they bound.

Audit the actual final artifact and derive closure. If evidence remains bounded,
the wording and completion claim must be equally bounded.

Choose the delivery shape for the reader's decision: narrative explanation for
a causal or historical account, a comparison table for repeated exact fields,
a timeline for material sequence, or a decision note for alternatives and
trade-offs. Do not expose the research-stage numbering as the report's
storyline. Put necessary limitations near the claims they change and reserve a
technical appendix for provenance detail that would otherwise interrupt the
main argument.

Use the shared writing contract for every important finding and section. Name
the reader's incoming state, the concrete contribution, the changed state, the
remaining question, and the exact later consumer. Recover the original reader
question at major turns and in the conclusion; do not let an interesting source
silently replace the question being answered.

Negative evidence is a result, not an empty box. Say what was checked, what was
not found, how much the absence changes the conclusion, and when or by whom it
should be rechecked. When a recommendation depends on access, execution, cost,
timing, or another practical constraint, preserve the friction and provide the
nearest evidence-licensed fallback instead of polishing the obstacle away.

Bind the important rows in the claim/argument model to exact spans in the
current delivered artifact. Important prose without a model row, or important
model rows that never appear in the artifact, block closure until repaired or
explicitly dispositioned.

## Independent actual-text review

One context independent of the writer may assess this route's semantic
obligations and the eight reader dimensions together. Preserve both existing
`route_review` and `ReaderJudgment`, including actual spans, reverse outline,
required dimensions, scores and their current fingerprint bindings. If a
revision round fixes none of the reported defects, stop and return the artifact
with the audit note.
