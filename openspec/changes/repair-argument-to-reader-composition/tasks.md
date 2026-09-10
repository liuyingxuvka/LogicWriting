## 1. A01 change contract

- [x] 1.1 Create `repair-argument-to-reader-composition` in the isolated candidate and record the A01 scope, ownership, non-goals, and governance boundary.
- [x] 1.2 Add capability specs for consumer closure, writing benchmark, and the affected fiction, travel, and unified-routing requirements.
- [x] 1.3 Freeze the A11–A13 file map and status semantics in this change's design and tasks.

## 2. A11 consumer resource closure

- [x] 2.1 Add the four disjoint `content_role_overrides` entries to the managed source contract.
- [x] 2.2 Add explicit fiction/travel route resource references and a portable required-resource manifest.
- [x] 2.3 Implement recursive Markdown/manifest/JSON正文 closure checking and focused positive/negative tests.
- [x] 2.4 Build and inspect a clean stage; prove missing `prose-native-contract` and missing travel guide正文 fail.

## 3. A12 protocol and real quality benchmark

- [x] 3.1 Rename/annotate reader-v2 tests and fixture as synthetic protocol/fingerprint regression only.
- [x] 3.2 Add twelve case input files derived from the fixed acceptance materials and rubric without copying the example article into source.
- [x] 3.3 Implement a backend-injected runner that records requests, provenance, outputs, fingerprints, timing/token/cost fields, blind order, and unavailable/incomplete states.
- [x] 3.4 Run the runner with no backend and preserve `execution_provider_unavailable`; do not claim quality or preferred scores.

## 4. A13 contract evidence

- [x] 4.1 Add only focused verification-contract declarations for the changed source and tests.
- [x] 4.2 Run resource closure, protocol fixture tests, and benchmark unavailable-path checks in the isolated evidence root.
- [x] 4.3 Record generated-contract/SkillGuard compile status as blocked if governance prevents formal compilation; do not edit generated outputs.
- [x] 4.4 Add and validate the candidate-only ResearchGuard LogicGuard unit handoff bridge; preserve provider and prose-quality boundaries.

## 5. Current recovery implementation ledger (R00–R10)

This appended section is the current integration ledger for the 2026-09-09
recovery round. Sections 1–4 remain the historical A01 candidate checklist;
their checked boxes do not close a current R00–R10 gate. The integration owner
updates the state column only from the named evidence. Each row must retain
these independent claims: `implemented`, `protocol_tested`,
`current_model_closed`, `real_quality_proved`, and `installed_current`.

| Package | Current scope and owner | Required implementation/evidence | Dependencies and stop condition | State at ledger authoring |
|---|---|---|---|---|
| R00 | Baseline, ownership, OpenSpec alignment; integration owner | New run root with source/peer/lock inventory, exact owner map, and this current ledger; no unknown dirty path is discarded | Stop on active writer, ambiguous ownership, or identity drift; re-freeze before any model or release write | `landed for baseline; final model/source freeze still required` |
| R01 | `skills/logic-writing/scripts/local_execution_backend.py`; Worker A | Single stdout/stderr reader, bounded stdin and hard deadline, explicit lifecycle events, owned process-tree cleanup, and external-process lifecycle tests | No slot or next wave is released before reader drain, owned descendants gone, and atomic completion; any missing cleanup is `cleanup_unconfirmed` | `in progress under integration review` |
| R02 | `scripts/run_writing_quality_benchmark.py` and lifecycle tests; Worker A | One final row per planned job, queued→starting→running→terminal transitions, dependency-derived judge rows, bounded concurrency of two, and no late overwrite | A global deadline may stop new work but must give every planned row a terminal reason; a timed-out/unclean job stops the lane | `in progress under integration review` |
| R03 | Quality provenance and sole owner entrypoint; Worker A with integration owner | Separate corpus, implementation, and execution-policy fingerprints; immutable plan/capture/manifest; aggregate-only is read-only; old receipts fail after relevant identity changes | Source, policy, input, capture, pair order, or context mismatch is stale/incomplete; direct low-level runner cannot claim product readiness | `in progress under integration review` |
| R04 | `skills/logic-writing/scripts/production_reader_pipeline.py`; Worker C | Valid WritingRequest→planner→installed ResearchGuard native plan/receipt→CompositionPlan→ReaderBrief→handoff consumption→exact writer input, with no case/rubric/expected leakage | Native provider absence or invalid planner output blocks; synthetic doubles remain `protocol_only` | `partial: implementation and focused protocol tests landed; real integration pending` |
| R05 | ResearchGuard strict self-DNA mapping and native parent/child adapter; Worker B | Coverage mapping stays separate from strict execution; current parent receipt consumes the exact declared child model set; stale/foreign/missing/duplicate receipts fail | Do not treat 63/63 coverage as native proof; a fresh immutable child/parent receipt is required for model closure | `partial: adapter and focused tests landed; fresh native receipt pending` |
| R06 | ResearchGuard suite checker and current FlowGuard owner execution; integration owner with Worker B | Bounded member checker with terminal timeout/cleanup diagnostics; current LW22/RG10 owner receipts and project/model audit | Any stale authority, failed owner, or unexplained timeout blocks the model gate; shared FlowGuard remains read-only | `partial: bounded checker fix tested; native/model rerun pending` |
| R07 | Isolated SkillGuard projections and RG wheel/console; integration owner | Prepare and verify clean LW/RG projections in a new test Codex home; install exact RG wheel in isolated venv; prove no author/private/evidence leakage | Prepare, projection, package, or console identity failure prevents activation; test projection never updates daily home | `open` |
| R08 | Real production smoke, held-out, and 12-case quality; integration owner | `--preflight-case I01`, then four held-out tasks (4 writers + 8 independent judges), then 48 writers + 48 judges; immutable manifests and distinct planner count | Do not launch full run before smoke; incomplete execution has no score; held-out and pair gates are separate | `open` |
| R09 | Final regression, SkillGuard closure, daily installation; integration owner | Current tests/checkers, FlowGuard/model-test alignment, clean projection parity, and native transactional installer receipt | Any source change invalidates affected evidence; activation happens only after quality/model gates and uses native rollback on failure | `open` |
| R10 | Scoped commit, push, and remote readback; integration owner | Public allowlist only, `git diff --cached --check`, commit, push to the actual default branch, and `git ls-remote` readback | Never push private evidence or unverified model/install claims; tag/release remains not-run until its own contract passes | `open` |

### Current closure rules

1. A package state is complete only when its implementation is present and its
   named focused checks pass. A protocol test may verify transport and
   fingerprints, but it cannot prove a real provider or article-quality
   claim.
2. `current_model_closed` requires current native receipts and the affected
   FlowGuard authority pointer after the final source/spec identities are
   frozen. A model denominator, directory count, or old receipt is not a
   substitute.
3. `real_quality_proved` requires `execution_complete` plus the original
   9/12 pair rule and the four held-out double-judge rule. The consumer must
   reject missing judges, same-context judges, wrong hashes, missing text
   locations, or any incomplete row.
4. `installed_current` requires the exact tested projection, package/console
   identity, native installation transaction, and read-only parity. A copied
   skill directory or a matching single-file hash is insufficient.
5. R10 is source publication evidence only. GitHub readback never upgrades a
   pending model, quality, or installation gate. Any failure leaves its exact
   state and receipt visible for the next bounded repair.

## 6. Current reader-spine hardening

- [x] 6.1 Compile a deterministic minimal reader-spine from the current `CompositionPlan` and `ReaderBrief`, including root question/conclusion, ordered major units, predecessor/forward relations, necessary evidence anchors, editorial dispositions, and conclusion-sensitive limitations.
- [x] 6.2 Route production writer execution through the reader-spine projection and keep raw ledgers, model/status fields, complete gaps, private receipts, and duplicate evidence in the internal evidence record; reject a full card-level WriterInput as the writer's parallel structure.
- [x] 6.3 Add focused positive/negative diagnostics and tests for one-finding-one-paragraph expansion, repeated no-new-information disclaimers, list inflation, Guard/process leakage, transition-only coherence, and material-limit retention/consolidation.
- [ ] 6.4 Run the current LogicWriting production-reader, contract, and quality-projection checks under one frozen source identity and record real provider/unavailable outcomes without converting protocol fixtures into quality evidence.
