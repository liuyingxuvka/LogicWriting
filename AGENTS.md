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

- Run the affected tests while developing. Before a product release freeze the source and run the complete native suite once through `python -m flowguard check --all` from an environment outside the project; it includes pytest. CI (`.github/workflows/ci.yml`) runs the full pytest suite, fiction and travel regressions, `python -m flowguard check --all`, and a scratch skill byte check on every push and pull request. Its second job runs tests and the member preflights with ResearchGuard at `RESEARCHGUARD_MIN_VERSION` (`skills/logic-writing/scripts/_common.py`). Publishing waits for successful CI on the same source commit.

Commit code and its tests together; add `Request: <id>` when answering a saved owner request. Report the actual commands, results and remaining work.

A release has exactly one commit titled "Release LogicWriting v<version>", made after the last change of that release; it changes only the version files and CHANGELOG.md.

Version numbers are independent for each project; use the same MAJOR.MINOR.PATCH rules:

- At 1.0 and later, incompatible changes to a supported public CLI, skill id, SDK or saved input format raise MAJOR; backward-compatible features raise MINOR; corrections within the existing contract raise PATCH. Internal code volume or a dependency's version is not a version criterion. Never skip a number.
- Before 1.0, keep the unstable status explicit: incompatible public changes raise MINOR and describe migration. Publish 1.0 when declaring a stable contract, not merely because the implementation changed.
- A format consumed by a documented command remains a contract even when generated. Distinguish it from disposable caches. A new required field or changed supported meaning needs a compatibility decision; do not silently reinterpret old material.
- For a changed public surface, retain a small existing valid example and a real counterexample. Explain a corrected old bug separately from a new requirement. Give rejected old material a rebuild path from original inputs; never invent verified results, source digests or evidence fields to make it load.
- Record the release classification and migration in the existing CHANGELOG. Preserve historical commits, tags and releases; append corrections instead of renumbering them. Changes limited to repository policy or maintenance tooling do not by themselves require a product release. Raise a maintenance dependency only for a capability actually used or an evidenced correctness fix required by that workflow, not merely because a new tag exists.

Public saved inputs include documented writing requests, CompositionPlans, source references and artifact bytes. Briefs, specialist reports, audits and closures accepted by a documented command are also format contracts; their conclusions remain tied to their actual inputs and scope. See MIGRATION.md for the current saved-material boundary.

Maintenance needs FlowGuard from the owner's repository at the version written once, in `.github/workflows/ci.yml` (the PyPI package named `flowguard` is a different project).
Raise that version, or `RESEARCHGUARD_MIN_VERSION` in `skills/logic-writing/scripts/_common.py`, only for a capability Logic Writing actually uses or a demonstrated correctness fix required by its workflow; a FlowGuard or ResearchGuard release alone is no reason to change them or to release Logic Writing.

<!-- flowguard:start -->
## FlowGuard rules for the project agent

1. At session start, look at `python -m flowguard` when the project has intent rules.
2. Before writing a decision, use `python -m flowguard show "what it decides"` to find its existing owner.
3. Write one rule, bind each real home, and add a literal regression row only when a decision has copies, the owner says everywhere, or a bug was fixed. Otherwise stay quiet.
4. After changing a bound decision run `python -m flowguard check`; CI runs `check --all`. Store actual owner words once with `req add`.
<!-- flowguard:end -->
