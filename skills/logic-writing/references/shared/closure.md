# Reader closure v2

The executable reader closure covers UTF-8 text/Markdown. A text projection does
not establish closure of its source DOCX/PDF or rendered pages. Keep Documents/PDF
content evidence and visual evidence separate, including explicit missing binary
or render dependencies.

## One current quality chain

`WritingRequest -> ReaderIntent -> RouteDecision -> CompositionPlan -> selected
route composition -> ReaderBrief -> ArtifactMap -> SharedWriting -> deterministic
audit -> route review -> ReaderJudgment -> conditional revision provenance -> closure`

Every byte-bound record must refer to the same current artifact. Intent and plan
bindings must agree. Only the selected final route closes the artifact; bounded
investigation children return evidence to their parent.

`create_new` may omit revision provenance and receives the explicit
not-applicable default. `revise_existing` must preserve real source bytes,
source-unit treatments and their current bindings. A missing revision record
cannot be turned into a creation default.

The deterministic audit, selected-route review and reader judgment must all pass
for textual `status: passed`; otherwise it is `needs_repair`. A plan, score or
caller-written completion marker cannot replace the actual read. All quotations,
references and evidence must still match current bytes at closure time.

One reader who did not write the text may cover the route obligations and all
eight reader dimensions in one read, preserving both records, actual quotations
and the reverse outline. An independent read uses `judge_kind: independent_context`
and different producer/judge ids. A self-review is allowed but stays explicit:
`SELF`, self-review residual risk, `broad_claim_allowed: false`, even when textual
quality passes. Id labels alone do not authenticate who performed a read.

When a repair round resolves none of the actual defects, stop and return the
artifact with its audit note. After a real edit, rebuild dependent maps, bindings
and checks. Repeated calls on unchanged text do not demonstrate repair.

## One saved research verdict

Save the native question result using
`researchguard status <folder> --json --output research-status.json`, then list
`{"provider":"researchguard","path":"research-status.json"}` in `provider_reports`.
Paths are relative to the closure request. Closure reads the report; it never
runs research or rewrites a member's conclusion.

The saved `verdict` has exactly `search`, `root_claim`, `live_hypotheses`,
`contested`, `errors`. Nonzero errors or `search` other than `stop_sufficient`
fail the provider check. Other live hypotheses require a non-null root claim
with an `assert` wording license. A source-only question's single primary
hypothesis is not an additional competitor; its null root remains an explicit
missing-license risk and does not authorize assert wording. A sole live id that
is a declared alternative cannot use that exception. Matching brief alternative
ids must agree with native live dispositions, or the check reports
`alternative_status_conflict:<id>`.

Investigation always needs this report. Academic work needs it for live
alternatives or an explicit `research_folder`. `contested` adds
`research:contested` risk and is not itself a blocking condition. Native
`qualify`/`withhold` limits remain visible. Missing required reports are `not_run`;
unreadable JSON or an invalid/missing verdict is `unreadable`.

## Other current model boundaries

Travel needs a saved WorldGuard report; fiction needs it when
`world_check_required` is true. Only native `PASS` passes. Preserve `FAIL`, `GAP`,
`BOUNDARY_EXCEEDED` and `unreadable`; one shared report reader supplies this
status. Required `world_contract` and `world_refs` must resolve:
`world_contract_missing` and `unknown_world_ref` are errors; an unquoted reference
stays `world_ref_unquoted:...` risk rather than invented observed evidence.

A `longform_project` must point to the same CompositionPlan; its ledger uses
planned-unit ids. Closure derives long-form findings from the actual project
files and records `longform:...` risks. Travel's `trip_plan` likewise supplies
one itinerary whose feasibility is derived from its files. Neither route may
supply a handwritten final verdict in place of those checks.

Applicable known-bad edits are checked by `scripts/known_bad.py` against the
current piece and plan. An uncaught defect remains `toothless:...` risk. This
checks the existing mapping/audit/review chain; it does not generate new prose
or substitute for an independent reader.

Broad quality claims require the complete current quality chain, an independent
read, every relevant native-provider gate and disposition of material live
competition. Provider failures do not rewrite the textual-quality status;
they remain in `provider_checks`/`residual_risk` and prevent the broader claim.
A passing text-layer check never proves factual truth, a source's freshness,
world-model completeness or the rendering of an uninspected document.
