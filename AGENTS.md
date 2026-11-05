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
- One route per function: when a step fails, the error reaches the caller or is reported with its text; never a quiet default or a second path. `tests/contract/test_error_handlers.py` lists every exception handler that can end without raising (also `contextlib.suppress` under any name, and a context manager whose `__exit__` can return true), per function with its count, its reason and the written rule it serves; `tests/contract/default_reads.py` inventories the default reads (`.get(key, default)`, `.get(key) or default`, `getattr(obj, name, default)`; not yet reviewed one by one); new code reads required fields directly. A test or a test module may never end skipped (`tests/no_skips.py` turns either into a failure, and a test fails when `tests/conftest.py` stops loading it).

## Validation

- Run the affected tests while developing. CI (`.github/workflows/ci.yml`) runs the full pytest suite, fiction and travel regressions, `python -m flowguard release`, and an installed skill byte check on every push and pull request. Its second job runs tests and the member preflights with ResearchGuard at `RESEARCHGUARD_MIN_VERSION` (`skills/logic-writing/scripts/_common.py`). Publishing waits for successful CI on the same source commit.

A release has exactly one commit titled "Release LogicWriting v<version>", made after the last change of that release; it changes only the version files and CHANGELOG.md.
Version numbers: a release that adds features raises the second number (4.1.0 -> 4.2.0); a release with only small fixes raises the third (4.2.0 -> 4.2.1); never skip a number.

Maintenance needs FlowGuard from the owner's repository at the version written once, in `.github/workflows/ci.yml` (the PyPI package named `flowguard` is a different project).
Raise that version, or `RESEARCHGUARD_MIN_VERSION` in `skills/logic-writing/scripts/_common.py`, only when Logic Writing starts using a newer feature of that tool; a FlowGuard or ResearchGuard release alone is no reason to change them or to release Logic Writing.

# FlowGuard rules for the project agent

1. At the start of a session and after any loss of context, run `python -m flowguard status` before anything else.
2. When the owner asks for something, store the owner's own words once, as received: `python -m flowguard req add <file|-> --id <id>`. It stores only words the owner wrote, byte for byte: never a plan, a list or text an AI wrote. When a new owner message replaces an earlier one, add `--supersedes <old id>`; never edit `.flowguard/requests/`.
3. Find code with `python -m flowguard where NAME`. Before changing state values, actions, conditions, settings or endings, update the affected `.flowguard/flow/` model first and run `python -m flowguard check`. For code claims, follow the installed `flowguard/flow/HOWTO.md` and bind only the affected actions to real public calls. When explaining a flow, embed the `python -m flowguard show` picture as `![Flow](PATH)` using its returned path. Keep purely functional contracts in direct production tests.
4. Change code and its tests together; run `python -m pytest -q` and `python -m flowguard release` for the final source, and report exactly what ran and its result. Commit them together with a message in your own words; add `Request: R<n>` when answering a stored owner request.

Repair dead ends and unreachable behavior in code; reconcile model/code drift. A provisional decision applies only to eligible contradictory requested obligations. If conflicts remain in a reply, end with “需要你决定” and the relevant question and stored owner words. This migrated workflow needs FlowGuard v1.0.0.
