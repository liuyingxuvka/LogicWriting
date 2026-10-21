# LogicWriting repository instructions

## Coordination

- Read `docs/coordination.md` before editing when that optional coordination file exists.
- Treat `skills/logic-writing` as the single canonical installable skill source.
- Do not edit files currently claimed by another active writer.
- Keep generated receipts, model evidence, caches, and release scratch data outside source authority.
- Do not run repository-wide formatters, dependency installs, or broad generators unless the active OpenSpec task requires them.

## Product boundaries

- `logic-writing` is the only supported entrypoint. Do not add aliases or fallback routes for predecessor skill ids.
- Preserve SourceGuard, LogicGuard, TraceGuard, WorldGuard, Documents, and PDF as native domain owners.
- Never put private investigations, machine-specific paths, credentials, or internal coordination records in public release files.
- A task or release status is derived from current evidence; caller-authored `pass` or `complete` values are not proof.

## Validation

- Run the affected tests while developing. CI (`.github/workflows/publish-release.yml`) runs `python -m pytest -q`, `python scripts/run_fiction_regression.py --repository-root . --json`, `python scripts/run_travel_regression.py --repository-root . --json`, `python -m flowguard map models` and `python -m flowguard map check` on the release commit; a second job installs ResearchGuard at `RESEARCHGUARD_MIN_VERSION` (`skills/logic-writing/scripts/_common.py`) and runs `python -m pytest -q` and the three member preflights.

## Model map

- Use the current FlowGuard `map` surface. `.flowguard/map.json` binds each actual runtime/schema/config owner to native models and ordinary tests.
- Inspect affected components before editing; update their model/anchors when behavior changes, then run affected native checks or pytest nodes.
- Confirm a component pointer only after reviewing its current code and validating its affected behavior. A confirmed description is not cached test PASS.
- Preserve four final owners, reader/writer execution isolation, exact artifact bytes, freshness, repair stopping, and native specialist authority.
