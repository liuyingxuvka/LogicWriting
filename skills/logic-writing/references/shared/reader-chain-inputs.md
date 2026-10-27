# Reader Chain Inputs

## Commands

Start from the worked example of your route in assets/examples/<route>/ (see its README).

Run reader-chain request wrappers from the skill root with Python 3.10 or newer.
Each reads a JSON file through `--input <file>`, prints its JSON result (or saves
it with `--output <file>`), and exits 0 when that result passes. Readback and
known-bad commands below default to readable text and offer `--json`; provider
preflight takes the provider name instead of a request.
A top-level field that holds an object may instead name a `.json` file
(relative to the request file), including a file an earlier step wrote with
`--output`. Scalar IDs, artifact paths and opaque native result locators stay
strings even when they end in `.json`. A relative `artifact_path` is read relative
to the file that contains it. Leave every script-derived `*_fingerprint` field out of the records you write:
the scripts compute each record's own fingerprint and copy the ones it must
share with other records in the same request; a value you do give is still
checked. Keep real source-byte identities such as revision
`source_artifact_fingerprint` where the entrypoint schema requires them;
these identify actual source bytes. Field shapes are in `assets/schemas/`.
A failed result file without the requested record reports its first error; fix
that step before continuing. A vanished artifact unit is named before any
fingerprints are filled. Correct the binding or evidence against the current
ArtifactMap; the scripts never guess a replacement unit.

1. `python scripts/select_route.py --input route-request.json` with
   `writing_request`, `decision_id`, `decided_at`; returns the RouteDecision.
2. `python scripts/build_reader_brief.py --input brief-request.json` with
   `route_decision`, `content_boundaries`, `composition_plan`,
   `route_composition`, `brief_id`. Later steps can name this result file for `reader_brief` and
   `route_composition`. Optionally set `research_folder` to the ResearchGuard folder or `research.yaml`; missing anchors are imported from its `models.source`. Matching handwritten dispositions stay unchanged; a different source id or locator fails `anchor_conflict:<id>`. With `research_status` (the saved `researchguard status --json` report of that folder), imported anchors take their relation from the research direction; a contradicting handwritten relation fails `anchor_relation_conflict:<id>`.
3. Write the artifact as UTF-8 text or Markdown from `ReaderBrief.writer_input`. For travel, attach one `trip_plan`; for long-form fiction, name its `longform_project`. Supply `world_contract` and `world_refs` when the route requires a WorldGuard check.
4. `python scripts/build_artifact_map.py --input map-request.json` with
   `artifact_path`, `map_id`, `language`, `artifact_format`.
5. `python scripts/validate_shared_writing.py --input shared-writing.json`
   with `contract`, `artifact_map`, `reader_brief`. Prefer `anchor_excerpts`
   (exact unique quotes, each at least 12 characters) over hand-written unit IDs.
6. `python scripts/audit_reader_output.py --input audit-request.json` with
   `audit_id`, `artifact_map`, `reader_brief`, `shared_writing`, `audited_at`.
7. `python routes/<route>/scripts/validate_<route>_artifact.py --input review.json`
   with `review`, `route_composition`, `artifact_map`, `reader_brief`,
   `shared_writing`; `<route>` is
   `investigation`, `academic`, `fiction`, or `travel`.
8. `python scripts/derive_closure.py --input closure-input.json` with
   `closure_id`, `route_decision`, `reader_brief`, `route_composition`,
   `artifact_map`, `shared_writing`, `deterministic_audit`, `route_review`,
   `judgment`, and `revision_provenance` for `revise_existing` with real source
   and treatments; `create_new` may omit provenance and use the default not-applicable record.

For a readback, `python scripts/show_plan.py --input reader-brief.json [--json]`
shows the plan tree even before drafting, with `UNBOUND` units. It also reads
the later chain JSON files beside `reader-brief.json`; available text bindings
must still resolve against the current artifact. For known-bad checks,
`python scripts/known_bad.py --input closure-input.json [--json] [--write-catalog <directory>]`
checks deterministic edits of a copy of the current text. It reports the first
check that catches each applicable defect without changing the original text.

Before a specialist
handoff, `python scripts/provider_preflight.py <provider>` checks that the
provider is installed; for ResearchGuard status and its three semantic members it uses the
ResearchGuard installed in the running Python, or else the `researchguard`
command on PATH. Specialists run through
their own commands, not through these scripts.
