# LogicWriting repository instructions

## Coordination

- Read `docs/coordination.md` before editing when that optional coordination file exists.
- Treat `skills/logic-writing` as the single canonical installable skill source.
- Do not edit files currently claimed by another active writer.
- Keep generated receipts, model evidence, caches, and release scratch data outside source authority.
- Do not run repository-wide formatters, dependency installs, or broad generators unless the task requires them.

## Product boundaries

- `logic-writing` is the only supported entrypoint. Do not add aliases or fallback routes for predecessor skill ids.
- Preserve SourceGuard, LogicGuard, TraceGuard, WorldGuard, Documents, and PDF as native domain owners.
- Never put private investigations, machine-specific paths, credentials, or internal coordination records in public release files.
- A task or release status is derived from current evidence; caller-authored `pass` or `complete` values are not proof.
- Preserve four final owners, reader/writer execution isolation, exact artifact bytes, freshness, repair stopping, and native specialist authority.
- One route per function: when a step fails, the error reaches the caller or is reported with its text; never a quiet default or a second path. An exception handler that does not re-raise is listed with its reason in `tests/contract/test_error_handlers.py`, and a test may never end skipped (`tests/no_skips.py` turns a skip into a failure).

## Validation

- Run the affected tests while developing. CI (`.github/workflows/ci.yml`) runs the full pytest suite, fiction and travel regressions, `python -m flowguard map check`, `python -m flowguard release`, and an installed skill byte check on every push and pull request. Its second job runs tests and the three member preflights with ResearchGuard at `RESEARCHGUARD_MIN_VERSION` (`skills/logic-writing/scripts/_common.py`). Publishing waits for successful CI on the same source commit.

A release has exactly one commit titled "Release LogicWriting v<version>", made after the last change of that release; it changes only the version files and CHANGELOG.md.
Version numbers: a release that adds features raises the second number (4.1.0 -> 4.2.0); a release with only small fixes raises the third (4.2.0 -> 4.2.1); never skip a number.

Maintenance needs FlowGuard from the owner's repository at the version written once, in `.github/workflows/ci.yml` (the PyPI package named `flowguard` is a different project).
Raise that version, or `RESEARCHGUARD_MIN_VERSION` in `skills/logic-writing/scripts/_common.py`, only when Logic Writing starts using a newer feature of that tool; a FlowGuard or ResearchGuard release alone is no reason to change them or to release Logic Writing.

# FlowGuard rules for the project agent

1. At the start of a session and after any loss of context, run `python -m flowguard status` before anything else.
2. When the owner asks for something, store the owner's own words once, as received: `python -m flowguard req add <file|-> --id <id>`. It stores only words the owner wrote, byte for byte: never a plan, a list or text an AI wrote. When a new owner message replaces an earlier one, add `--supersedes <old id>`; never edit `.flowguard/requests/`.
3. Find code with `python -m flowguard where NAME`; change code and its tests together; run the project's own test command (for example `python -m pytest -q`) and report exactly what you ran and the result.
4. Commit code and tests together in one commit with a message in your own words; add a line `Request: R<n>` when the change answers a stored owner request. The legacy map, `.flowguard/models/` and the target commands need no upkeep.
