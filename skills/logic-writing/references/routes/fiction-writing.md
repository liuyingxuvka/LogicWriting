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

## Consumer resource closure

The selected fiction depth loads only its declared route references. Compact and
short-story reader-native work requires the [prose-native contract](../../routes/fiction/references/prose-native-contract.md),
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
- Short stories add a story ledger, turning points, scene contracts, promises,
  and story closure.
- Long form adds `novel_ledger`, chapter interfaces, continuity layers,
  story-contribution rows, voice/style state, semantic review, project mesh,
  and model-prose binding.
- Final manuscripts add source requirements, the real manuscript identity,
  reverse outline, artifact-bound semantic review, and exact binding.

## Preserve specialist authority

Use TraceGuard, WorldGuard, LogicGuard or SourceGuard only when its question is
material, through its own command, and report its own status unchanged; a
skipped or missing Guard is never reported as a pass.
When world consistency matters, run WorldGuard and attach the path of its
`run_worldguard.py check` report and its overall status (`PASS`, `FAIL`,
`GAP` or `BOUNDARY_EXCEEDED`); a non-pass status stays visible.
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

- Short story: `story_ledger_check.py`, `turning_point_check.py`,
  `scene_contract_check.py` and `promise_payoff_check.py` on the story ledger.
- Long form: `novel_ledger_check.py` and `story_contribution_check.py` on the
  novel ledger, `chapter_interface_check.py` on the chapter interfaces,
  `promise_payoff_check.py` on the promise ledger,
  `voice_style_continuity_check.py` on the voice/style report, and
  `storyline_project_mesh_check.py --repo-root <project folder>` on the
  project mesh.
- Final prose: `model_prose_binding_check.py --repo-root <project folder>` on
  the model-prose binding and `semantic_review_check.py --repo-root <project
  folder>` on the review of the actual manuscript, then
  `longform_closure_check.py --repo-root <project folder>` on the closure
  bundle.

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

## Bind and close the actual manuscript

Use one current project model mesh. The
model-prose binding links important model rows to exact manuscript spans and
records the changed effect of any repeated binding. Reject unbound prose,
unrealized rows, unsupported duplicate binding, a stale review, or a manuscript
whose bytes changed after review.

Before claiming final long-form prose closure, open the final artifact,
recompute its identity, reverse-outline observed events and reader-state
changes, check source requirements, and run artifact-bound semantic review.
If closure fails, return to the earliest failed model surface. Human judgment
about beauty or originality remains explicit; deterministic checks cannot
manufacture it.

The internal route pack under `routes/fiction/` preserves the verified compact,
short-story, long-form, mesh, and known-bad regression families.
It is implementation material, not a separately installed skill or final owner.

## Independent actual-text review

One context independent of the writer may assess this route's semantic
obligations and the eight reader dimensions together. Preserve both existing
`route_review` and `ReaderJudgment`, including actual spans, reverse outline,
required dimensions, scores and their current fingerprint bindings. If a
revision round fixes none of the reported defects, stop and return the artifact
with the audit note.
