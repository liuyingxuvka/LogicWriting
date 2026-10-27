# Reader chain details

Start from the worked example for the selected final owner. Write or revise the
text in its existing writer workspace; commands validate existing text only.

## Run an existing example or working folder

`python scripts/run_chain.py <folder>` runs native steps in process on existing text.
It writes the usual JSON results, prints the plan summary and first failure, and
stops there: exit 0 for a passing chain, 1 for a native rejection, 2 for unreadable
inputs or an unavailable refresh provider. `--until` accepts route, brief, map,
binding, audit, review or closure. The single-step commands remain available.
Map and audit request files are optional; the command uses piece.md and current
result files. The seven chain-file fields in closure-input.json may be omitted;
explicit fields retain their meaning and resolve beside that input file.
`--refresh-providers` refreshes researchguard status for research_folder and runs
the same verified portable WorldGuard launcher as provider_preflight for a
world_contract. Install ResearchGuard >= 0.5.16 and WorldGuard >= 0.7.23 beside
this skill before refreshing. Closure itself only reads saved native reports.

## Expert single steps

1. `scripts/select_route.py` selects the final owner.
2. `scripts/build_reader_brief.py` freezes reader intent and the one plan.
3. Write the text from the writer projection.
4. `scripts/build_artifact_map.py` maps current text bytes.
5. `scripts/validate_shared_writing.py` binds exact quotes to planned units.
6. `scripts/audit_reader_output.py` checks the bound current text.
7. `routes/<route>/scripts/validate_<route>_artifact.py` runs the native route review.
8. `scripts/derive_closure.py` derives current closure from saved results.

Read the [request fields and command flags](reader-chain-inputs.md) only when
preparing a request or calling a single step. The [workflow gates](reader-chain-workflow.md)
cover frozen intent, specialist ownership, reader/writer separation, actual-text
review and derived closure. The [entrypoint scope](reader-chain-routing.md) describes
route acceptance and bounded handoffs. These rules remain required for the steps
they govern. `show_plan.py --input <chain file>` reads the plan without writing;
`known_bad.py --input closure-input.json` checks finite edits of a copy.
