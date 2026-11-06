# Migration to the current Logic Writing

Keep the `logic-writing` entrypoint, four final owners and existing user material.
ResearchGuard's installed console supplies the research question result and its
three native semantic members. The minimum version has one authority in
`skills/logic-writing/scripts/_common.py`. WorldGuard remains a separate native
owner, found in the skills root or through its explicit `--provider-root`.

SourceRegistry, ClaimSupport and ResearchPacket and their scripts are removed;
a piece's evidence stays in its content boundaries and ResearchGuard research folder.

Brief requests use `research_folder`, relative to their JSON file, for a folder
or `research.yaml`. Source-owned anchor ids, source ids and locators cannot be
silently overridden: conflicting handwritten ownership fails
`anchor_conflict:<id>`, while matching author summaries and dispositions remain.
Save one `researchguard status <folder> --json --output research-status.json` and
name the `researchguard` report in closure. Native errors, stop conditions,
wording limits and live hypotheses remain authoritative; `contested` is a risk,
not a new gate. A source-only stop is not a root-claim assert license.

## Current maintenance

Find the current runtime/schema/test owner in `docs/development/flow-contracts.md` and the current scripts/tests. Reader work
is grouped by planning, binding, checking and closure. Supported reader-chain
request wrappers keep their names and input/output flags. ResearchGuard supplies
fresh saved reports and source anchors; CompositionPlan is the sole writing plan.

The CompositionPlan is the piece's one unit tree. Long-form ledgers use planned
unit ids and point to that same plan; one `longform_project` supplies actual
project files to shared closure. Travel uses one itinerary `trip_plan` and the
guide CompositionPlan. World references bind through `world_contract` and
`world_refs`; missing/unknown objects are errors, not guessed replacements.
Do not supply handwritten long-form or itinerary conclusions.

After any edit, rebuild affected byte references, quoted bindings, audits and
reviews. `create_new` may omit provenance and receive the not-applicable default;
`revise_existing` still needs real source bytes and complete treatments.
Quality `passed` requires the actual audit, route review and judgment. A
self-review remains explicit and never grants a broad claim. Broader claims also
need an independent read, applicable native verdicts and disposition of material
live competition. Plans, labels and caller scores do not verify a read.

Use `scripts/show_plan.py` to inspect current plan/text bindings and
`scripts/known_bad.py` for deterministic defects in a disposable copy of the
current piece. They do not generate new prose. Normal development uses affected
checks; final CI runs the complete suite and native gates on the publication
source. Installation, Git tag and hosted Release identities remain separate.

## Saved material and version history

The public compatibility surface is the documented skill/CLI entrypoints and
input formats, including saved models or reports that a command explicitly
accepts. Original requests, manuscripts, research captures and source references
remain user material. Generated maps, trace caches and installation scratch files
can be rebuilt; they are not evidence that a new read or model execution occurred.
A documented saved input does not become disposable merely because a tool wrote it.

The 4.3.1 and 4.3.2 single-PhysicsGuard-report form and its `pg:<row-id>` bindings
remain accepted. Their scalar values retain their original scope: an old row
without an entity binding does not gain one, and a saved `sourced` or `passed`
flag does not verify a new source, model execution or writing judgment. Original
input digests and request identity must still match. Changed input bytes require
fresh native evidence rather than editing the old report's digests or flags.

Some historical generated formats need rebuilding. A ReaderBrief produced by
3.0.2 lacks `writer_input` and `writer_input_fingerprint`, added in source commit
`53606976d847e46d512cbcbae07fe682a327d909`; later current contracts also require
an actual `request`. Both old and new schemas used the text `schema_version: 2.0`,
so that text alone cannot establish compatibility. The current schema rejects
such an old brief instead of manufacturing these fields or retaining its verdict.
Preserve the old file for reference, recover its real request/plan/source material,
and build a fresh brief with the existing command:

```text
python skills/logic-writing/scripts/build_reader_brief.py --input brief-request.json --output reader-brief.json
```

Use the current request example and normal artifact binding, audit, route review
and judgment steps for the recovered material. Re-read changed sources and use
actual native reports where needed. If the original request or evidence cannot
be recovered, keep the result unverified; do not fill a missing field with an
empty/default value or copy an old `verified`/`passed` conclusion into new output.
No legacy reader or automatic converter is introduced.

Historical numbering stays intact. 2.0 removed the separate predecessor runtime
entrypoints; 3.0 changed the reader/closure contracts. Source 4.0.0 added required
ReaderBrief fields, although its then-current MIGRATION and CHANGELOG incorrectly
called it a patch. At the 2026-11-06 history check, the GitHub tag and Release endpoints for `v4.0.0` were
absent; the source version is not evidence that this version was published.
Published 4.x history includes `v4.0.1`. Later 4.x releases also changed generated
required fields while retaining schema version 2.0. These facts explain why the
current format and a small historical example, rather than the major number or
schema text alone, determine whether saved material can be used. They do not
rename or rewrite any historical commit, tag or Release.

## Installation

Install with `python scripts/install_skill.py --target <skills dir>`; add
`--check` to compare the installed copy with source. This copies the one canonical
skill; project metadata installation does not install it.

The former `storyline-design` and `travel-story-planner` skill ids remain retired
without runtime aliases. Preserve user
manuscripts, libraries and plans when moving old active skill directories out of
the skills root. All supported writing intents enter through `$logic-writing`;
ResearchGuard, WorldGuard, Documents and PDF retain their native responsibilities.

Earlier migration details remain in
[the historical record](docs/history/migration-before-4.0.5.md).
