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
- One route per function: when a step fails, the error reaches the caller or is reported with its text; never a quiet default or a second path. `tests/contract/error_policy.py` lists every exception handler that can end without raising (also `contextlib.suppress` under any name, and a context manager whose `__exit__` can return true), per function with its count, its reason and the written rule it serves; `tests/contract/default_reads.py` inventories the default reads (`.get(key, default)`, `.get(key) or default`, `getattr(obj, name, default)`; not yet reviewed one by one); new code reads required fields directly. A test or a test module may never end skipped (FlowGuard's `no_skip` policy turns either into a failure, and a test fails when its plugin stops loading).

## Validation

- Run the affected tests while developing. CI (`.github/workflows/ci.yml`) runs the full pytest suite, fiction and travel regressions, `python -m flowguard check --all`, and an installed skill byte check on every push and pull request. Its second job runs tests and the member preflights with ResearchGuard at `RESEARCHGUARD_MIN_VERSION` (`skills/logic-writing/scripts/_common.py`). Publishing waits for successful CI on the same source commit.

Commit code and its tests together; add `Request: <id>` when answering a saved owner request. Report the actual commands, results and remaining work.

A release has exactly one commit titled "Release LogicWriting v<version>", made after the last change of that release; it changes only the version files and CHANGELOG.md.
Version numbers: a release that adds features raises the second number (4.1.0 -> 4.2.0); a release with only small fixes raises the third (4.2.0 -> 4.2.1); never skip a number.

Maintenance needs FlowGuard from the owner's repository at the version written once, in `.github/workflows/ci.yml` (the PyPI package named `flowguard` is a different project).
Raise that version, or `RESEARCHGUARD_MIN_VERSION` in `skills/logic-writing/scripts/_common.py`, only when Logic Writing starts using a newer feature of that tool; a FlowGuard or ResearchGuard release alone is no reason to change them or to release Logic Writing.

<!-- flowguard:start -->
## FlowGuard rules for the project agent

1. At session start, look at `python -m flowguard` when the project has intent rules.
2. Before writing a decision, use `python -m flowguard show "what it decides"` to find its existing owner.
3. Write one rule, bind each real home, and add a literal regression row only when a decision has copies, the owner says everywhere, or a bug was fixed. Otherwise stay quiet.
4. After changing a bound decision run `python -m flowguard check`; CI runs `check --all`. Store actual owner words once with `req add`.
<!-- flowguard:end -->
