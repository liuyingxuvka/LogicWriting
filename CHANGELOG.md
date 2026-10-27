# Changelog

This file records notable source-tree changes. It is not a registry of hosted
releases, tags, package publications, installations, or predecessor deletions.

The format follows the main ideas of Keep a Changelog, and the source version
line follows semantic versioning.

## Unreleased

- Plan readback remains available when required new units are not bound yet; passing checks and missing limitation quotes are labeled explicitly.

- Research anchor imports read the fresh saved report only, including its source-owned locator, summary and boundary.

- Closure checks the saved provider reports against their current raw input files; stale reports require repair.

- Maintenance checks run on FlowGuard 0.70.13; ResearchGuard 0.5.16 is the minimum.

## [4.0.15] - 2026-10-25

### Changed

- Closure checks that each saved provider report belongs to the brief. A ResearchGuard report must match the research folder's question, hypotheses, models and source anchors, and a WorldGuard report must name the world contract's id; a report from another question or world fails with research_report_mismatch or world_report_mismatch and closure needs repair. After a research folder or world contract changes, save its report again. A travel trip plan's world reports are checked the same way when the brief is built.
- A brief request may name research_status, the saved researchguard status report of its research folder. Imported anchors then take their relation from the research model's direction for the root claim (counter, limit, support, else context; without research_status they are context), and a handwritten relation that contradicts it fails anchor_relation_conflict.
- The deterministic audit checks that sibling planned units appear in the text in plan order and reports plan_order_mismatch otherwise.
- show_plan starts with a one-line summary of bindings, audit, review, closure and uncaught known-bad edits, and lists each unit's findings with quoted spans, its evidence anchors and world references; results made from other bytes show as stale.
- Known-bad edits also break the plan's relations: two sibling sections swapped, a sentence holding a world reference removed, and a sentence binding a live alternative removed; each must be caught. The shipped known-bad catalogs include the new edits.
- The skill starts from the model: read an existing plan back with show_plan, or the research and world models it relies on, before choosing a route. SKILL.md is under 200 lines; the reader-chain details live in references/shared/reader-chain.md and the route notes in the route references.
- Long-form ledger arcs and threads no longer require a status field; negative domain states still block.
- ResearchGuard 0.5.15 is the minimum supported release; the shipped research-status.json is regenerated with it.
- Maintenance checks of the skill's own model tree run on FlowGuard 0.70.12.

### Removed

- Removed the unused verification-contract fallback from the privacy and public-docs checks.

## [4.0.14] - 2026-10-24

### Changed

- Use one composition plan for fiction unit identity and state, with native domain models supplying promises, arcs, continuity and voice. Long-form writing follows the same reader chain and computes its surface checks in process.
- Closure reads one saved ResearchGuard verdict. `research_folder` imports native source anchors atomically; conflicting handwritten ownership is rejected. ResearchGuard 0.5.14 is the minimum supported release.
- Travel requires a trip plan that the brief validates. World, route, fit and recommendation results and source currency are derived from WorldGuard reports and check dates; guide structure lives only in the travel composition.
- Optional `world_refs` bind planned units to real world ids and current quotations. Missing quotations remain explicit residual risks.
- `show_plan.py` displays the real unit tree, reader-state handoffs and current text bindings. `known_bad.py` generates deterministic mutations of the user's piece and reports the first actual check that catches each; closure lists uncaught mutations as residual risks.

### Removed

- Retire the second ResearchPacket source/claim system and the separate fiction model-prose and semantic-review machines. The existing native providers, domain checks and current-text review own those responsibilities.

## [4.0.13] - 2026-10-23

### Fixed

- Validate all quote bindings and existing artifact-unit references before filling any request bindings or fingerprints; rejected requests retain their original input.
- Determine limitation adjacency from actual body offsets, preserving the same result when a valid ArtifactMap reorders its rows.
- Clarify that new writing may omit revision provenance while revisions still require real source provenance and treatments.

## [4.0.12] - 2026-10-23

### Changed

- New work can omit revision provenance. Revisions derive source fingerprints and unit identities from the real old file and check treatments against the current target.
- Treat travel texture counts and generic risk keyword hints as warnings. Reuse reader block classification so Chinese prose is recognized without English keywords.
- Import missing evidence anchors directly from a saved SourceGuard model, preserving handwritten relations and boundaries.
- Plan short stories in the fiction composition and reader chain; reserve separate story ledgers for longer planning or explicit requests. Read ledger WorldGuard status from native report files.
- Give closure command output a consistent status, errors and warnings envelope while preserving exit codes.
- Describe the current WorldGuard summary fields and accepted homogeneous time formats.

### Removed

- Leave repository fixture mutation helpers and unused placeholder files out of installed skills.

## [4.0.11] - 2026-10-23

### Changed

- Derive omitted body dispositions and shared fiction unit fields from the composition plan before computing fingerprints; preserve explicit choices.
- Ship a compact, runnable example for each route, including known-bad texts and honest author self-reviews.
- Read saved SourceGuard, LogicGuard and WorldGuard report statuses at closure. Missing or failing required reports forbid broad claims and are named in residual risk; textual closure status remains based on the current reader chain.
- Require quoted review rows for every body or note limitation and every prohibited overclaim. Optional forbidden regular expressions also produce deterministic audit findings.
- Rename the audit dimension `binding_coverage` to `binding_declared`; declared bindings do not establish semantic correctness.
- Bind planned units by exact, unique quotations that are resolved against the current text on every run. Missing or ambiguous quotes and contradictory explicit IDs fail clearly; ID-only requests remain supported.
- Add the read-only `show_plan.py` command to display the composition plan beside its bound text, as plain text or JSON.

## [4.0.10] - 2026-10-22

### Changed

- Run CI on every push and pull request, and publish only after successful CI on the same commit.
- Record whether a reader judgment comes from an independent context or a self-review. Self-review can pass the text checks, but keeps an explicit risk and never permits a broad claim.
- Ask the user to resolve a material open choice before routing or planning a brief.
- Let fiction requests provide a structured voice contract for point of view, tense and narrative distance.
- Keep JSON schemas compact and remove unused preflight fingerprints and hash helpers.
- Strengthen model checks for ownership, bounded research and repair outcomes, and keep the model tree aligned with the code.
- Make `pip install .` register project metadata only; install the skill with `scripts/install_skill.py`.

### Fixed

- Resolve relative artifact paths from the request or referenced record that contains them.
- Report failed upstream inputs and vanished artifact units directly, before filling fingerprints or continuing the reader chain.
- Find an editable ResearchGuard source outside the sibling directory while preserving explicit source priority and compatibility with a stale imported module.

### Removed

- Tracked execution journals from public repository files.

## [4.0.9]

Slim release from the slim/2026-10 audit.

### Changed

- Require ResearchGuard 0.5.0 or newer, declared once as `RESEARCHGUARD_MIN_VERSION` in `skills/logic-writing/scripts/_common.py`, instead of the exact 0.5.7 contract. The member preflight also finds the `researchguard` command on PATH, and a release job runs the tests and member preflights on that minimum.
- Point the SourceGuard, LogicGuard and TraceGuard steps at the `source`, `logic` and `trace` routes of the merged `researchguard` skill.
- Let command-line requests name upstream records as JSON file paths, while scalar IDs, artifact paths and opaque native locators remain strings; the commands compute the fingerprints and references a caller leaves out and still check the ones given.
- Derive closure as `passed` or `needs_repair` from the current reader and route chain and an independent reader judgment; `derive_closure.py` exits 1 when closure does not pass, and repair is one text rule instead of typed repair requests.
- Make the ResearchPacket an optional evidence record and the travel workflow and itinerary model on demand; the fiction and travel route guides name the story and itinerary checks to run.
- Publish after ordinary CI steps (tests, fiction and travel regressions, FlowGuard models and map check) instead of the frozen validation gate; keep the OpenSpec specs in line with current behavior.
- Add `scripts/install_skill.py`, which installs only the runtime skill files and can `--check` an installed copy.
- Write the skill description in the "Use for ... Not for ..." form.

### Removed

- Receipt authority, invocation envelopes, review-execution capture, closure receipts, the ResearchGuard handoff consumption binding and the native depth-receipt fields.
- The production reader pipeline, the writing-quality experiment harness, the frozen release gate, text and constant locks, the 16.7 MB `.flowguard/models/authority/` store, predecessor retirement records and outdated OpenSpec specs.
- Eight abstract FlowGuard models; the two remaining models replay their traces on the real reader chain and on real routing and preflight, including the ResearchGuard PATH fallback (a fake `researchguard` command on a temporary PATH).

### Fixed

- SourceGuard, LogicGuard and TraceGuard work again with ResearchGuard 0.5.9.
- fiction and travel accept evidence-gap packets, the Documents preflight accepts a skill named `docx`, and WorldGuard is found next to the skill by default.
- `scripts/validate_skill.py` no longer writes `__pycache__` into the skill.
- Installed-skill checks compare actual file bytes even after a same-process cache warmup with unchanged file size and timestamps.

### Audit actions

- Done: LW-01–LW-59.
- Skipped: none.
- Cross-repo pass: XR-04, XR-05, XR-06, XR-07, XR-11, XR-12; skipped none. Details in the cross-repo action list.

## [4.0.8]

### Fixed

- Authorize repair progress only from the complete current reader and route chain plus independently captured judge output, including judgments that still need repair; preserve strict defect reduction and the one-no-progress stop.
- Bind seven named longform negative families to their intended native issues, with otherwise valid fixtures; input loading and schema failures cannot stand in for domain rejection.
- Keep distinct relative and absolute longform closure cases in their single native owner, remove the duplicate lifecycle positive, and combine reader-projection assertions into one execution.
- Use the official FlowGuard 0.70.6 toolchain while retaining the exact ResearchGuard 0.5.7 provider contract and existing synthetic hash fixtures.

## [4.0.7]

### Fixed

- Replace shallow travel/fiction inventory tests with direct native positive and exact negative checks for fallback reachability and unbound prose.
- Run five shared longform positive cases only in their existing longform owner; retain the six unique native cases and all longform failure and artifact-binding checks.
- Use FlowGuard 0.70.5 for ordinary maintenance while retaining the exact ResearchGuard 0.5.7 provider contract and its synthetic fixtures.

## [4.0.6]

### Fixed

- Resolve every declared native dependency as a current passing authority original before final reader closure, including non-persisting calls; use the existing canonical final receipt route and domain for persistence.
- Bind automatic publication to the sole frozen ordinary validation job on the same source commit.
- Clarify text/markdown automatic closure versus native DOCX/PDF binary and rendering duties, and make the optional coordination-file read conditional.
- Align current provider contracts and synthetic fixtures with ResearchGuard 0.5.7 and the ordinary toolchain with FlowGuard 0.70.4. Synthetic fixture status is not provider-execution or writing-quality evidence.

## [4.0.5]

### Fixed

- Refreshed canonical fiction/travel fixture byte references and the ResearchGuard 0.5.6 provider contracts; real user artifacts still use exact byte hashes.
- Bound passing judgments and final closure to the current independent capture, its actual JSON output and current intent/writer/artifact identities. Missing, unrelated or changed capture evidence cannot license pass.
- Reused one same-call artifact/audit validation in closure and reject artifact changes before emission.
- Added portable WorldGuard launcher preflight with an explicit contained skill root.

### Simplified

- Removed SkillGuard author contracts, duplicated local skill copies, the old 22-receipt proof mesh and nested pytest launches. Retained native state models, real bad variants, ordinary domain tests and current FlowGuard 0.70.3 map bindings.
- Kept one full pytest owner in ordinary offline release; live quality experiments remain explicit finite-budget operations. Independent reader review remains required for actual final closure.
- Documented one independent review context for route and reader responsibilities, aligned the one-no-progress stopping rule, and removed the unused fiction self-proof bundle.

## [4.0.4]

### Fixed

- Closed the ReaderSpine repair and closure path so repaired reader artifacts keep one current producer identity, compact prompt projections, and explicit no-progress safeguards.
- Made quality execution opt-in with finite local budgets and added lifecycle, release-wrapper, freshness, and repair-invariant coverage.
- Refreshed the SkillGuard v2 author contract and FlowGuard model authority/depth receipts for the current 22-model Logic Writing mesh.

## [4.0.3]

### Fixed

- Hardened frozen-validation receipt reuse so a cached result must remain under
  its own owner attempt and match the current result identity before reuse.
- Bound reader-quality consumers to one producer dependency index, held-out
  implementation/policy pair, and current source/toolchain fingerprints.
- Added release-wrapper and preflight dependency counterexamples while keeping
  real model quality batches explicitly out of this patch release.

## [Unreleased]

- Hosted release metadata is intentionally not asserted by this source file.

## [4.0.2]

### Fixed

- Hardened the local execution backend so provider errors and structured tool
  events remain separate, the fixed disable list is deterministic, and failed
  attempts preserve their original evidence.
- Added direct counterexample coverage for unknown event shapes and non-zero
  provider exits.
- Added the current ResearchGuard behavior-commitment candidate boundary while
  keeping incomplete native evidence explicitly blocked.

## [4.0.1]

### Fixed

- Adopted the compact SkillGuard v3 author contract with one explicit,
  sequential current-validation route and portable check wrappers.
- Bound the provider adapters, examples, schemas, and current OpenSpec
  requirements to ResearchGuard `0.5.2` while retaining the single console and
  the three supported direct members.
- Refreshed the local execution timeout split and the ResearchGuard topology
  scan so current checks fail visibly without traversing historical evidence.

## [4.0.0]

### Fixed

- Bound the current ResearchGuard provider identity to the released `0.5.1`
  distribution and one exact `researchguard` console identity.
- Kept LogicGuard, SourceGuard, and TraceGuard as the only active direct
  members while making ExperimentGuard and umbrella requests visible scope
  blocks with no fallback execution.
- Refreshed FlowGuard 0.69.0 verification inputs, installed SkillGuard
  projection, global-router pointer, route smoke coverage, and release metadata
  for this patch.

## [3.0.1]

### Fixed

- Bound the three direct ResearchGuard routes to the released `0.4.5`
  distribution and one exact `researchguard` console identity.
- Made unsupported provider versions, scope-out members, and provider evidence
  ownership visible without adding fallback paths or an automatic updater.
- Refreshed current release metadata, fixtures, and maintenance evidence while
  preserving the `3.0.0` history below.

## [3.0.0]

### Added

- Immutable `ReaderIntent`, whole-artifact `CompositionPlan`, exact-byte
  `ArtifactMap`, and route-specific composition contracts for investigation,
  academic writing, fiction, and travel.
- Three separate actual-artifact quality owners: deterministic ReaderAudit,
  route-semantic span review, and independent ReaderJudgment.
- Typed repair requests and results with preservation duties, defect lineage,
  byte-level progress, and real no-progress termination.
- A frozen twelve-case Chinese/English reader benchmark with three cases per
  route.

### Changed

- Replaced finding-order and unit-card drafting with integrated whole-artifact
  composition and complete plan-to-byte coverage.
- Made revision provenance conditional on artifact mode rather than academic
  ownership.
- Upgraded managed reader receipts and closure to schema version 2.0.

### Removed

- Removed v1 reader-contract authority, caller quality shortcuts, repeated
  closure attempts as progress, and all normal-runtime compatibility, alias,
  converter, dual-emission, and fallback paths.

## [2.1.3]

### Changed

- Adopted the current SkillGuard 0.4.1 author contract and bounded evidence
  lifecycle while preserving Logic Writing's exact eleven target-declared
  checks and native domain criteria.
- Upgraded the FlowGuard project record to 0.59.0 and materialized the existing
  behavior commitment ledger in the current canonical form without changing
  its fourteen declared commitments.
- Kept transient validation runs, staging data, caches, and author receipts out
  of the independent consumer projection and release authority.

## [2.1.2]

### Changed

- Refreshed the private author-side SkillGuard contract under the current
  affected-only validation ownership model.
- Bound all current ResearchGuard provider examples, topology checks, and
  migration guidance to the single ResearchGuard `0.1.2` distribution.
- Retained one `logic-writing` entrypoint and one ResearchGuard console with no
  predecessor alias, alternate launcher, compatibility reader, or fallback.

## [2.1.1]

### Fixed

- Resolved the one installed ResearchGuard console from its exact distribution
  record instead of depending on ambient Windows PATH state.
- Kept missing, ambiguous, failing, and timed-out provider probes terminal; no
  PATH lookup, old-module import, module command, checkout override, alternate
  member, or fallback launcher was added.
- Updated the project to FlowGuard 0.58.1 and its single `flowguard` entry.

## [2.1.0]

### Changed

- Kept `logic-writing` as the sole public skill while routing LogicGuard,
  SourceGuard, and TraceGuard through the single ResearchGuard `0.1.0`
  console and their exact `logic`, `source`, and `trace` member commands.
- Preserved the three Guard semantic owners and native receipt boundaries
  without publishing them as Logic Writing child skills.
- Bound source, tests, FlowGuard, SkillGuard, and current fiction handoffs to
  the same ResearchGuard primary-path identities.

### Removed

- Direct `logicguard`, `sourceguard`, and `traceguard` Python/module provider
  paths, retired LogicGuard satellite-skill routes, `traceguard-library`, and
  all provider retry, alias, or compatibility paths.

## [2.0.0]

### Added

- Four final-owner routes behind one `logic-writing` entrypoint:
  `investigation`, `academic-writing`, `fiction-writing`, and `travel-guide`.
- A neutral shared writing contract for contribution, reader-state movement,
  specific handoffs, register ownership, effect-aware variation, actual
  artifact identity, and model-span binding.
- WorldGuard as a first-class native adapter.
- Preserved fiction compact/short/long-form/final-manuscript models, Guard
  lifecycle, semantic review, model mesh, and exact known-bad regression family.
- Preserved travel source-time, weather/alert, feasibility, lodging, fit,
  negative-evidence, reachable-fallback, traveler-native, and reverse-guide
  regression families.

### Changed

- Travel consumes the shared reader-projection kernel instead of invoking
  Storyline Design.
- Investigation and academic writing gain reader-state, question-recovery,
  explanation-pressure, register, variation, friction, and model-artifact
  guidance without weakening existing evidence and provenance gates.
- FlowGuard, SkillGuard, public docs, release validation, and installation now
  describe one entrypoint and four routes.

### Removed

- Separately installable `storyline-design` and `travel-story-planner` runtime
  authorities, aliases, and sibling-route dependencies. Historical schema
  strings may remain only inside frozen regression implementation material.

## [1.0.2]

### Fixed

- Replaced the archived change-local verification path with one stable current
  release contract at `openspec/verification-contract.yaml`.
- Added FlowGuard model-miss, Model-Test Alignment, TestMesh, and regression
  coverage for live consumers that retain a change-lifecycle contract path.
- Added a mandatory full post-archive release gate so pre-archive evidence
  cannot authorize a tag for source that changed during archival.
- Preserved the published v1.0.0 and v1.0.1 identities; this correction uses a
  higher patch version instead of rewriting release history.

## [1.0.1]

### Fixed

- Renamed the authoritative evidence-receipt schema so OpenSpec's frozen
  validation snapshot cannot mistake it for a generated receipt output.
- Added finite same-class checks for tracked source names that collide with
  OpenSpec's generated-output classifier, with FlowGuard model-miss,
  Model-Test Alignment, and TestMesh projections.

## [1.0.0]

`1.0.0` identifies the first Logic Writing source version line. It does not, by
itself, state that a corresponding Git tag or hosted release exists.

### Added

- One public `$logic-writing` entrypoint.
- Two internal final-owner routes: `investigation` and `academic-writing`.
- A bounded academic-to-investigation evidence-gap request.
- `ResearchPacket` as the default cross-route evidence handoff.
- `ReaderBrief` as the clean-room contract between internal evidence work and
  reader-facing prose.
- Actual-artifact reader audit with deterministic diagnostics kept separate
  from clarity and coherence judgment.
- Bounded adapters for SourceGuard, LogicGuard, TraceGuard, FlowGuard,
  Documents, and PDF.
- Explicit freshness, degraded-state, no-progress, and closure rules.
- Public architecture, responsibility, migration, contribution, and
  release-retirement documentation.

### Changed

- Consolidated the intended public invocation of investigation and academic
  writing under one named skill while preserving separate internal ownership.
- Made the terminal deliverable, rather than the first activity, the route
  selection rule.
- Made reader-facing language a first-class contract rather than a final
  cosmetic rewrite.

### Migration boundary

- The former `research-investigation-workflow` and
  `academic-thesis-revision-workflow` ids are not compatibility aliases.
- Predecessor runtime records are not accepted as current Logic Writing
  evidence.
- Remote-repository retirement remains a separate state-changing action and is
  not implied by this changelog entry.
