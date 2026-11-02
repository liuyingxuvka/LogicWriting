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

After completing the review, explicitly bind it with
`python skills/logic-writing/scripts/run_chain.py <folder> --stamp-review`.
It runs the existing reader steps through route review, validates the judgment's
dimensions, evidence and required-unit coverage, then writes only the judgment
in `closure-input.json`. Failed input validation leaves that file unchanged.
A valid completed `repair` judgment may be stamped; its defects remain and normal
closure stays `needs_repair`.

A researched required unit is also compared with what its own anchors say: when
its claim shares no content word with the observed_summary or boundary of any
anchor it cites (counter anchors aside), the brief step prints
`warning: claim_outruns_anchor:<unit>` and closure keeps it as a nonblocking
residual risk. This is a lexical signal, not entailment: one shared word clears
it, and a warned claim may still be right; check that the anchor supports it.

The stamp also saves the exact text it read as `reviewed_text` in
`closure-input.json`, sealed with its own `reviewed_text_fingerprint` and with the
basis of that stamp. A later stamp on changed text compares the two word by word:
every unit whose words changed (paragraphs, lists, tables, quotes, scenes,
headings and the title; a change across two units belongs to both) needs review
evidence for that unit (its reverse_outline row, or a defect or strength; a
heading or the title may get its own row) whose excerpt quotes it at a changed
passage, or spans the place where words were removed. Otherwise the stamp fails
with `review_not_reread:<unit>`, names the changed place and the old wording, and
writes nothing; removing the judgment's fingerprints does not skip this.
Whitespace-only changes need no reread, and a plan or evidence change on
unchanged text needs no new quotes and keeps the saved record.

Without a saved copy nothing can be compared, so a plain `--stamp-review` is
refused: `review_first_undeclared:<id>` for a review never stamped, and
`review_text_unknown:<id>` for one stamped by LogicWriting 4.1 or earlier or whose
copy was deleted. The reviewer then reads the whole piece and stamps with
`--stamp-review --first-review`; `--first-review` is refused while a saved copy
exists (`review_copy_exists`). Closure needs the saved copy of a stamped review
(`reviewed_text_missing`), refuses one that was edited or is not the text the
judgment was stamped on (`reviewed_text_invalid`, `reviewed_text_stale`), and
reports `review_basis`: `first_review`, or `compared` with the units quoted
again; a first review is also named in `safe_claim`.

Limits. The tool checks that changed words are quoted again, not that they were
understood. A first review is the reviewer's declaration, and the tool cannot
tell a real one from a saved copy deleted on purpose; it only makes the
declaration explicit and visible in closure. The seal stops a copy edited by hand,
not one rebuilt by code that recomputes the tool's own fingerprints.

Default runs and closure never fill or refresh a judgment stamp. An unstamped
review fails with `judgment_unstamped:<id>`; changed content, plan or file
references fail with `judgment_stale:<field>`. Both name the explicit command:
reread changed work before stamping again. Fingerprints bind bytes, plan and
evidence, never the folder: a copied or moved folder keeps its stamp, and
`reader-brief.json` names its research and world files relative to its own
folder. A required unit missing from the review is
`judgment_content_unit_unreviewed:<id>`.

The five records keep their own execution timestamps as metadata while excluding
them from their fingerprints: `audited_at`, `judged_at`, `recorded_at`,
`decided_at` and `reviewed_at`. Domain evidence dates/times and raw file digests
still participate in their existing identities. Revision provenance is still
prepared and checked by the ordinary closure path.

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

## Each saved report belongs to the brief

When the saved report withholds or qualifies the root claim, every required unit that cites an anchor supporting it also cites a limit anchor or a limitation.

Closure counts a saved report only while its declared raw input bytes match the current files. It never runs a provider.

- ResearchGuard: `input_digests` must include `research.yaml` and match every
  declared input in `research_folder`. Changed or missing bytes are
  `research_report_stale:<path>`; missing or malformed digests are
  `research_report_stale:input_digests`. No bound folder is
  `research_report_unbound:research_folder`. Closure does not parse the research YAML.
- WorldGuard: the report's `contract_id` (default summary or `--json` report)
  must equal the composition's `world_contract` id: its `contract_id`, else
  `claim.claim_id`, as WorldGuard defines it. A difference is
  `world_report_mismatch:contract_id`; no readable `world_contract` is
  `world_report_unbound:world_contract`. Its raw input digests must also match;
  changed bytes are `world_report_stale:<path>`. A travel trip plan's
  `world_feasibility` reports are checked the same way when the brief is built
  (`travel_composition.world_report.mismatch`).

- A fiction or travel composition can instead name `world_mesh`. Its saved
  `mesh-check` report binds by `mesh_id` and raw `input_digests` for the mesh
  and every file node; embedded contracts are covered by the mesh bytes.
  Missing `mesh_id` is `world_report_unbound:world_mesh`, with the
  `worldguard mesh-check --mesh` command to regenerate the report (WorldGuard
  0.8.0 or newer), or `run_chain.py --refresh-providers`. A different id is
  `world_report_mismatch:mesh_id`; changed or omitted inputs are
  `world_report_stale:<path>`. `world_contract` and `world_mesh` are exclusive.

Such a provider check is `failed`, its reason starts with the codes, the
provider is named in `residual_risk`, and closure is `needs_repair`. The repair is
to save the report again from the right folder or contract. An unreadable report
stays `unreadable`.

Only the report's actual WorldGuard `scope_limits` are retained as nonblocking
residual risks, with the final owner and saved report path. The readback adds a
count; the risk entries carry the details. A PASS with limits remains a PASS.

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

Saved ResearchGuard and WorldGuard reports must contain current `input_digests`. Closure only compares the declared raw files; it never runs a provider. Changed inputs require refreshed reports before a broad claim.
