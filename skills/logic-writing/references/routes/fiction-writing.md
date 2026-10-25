# Fiction-writing route

The fiction route owns story plans, short stories, chapters, novels, series
structures, substantive fiction revisions, and final-manuscript closure. It
may request bounded research, but it never transfers final ownership.

## Reader composition v2

Freeze the output room and artifact kind. For reader-native prose, plan story
movements rather than a sequence of scene cards: entry state, pressure,
resistance or cost, reader-state change, irreversible change, exit state,
downstream effect, and promise/reveal movement. Models are content authority;
the manuscript realizes them through action, perception, objects, dialogue,
rhythm, and consequence rather than model labels.

Build the manuscript ArtifactMap from current bytes. Review actual spans for
output-room compliance, story movement, resistance/cost, promise and reveal
handling, continuity, POV/voice, reader-state change, and real-span binding.
A clean plan is not evidence that the prose works.

Use `voice_contract` for POV and tense, with optional narration distance, register,
and allowed variation. Keep `voice_contract_ref` an identifier; without the
contract payload, the writer input retains a voice gap. Changing the contract
changes the route extension and ReaderBrief fingerprints.

## Consumer resource closure

The selected fiction depth loads only its declared route references. Compact and
short-story reader-native work requires the the SharedWriting contract and the actual-text review below,
[scene contract](../../routes/fiction/references/scene-contract.md), and
[voice/style continuity contract](../../routes/fiction/references/voice-style-continuity.md).
Long-form work additionally requires the [chapter interface blueprint](../../routes/fiction/references/chapter-interface-prose-blueprint.md),
[novel ledger](../../routes/fiction/references/novel-ledger.md), and
[long-form lifecycle](../../routes/fiction/references/longform-lifecycle.md).

## Choose depth from the terminal artifact

Every substantive story run follows the same story lifecycle; artifact size
changes evidence depth.

- Compact work needs a clear story movement, a promise boundary and a re-read
  of the actual text after writing.
- Short stories use the fiction composition (`story_movements`,
  `promise_and_reveal_bindings`, `unit_plans`) and the reader chain; use
  `scripts/show_plan.py` to read back the plan. Attach a native WorldGuard report
  when `world_check_required` calls for one.
- Long form adds `novel_ledger`, chapter interfaces, continuity layers,
  story-contribution rows, voice/style facts, and a project mesh.
- Final manuscripts add source requirements, the real manuscript identity,
  reverse outline and the same eight-step reader chain used by every route.

## Preserve specialist authority

Use TraceGuard, WorldGuard, LogicGuard or SourceGuard only when its question is
material, through its own command, and report its own status unchanged; a
skipped or missing Guard is never reported as a pass.
When world consistency matters, run WorldGuard and attach the path of its
`run_worldguard.py check` report and its overall status (`PASS`, `FAIL`,
`GAP` or `BOUNDARY_EXCEEDED`); a non-pass status stays visible.
Use one time format throughout a world contract: all numbers, all `HH:MM`,
all canonical numeric labels (`t1`, `t2`), or all ISO datetimes. Mixed formats
and labels such as `t4b` are WorldGuard input errors (exit 2).
TraceGuard owns temporal and revelation
traces, WorldGuard owns material world consistency, LogicGuard owns support and
structure, and SourceGuard owns source/canon discovery depth.

## Build the story model

Name the target change in the reader, the protagonist's pressure, the live
opposition, the central promise, and the ending boundary. Then model turning
points, scene contracts, promise movements, arc movements, continuity state,
and chapter interfaces. Every important scene or chapter states its
contribution, incoming state, outgoing reader state, unresolved tension, and
exact downstream consumer.

Keep world consistency separate from story continuity. WorldGuard checks
whether events, spaces, resources, access, capabilities, authority, conflict,
and norms can coexist. Fiction validators check character knowledge, point of
view, tense, narration distance, promise movement, arc movement, dialogue
distinction, exposition pressure, voice, and allowed variation.

## Run the story models

The story model files are checked by scripts under `routes/fiction/scripts/`.
Run them from the skill root with Python 3.10 or newer; each takes one JSON
file, prints its report with `--json`, and exits 0 only when the file passes.
Run the ones that match the chosen depth after every material change to the
model or the prose, and put each failing check with its issue codes in the
audit note.

- Long story planning, or an explicitly requested story ledger:
  `story_ledger_check.py`, `turning_point_check.py`, `scene_contract_check.py`
  and `promise_payoff_check.py` on the story ledger.
- Long form: `novel_ledger_check.py` and `story_contribution_check.py` on the
  novel ledger, `chapter_interface_check.py` on the chapter interfaces,
  `promise_payoff_check.py` on the promise ledger,
  `voice_style_continuity_check.py` on the voice/style report, and
  `storyline_project_mesh_check.py --repo-root <project folder>` on the
  project mesh.
- Final prose uses the standard eight-step chain: select route, build the
  ReaderBrief, write or retain the manuscript, build its ArtifactMap, validate
  SharedWriting, audit current text, review actual spans, and derive closure.
  Long form additionally runs `longform_closure_check.py project-mesh.json --json`
  on the current domain surfaces; there is no second prose-binding or semantic
  review machine.

Example: `python routes/fiction/scripts/story_ledger_check.py story-ledger.json --json`.
`storyline_route_check.py <request.json> --json` shows which surfaces a
request needs. Compact work has no script: re-read the actual text.

## Write in the reader room

Use the shared writing contract and reader-native manuscript review. Keep
planning labels out of prose; any leak is reader-room contamination. Deliver
action, objects, dialogue, sequence, resistance/friction, and consequence
instead of announcing intended emotion or meaning. A story-world chapter ending
must close through events or perception, not an author forecast.

Review explanation pressure, variation pressure, character voice distinction,
register ownership, resistance, payoff, and reader-state simulation. Repetition
is acceptable only when it creates escalation, contrast, inversion, cost,
rhythm, or a changed interpretation. Run post-draft contribution review on the
actual words, not on a plan that says the scene works.

## One unit tree and one manuscript binding

CompositionPlan.planned_units owns identity, parent, order, kind and reader job.
FictionComposition.unit_plans owns story-state entry/exit and fiction-specific
pressure, voice, open questions and reveal boundaries. Domain ledgers use only
`planned_unit_id` plus arcs, threads, promises, continuity, evidence and repairs;
they do not author a second hierarchy, copied contribution or adjacency fields.
A missing plan is `composition_plan_missing`; an unknown domain unit reports
`unit_not_in_plan:<surface>:<id>`. Changing a plan invalidates its consumers.

For long form, `longform_project` names the project mesh relative to the
composition file. Native domain checks read current surfaces and compute their
result. Handwritten validation, pass, model-alignment or closure reports do not
supply evidence. Preserve actual draft progress and domain promise/thread states.

SharedWriting binds required planned units and content to current ArtifactMap
spans. Use unique quotations of at least twelve characters; validate the whole
batch before filling a fingerprint or locator. Keep actual adjacency and the
optional create-new provenance boundary. The unchanged long-form example in
`routes/fiction/examples/longform_novel_project` supplies the same seven CLI
inputs around its existing manuscript; generated outputs stay outside source.

The long-form RouteReview requires the usual eight dimensions plus
`explanation_pressure`, `variation`, and `register_ownership`, each supported by
actual quoted spans. Review reader-room contamination, author-facing chapter
endings, frictionless success, unsupported or premature payoff, repeated
contribution, collapsed reader hypotheses, weak voice distinction and exposition
that replaces action. Repetition needs escalation, contrast, inversion, cost,
deliberate rhythm, changed interpretation or downstream use. Institutional terms
must belong to the narrator, character or document using them. Inspect dialogue,
perception, objects and consequences rather than accepting a plan's self-report.
A current fingerprint proves identity, not literary quality or reader response.

## World references

Optional `world_contract` points to the native world contract relative to the
composition file. Planned units may carry explicit `world_refs`; review records
`world_ref_checks` with actual quotations from the unit's realization. Missing
quoted checks remain visible as closure risk. World claims point through
`source_row_id` to these planned units; a planned/not-run adapter is not a native
WorldGuard pass. Keep the native report status unchanged.

## Independent actual-text review

One context independent of the writer may assess this route's semantic
obligations and the eight reader dimensions together. Preserve both existing
`route_review` and `ReaderJudgment`, including actual spans, reverse outline,
required dimensions, scores and their current fingerprint bindings. If a
revision round fixes none of the reported defects, stop and return the artifact
with the audit note.

For a brief request, each `unit_plans` row may omit `contribution`, incoming/outgoing reader states and downstream units; these come from the same planned unit. Open-question and prohibited-reveal arrays default to empty. Keep the fiction-specific id, kind, entry/exit story states, focal desire, cost, voice owner and rhythm role. Explicit fields are preserved and checked.

## From the entrypoint

Choose compact, short-story, long-form, or final-manuscript depth from the
terminal artifact. Preserve story contribution, turning points, scene/chapter
interfaces, promises, continuity, voice, reader-state movement,
actual-manuscript identity and quoted review of the delivered text. For long-form work, the project points to the same CompositionPlan and its ledger uses planned-unit ids; closure derives remaining work from actual project files, rather than accepting a handwritten conclusion.
Provide POV and tense in the optional `voice_contract`; the writer receives that
object, while an unfilled voice reference remains a gap.
