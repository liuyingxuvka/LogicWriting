# Frozen v2.1.3 Baseline

## Identities

- repository: authoritative local LogicWriting checkout
- branch: `main`
- source commit: `09ecf118cd9d9861ed5f9aed184b57ff2ae72ed7`
- source tag and product version: `v2.1.3` / `2.1.3`
- remote: `https://github.com/liuyingxuvka/LogicWriting.git`
- active consumer: current local Codex `logic-writing` skill installation
- source and installed `SKILL.md` SHA-256: `8A274974FD095E2539FFCECF39C344EF25120211F6D48BA257FF6E604E3EA9E9`
- FlowGuard engine: `0.65.1`
- FlowGuard observed snapshot: `logic-writing-observed-v2.1.3-pre-upgrade`
- pre-change model regression report: `.flowguard/evidence/simulator/reader-composition-preflight/report.json`
- pre-change report SHA-256: `380e3df3109a866a90e84c5513cb3ca499fa60a076a57dca499b8c274e1c0163`
- OpenSpec change: `repair-reader-composition-pipeline`
- SkillGuard maintained member: `skills/logic-writing`

The active consumer remains unchanged during implementation.

## Current Reader Contract Authority

The reader-contract schemas are:

- `route-decision.schema.json`
- `reader-brief.schema.json`
- `shared-writing-contract.schema.json`
- `reader-audit.schema.json`
- `reader-judgment.schema.json`
- `revision-provenance.schema.json`
- `evidence-receipt.schema.json`
- `closure.schema.json`

Primary producers and validators are:

- `select_route.py`
- `build_reader_brief.py`
- `build_reader_brief_receipt.py`
- `validate_shared_writing.py`
- `audit_reader_output.py`
- `validate_judgment_receipt.py`
- `validate_revision_provenance.py`
- `derive_closure.py`
- `propagate_staleness.py`
- `schema_validation.py`
- `receipt_authority.py`

Release helpers that consume reader quality evidence are:

- `scripts/check_reader_judgment.py`
- `scripts/check_source_reconciliation.py`
- `scripts/prepare_reader_quality_receipt.py`

Tests currently exercising these contracts are:

- `tests/contract/test_schema_runtime_gate.py`
- `tests/contract/test_schemas.py`
- `tests/e2e/test_routes.py`
- `tests/unit/test_academic.py`
- `tests/unit/test_freshness_closure.py`
- `tests/unit/test_reader.py`
- `tests/unit/test_shared_writing.py`
- `tests/adversarial/test_boundaries.py`

Public instructions are owned by `SKILL.md`, `references/router.md`, the four route references, and the shared reader, human-writing, writing-contract, and closure references.

## Persisted-Package Disposition

Repository search found no current fixture or work package that persists the legacy ReaderBrief, SharedWriting, ReaderAudit, or ReaderJudgment instance shapes. The only historical matches are archived OpenSpec verification records and the source schemas themselves. No external persisted v1 package is declared or promised by repository authority. Therefore this change may use direct current replacement and must not add a runtime converter, fallback, alias, or dual reader.

## Frozen Failure Evidence

The pre-change FlowGuard simulator discovered and ran all seven registered owners. Five passed. `plan_detailing` and `test_mesh` failed under FlowGuard 0.65.1 because the former lacked current proof identity fields and the latter lacked current coverage-inventory ownership. These failures are retained as baseline gaps and are upgrade tasks, not passing evidence.

## Coordination Boundary

`docs/coordination.md` assigns the primary orchestrator as the sole writer and records all prior parallel AI paths as integrated. The upgrade will re-read coordination and Git status at every source-freeze, validation, installation, and release boundary. No peer change may be reverted to manufacture a clean tree.
