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
- Preserve four final owners, reader/writer execution isolation, exact artifact bytes, freshness, repair stopping, and native specialist authority.

## Validation

- Run the affected tests while developing. CI (`.github/workflows/ci.yml`) runs the full pytest suite, fiction and travel regressions, `python -m flowguard map check`, `python -m flowguard release`, and an installed skill byte check on every push and pull request. Its second job runs tests and the three member preflights with ResearchGuard at `RESEARCHGUARD_MIN_VERSION` (`skills/logic-writing/scripts/_common.py`). Publishing waits for successful CI on the same source commit.

<!-- BEGIN FLOWGUARD PROJECT RULES -->

## FlowGuard map and model maintenance

1. Start each session with `python -m flowguard read` before opening source.
2. Before adding behavior, use `python -m flowguard read --find WORDS`; extend its existing owner.
3. Open only the affected component's files (`python -m flowguard read --component ID`).
4. After editing, run `python -m flowguard change`, fix errors, and run the affected tests and models it selects.
5. Re-read each REVIEW component, update its description if behavior changed, then `python -m flowguard map confirm ID`.
6. At final release, freeze the source and run the full suite and `python -m flowguard release` once on that revision (same-SHA CI may provide this); report failures and unrun checks honestly.

Maintenance needs FlowGuard from the owner's repository at the version written once, in `.github/workflows/ci.yml`; older versions do not see same-directory script imports and report `dep_unused` errors (the PyPI package named `flowguard` is a different project).
Raise that version, or `RESEARCHGUARD_MIN_VERSION` in `skills/logic-writing/scripts/_common.py`, only when Logic Writing starts using a newer feature of that tool; a FlowGuard or ResearchGuard release alone is no reason to change them or to release Logic Writing.

<!-- END FLOWGUARD PROJECT RULES -->
