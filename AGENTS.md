# LogicWriting repository instructions

## Coordination

- Read `docs/coordination.md` before editing.
- Treat `skills/logic-writing` as the single canonical installable skill source.
- Do not edit files currently claimed by another active writer.
- Keep generated receipts, model evidence, caches, and release scratch data outside source authority.
- Do not run repository-wide formatters, dependency installs, or broad generators unless the active OpenSpec task requires them.

## Product boundaries

- `logic-writing` is the only supported entrypoint. Do not add aliases or fallback routes for predecessor skill ids.
- Preserve SourceGuard, LogicGuard, TraceGuard, FlowGuard, Documents, and PDF as native domain owners.
- Never put private investigations, machine-specific paths, credentials, or internal coordination records in public release files.
- A task or release status is derived from current evidence; caller-authored `pass` or `complete` values are not proof.

## Validation

- Follow `openspec/verification-contract.yaml` as the sole current repository release contract. Change-local contracts verify only their own active change and archived contracts are historical evidence, never live fallbacks.
- After archiving any release-affecting OpenSpec change, rerun the complete stable release gate on the changed source snapshot before tagging.
- Reuse only immutable terminal-success receipts whose exact inputs and execution identity remain current.
- Run affected checks during development and one full validation owner after the release snapshot is frozen.
- After any timeout or interruption, confirm the complete descendant process tree is gone before accepting evidence or starting another validation owner.

## Model map

- Use the current FlowGuard `map` surface. `.flowguard/map.json` binds each actual runtime/schema/config owner to native models and ordinary tests.
- Inspect affected components before editing; update their model/anchors when behavior changes, then run affected native checks or pytest nodes.
- Confirm a component pointer only after reviewing its current code and validating its affected behavior. A confirmed description is not cached test PASS.
- Optional BCL, path-authority, alignment, plan-detailing, development-process and TestMesh views are explicit capabilities, not a mandatory release proof chain.
- Preserve four final owners, reader/writer execution isolation, exact artifact bytes, freshness, repair stopping, and native specialist authority.





## Audit handoff 2026-09-21

- Prefer short deterministic and metamorphic checks before any live author,
  planner, writer, judge, or self-review call.
- Live model execution is opt-in and requires an explicit finite call budget;
  this handoff's validation policy sets the live-call allowance to zero.
- Keep implementation evidence, skipped checks, environment blockers, and
  release claims separate. A passing offline fixture is not real writing-quality
  or release evidence.
