## 1. Foundation, authority, and recoverability

- [x] 1.1 Verify both predecessor source repositories, installed skill locations, remotes, tags, working-tree changes, and active references.
- [x] 1.2 Create full Git bundles, uncommitted-change patches, SHA-256 manifests, and restore receipts outside the public repository.
- [x] 1.3 Restore both bundles into isolated clones and verify expected HEADs and tag counts.
- [x] 1.4 Keep private investigation material out of the new repository and record the public/private boundary.
- [x] 1.5 Initialize a clean `LogicWriting` repository on branch `main`.
- [x] 1.6 Initialize OpenSpec and the `logic-writing` skill with the official skill scaffold generator.
- [x] 1.7 Complete and strictly validate the OpenSpec proposal, design, five capability specs, and verification contract.
- [x] 1.8 Add repository-local coordination guidance and confirm no peer owns any path before each edit phase.

## 2. FlowGuard models and execution plan

- [x] 2.1 Run the current FlowGuard toolchain preflight from the new repository and record schema, package, runtime, and source identity.
- [x] 2.2 Create the parent `logic_writing_lifecycle` model with separate `agent_operation` and `development_process` planes.
- [x] 2.3 Create the `route_and_guard_model` with exactly-one-owner and specialist-adapter FunctionBlocks.
- [x] 2.4 Create the `research_packet_model` with packet assembly, validation, handoff, rejection, and no-progress states.
- [x] 2.5 Create the `reader_artifact_model` with ReaderBrief, real-artifact writing, postwrite audit, repair, and current-artifact binding.
- [x] 2.6 Create the `operation_freshness_closure_model` with source-to-packet-to-brief-to-artifact staleness and monotonic closure.
- [x] 2.7 Create the `release_retirement_model` with frozen validation, staged install, activation/rollback, global route, release, and sequential retirement.
- [x] 2.8 Represent every FunctionBlock as `Input x State -> Set(Output x State)` and identify all state and side-effect owners.
- [x] 2.9 Create the behavior commitment ledger, one Primary Path Authority, and cross-plane relation records.
- [x] 2.10 Add normal scenarios, blocked/recovery scenarios, three KnownBadProof models, finite bad-case families, SCC/no-progress checks, and progress/fairness obligations.
- [x] 2.11 Run model-first checks, scenario review, conformance replay, stuck/loop review, success reachability, terminal-edge review, progress/fairness, and contract/refinement checks.
- [x] 2.12 Preserve current model receipts and a human-readable FlowGuard adoption log without treating logs as source authority.

## 3. Repository and skill package structure

- [x] 3.1 Add license, version, changelog, contribution guide, package metadata, Git ignore rules, and a source-only release layout.
- [x] 3.2 Keep one canonical implementation copy under `skills/logic-writing`; do not add repository-root script duplicates.
- [x] 3.3 Replace the generated `SKILL.md` with a concise one-entrypoint router under 500 lines.
- [x] 3.4 Finalize `agents/openai.yaml` with display name `Logic Writing`, a valid short description, and a default prompt that invokes `$logic-writing`.
- [x] 3.5 Add `references/router.md` and route references for `investigation` and `academic-writing`.
- [x] 3.6 Add specialist adapter references for SourceGuard, LogicGuard, TraceGuard, FlowGuard, Documents, and PDF.
- [x] 3.7 Add shared references for ResearchPacket, ReaderBrief, human writing, closure, and failure/status semantics.
- [x] 3.8 Check every reference path from `SKILL.md` and keep progressive disclosure route-specific.

## 4. Typed schemas and portable data contracts

- [x] 4.1 Add and validate the route-decision schema with exact final owner, child routes, input fingerprint, and stale state.
- [x] 4.2 Add adapter request/result schemas that preserve native owner, route, receipt, scope, and failure state.
- [x] 4.3 Add the SourceRegistry schema with locators, dates, coverage periods, roles, lineage, independence, support boundaries, and access status.
- [x] 4.4 Add the ClaimSupport schema with claim strength, source roles, can/cannot-support boundaries, alternatives, and safe wording.
- [x] 4.5 Add the ResearchPacket schema with exact member manifests, current native receipts, gaps, and packet fingerprint.
- [x] 4.6 Add the ReaderBrief schema with reader, genre, concepts, sequence, evidence, limitations, citations, and prohibited wording.
- [x] 4.7 Add receipt and closure schemas with typed evidence domains, exact fingerprints, terminal states, residual risk, and next owner.
- [x] 4.8 Add revision-provenance and reader-judgment schemas.
- [x] 4.9 Reject former predecessor runtime shapes as invalid inputs; do not add a reader, converter, alias, or fallback.

## 5. Core routing, packet, reader, and closure implementation

- [x] 5.1 Implement `select_route.py` with exactly-one-owner, terminal-deliverable routing, ambiguity, and out-of-scope behavior.
- [x] 5.2 Implement portable canonical hashing and input-manifest utilities.
- [x] 5.3 Implement provider preflight without persisting machine-specific import paths.
- [x] 5.4 Implement adapter-result validation without re-running or replacing native specialist checks.
- [x] 5.5 Implement SourceRegistry validation and candidate/source/lineage boundary checks.
- [x] 5.6 Implement claim-support validation for source role, scope, time, causality, execution, forecast, and independence.
- [x] 5.7 Implement ResearchPacket assembly and verifier-derived packet status.
- [x] 5.8 Implement exact ResearchPacket handoff validation and bounded repair responses.
- [x] 5.9 Implement ReaderBrief compilation that strips internal execution language while preserving citations, limitations, and uncertainty.
- [x] 5.10 Implement actual-artifact parsing, reverse-outline derivation, internal-language checks, and deterministic reader-flow diagnostics.
- [x] 5.11 Implement revision-provenance validation for added, rewritten, moved, omitted, and unresolved treatments.
- [x] 5.12 Implement content-addressed receipt storage with immutable terminal-success reuse and failed-attempt visibility.
- [x] 5.13 Implement dependency-driven staleness propagation for operation and development planes.
- [x] 5.14 Implement verifier-derived monotonic closure and no-progress loop blocking.
- [x] 5.15 Implement validation of separately judged reader-quality receipts.

## 6. Investigation route upgrade

- [x] 6.1 Port the claim/evidence intake, source policy, reasoning-atlas, source-role, key-claim/key-number, and impact-chain strengths from the investigation predecessor.
- [x] 6.2 Replace the old 18-stage flow with a bounded sequence: contract, discovery, trace/argument deepening, packet, reader artifact, and closure.
- [x] 6.3 Bind SourceGuard discovery and native source-depth receipts without copying its planner.
- [x] 6.4 Bind LogicGuard source-library preservation and content modeling for concrete sources.
- [x] 6.5 Bind TraceGuard only for temporal, implementation, causal, counterfactual, competing-storyline, or prediction-boundary claims.
- [x] 6.6 Bind LogicGuard model depth, conclusion competition, citation semantics, and artifact synthesis without making outlines final prose.
- [x] 6.7 Preserve access gaps, dependent lineages, negative findings, and bounded native results in final wording.
- [x] 6.8 Make the default final product a reader-ready investigation report or a bounded ResearchPacket, not an internal audit dump.

## 7. Academic-writing route upgrade

- [x] 7.1 Port reader-native prose, section interface, structural contribution, revision provenance, literature progression, method depth, figure/table, citation, and footnote strengths from the academic predecessor.
- [x] 7.2 Bind LogicGuard structured-artifact review and model deepening to actual academic units.
- [x] 7.3 Bind LogicGuard artifact synthesis to story plans and paragraph blueprints while keeping final prose ownership in Logic Writing.
- [x] 7.4 Implement bounded academic-to-investigation gap requests that never transfer final ownership.
- [x] 7.5 Bind Documents for DOCX mutation, tracked changes, comments, style/layout work, render, and page inspection.
- [x] 7.6 Bind PDF for extraction, creation, rendering, and visual inspection while keeping text and layout evidence separate.
- [x] 7.7 Preserve citation/source-role fit, revision provenance, artifact structure, figures/tables, and limitations across final prose integration.
- [x] 7.8 Require a postwrite audit of the exact final academic artifact and stale it after any material edit.

## 8. Current SkillGuard authority and project adoption

- [x] 8.1 Inventory the target skill entrypoint, routes, source rules, native checks, added checks, evidence, test gaps, and closure blockers.
- [x] 8.2 Create the sole current `.skillguard/contract-source.json` with the reviewed integration mode and native owner bindings.
- [x] 8.3 Create target-owned positive and single-important-gap shallow-negative calibration fixtures.
- [x] 8.4 Compile `.skillguard/compiled-contract.json` and the exact `.skillguard/check-manifest.json` from current source.
- [x] 8.5 Run runtime-authority, contract, and depth checks; remove every former-runtime residual.
- [x] 8.6 Adopt the repository with `.skillguard/project.json` and the marker-bounded AGENTS maintenance block.
- [x] 8.7 Run project audit and ensure the managed block preserves all unrelated repository instructions.

## 9. Tests, fixtures, and validation owners

- [x] 9.1 Add unit tests for routing, ambiguity, trivial skip, owner stability, and decision staleness.
- [x] 9.2 Add contract tests for every specialist adapter and every unavailable/degraded provider state.
- [x] 9.3 Add investigation tests for candidate-source boundaries, lineage, execution evidence, TraceGuard conditions, packet assembly, and verifier-derived closure.
- [x] 9.4 Add academic tests for structural contribution, progression, model depth, bounded source handoff, document/PDF states, citations, and provenance.
- [x] 9.5 Add reader tests for ReaderBrief sanitization, actual text parsing, reverse outline, concept introduction, referents, transitions, genre, and judgment separation.
- [x] 9.6 Add freshness/closure tests for exact identity, dependency invalidation, operation/development separation, monotonic states, and no-progress blocking.
- [x] 9.7 Add adversarial fixtures for candidate-as-fact, chronology-as-causality, metadata-false-positive prose, stale packet, stale audit, missing renderer, outline-as-final, and process-green/content-not-run.
- [x] 9.8 Add positive and intentionally shallow negative reader-quality calibration fixtures.
- [x] 9.9 Add end-to-end investigation, academic revision, and academic-with-investigation-child scenarios.
- [x] 9.10 Add installed-skill route smoke scenarios for both routes and the bounded cross-route handoff.
- [x] 9.11 Add portable validation wrappers for skill static validation, privacy, installation parity, global routing, release surface, and retirement residuals.
- [x] 9.12 Run Model-Test Alignment and bind every important model obligation to code and test evidence.
- [x] 9.13 Freeze the TestMesh owner plan with one primary owner per exact check and persistent receipt roots.

## 10. Public documentation and release surface

- [x] 10.1 Write an English-first README that explains one skill, two routes, shared evidence, reader-ready output, installation, examples, requirements, and boundaries in ordinary language.
- [x] 10.2 Write a complete Chinese mirror with the same section order and claims.
- [x] 10.3 Create a public hero visual with generation provenance and verify README rendering.
- [x] 10.4 Write `MIGRATION.md` with exact old-to-new route mapping, clean version line, no compatibility path, backup/recovery boundary, and residual-reference checklist.
- [x] 10.5 Write `CHANGELOG.md`, `CONTRIBUTING.md`, architecture, responsibility-map, and release/retirement checklist documents.
- [x] 10.6 Remove every placeholder, local path, secret, private case, internal coordination record, and unsupported release claim from tracked files.
- [x] 10.7 Keep the immutable initial `v1.0.0` identity and the repaired `v1.0.1` version, README status, changelog, tag, and release notes synchronized.

## 11. Frozen validation and repair

- [x] 11.1 Complete focused unit, contract, adversarial, E2E, model, and judgment checks while source is still changing.
- [x] 11.2 Fix every failure and rerun only the affected owner checks.
- [x] 11.3 Define the frozen source, model, contract, toolchain, and impact-plan identities consumed by the final validation owner.
- [x] 11.4 Define one final full validation owner and immutable child-receipt aggregation without duplicate execution ownership.
- [x] 11.5 Require confirmed zero descendant processes after any timeout or interruption before accepting evidence or starting another owner.
- [x] 11.6 Include OpenSpec strict validation, SkillGuard current-authority/contract/depth checks, project audit, privacy review, and public-release checks as required owners.
- [x] 11.7 Prepare the reader-quality judgment owner and representative actual-artifact fixtures.
- [x] 11.8 Define the final report fields for claim boundary, skipped checks, residual risk, accounting, and terminal receipt hashes.
- [x] 11.9 Backpropagate the frozen-source filename collision into OpenSpec, FlowGuard Model-Miss Review, a finite ContractExhaustionMesh family, Model-Test Alignment, TestMesh, and an observed-plus-same-class regression.
- [x] 11.10 Make the reader-judgment check self-contained under one frozen execution owner instead of depending on a pre-existing ignored runtime file.
- [x] 11.11 Exclude ignored coordination, adoption, and verification-receipt records from frozen public-source materialization, and bind the observed failures into FlowGuard and regression tests.
- [x] 11.12 Replace repository-dot check selectors with concrete admitted-source manifests and expand the frozen freshness inventory to every public source surface those checks observe.
- [x] 11.13 Make privacy fallback honor the same admitted-source exclusions and keep Git cleanliness, branch, commit, tag, and hosted-release identity outside metadata-free frozen source checks.

## 12. Install and global route cutover

- [x] 12.1 Prepare an isolated SkillGuard target-install stage from the exact installation projection.
- [x] 12.2 Verify the stage, activate atomically, and confirm the prior active installation remains recoverable until post-activation checks pass.
- [x] 12.3 Run active installed-skill smoke tests for investigation, academic writing, and research-to-writing ownership.
- [x] 12.4 Capture and replay the exact installation receipt and installed runtime fingerprint.
- [x] 12.5 Update active references in LogicGuard, LogicGuard model deepening, SourceGuard, and TraceGuard from the old academic id to `logic-writing`.
- [x] 12.6 Refresh the global SkillGuard registry and managed user AGENTS block.
- [x] 12.7 Verify exactly one current `logic-writing` route resolves and both predecessor routes are non-authoritative before local deletion.

## 13. GitHub publication

- [x] 13.1 Create the public `liuyingxuvka/LogicWriting` repository with a clean history and `main` as default.
- [x] 13.2 Push the reviewed source snapshot and verify repository identity, visibility, license detection, and public file boundary.
- [x] 13.3 Add an active main-branch ruleset that blocks deletion and non-fast-forward updates without duplicating protection.
- [x] 13.4 Run a fresh-clone validation and installation from the published commit.
- [x] 13.5 Create the annotated `v1.0.0` tag and GitHub Release only after the release gate consumes current install and validation receipts.
- [x] 13.6 Verify version file, commit, tag, release, README badge, and installed skill all refer to the same release identity.

## 14. Predecessor retirement

- [x] 14.1 Reverify both bundles, uncommitted patches, hashes, restore clones, final old HEADs, tags, releases, and zero-fork status immediately before retirement.
- [x] 14.2 Audit all active files, global routing, prompts, automations, and installed skills for old ids and old repository dependencies; require zero active residuals.
- [x] 14.3 Remove the two old installed skill directories and revalidate the active Logic Writing route and rollback boundary.
- [x] 14.4 Change `liuyingxuvka/research-investigation-workflow` to private through the authenticated GitHub CLI owner action.
- [x] 14.5 Verify authenticated visibility is `PRIVATE`, anonymous GitHub API access returns 404, and the Git HEAD, tags, and releases remain owner-accessible and unchanged; record a visibility receipt that explicitly does not claim deletion.
- [x] 14.6 Recheck the LogicWriting repository, release, installation, and routing health after the first privatization.
- [x] 14.7 Change `liuyingxuvka/academic-thesis-revision-workflow` to private through the authenticated GitHub CLI owner action.
- [x] 14.8 Verify authenticated visibility is `PRIVATE`, anonymous GitHub API access returns 404, and the Git HEAD, tags, and releases remain owner-accessible and unchanged; record a visibility receipt that explicitly does not claim deletion.
- [x] 14.9 Run the final legacy-residual audit, confirm Logic Writing is the only active supported route, and record the user-owned handoff for any later deletion of the two private repositories.

## 15. Archive-ready reconciliation

- [x] 15.1 Reconcile every current task, model, visibility receipt, backup identity, release identity, and validation input into one archive-ready snapshot.
- [x] 15.2 Run the explicit predictive-KB postflight and record the failed FlowGuard adoption preflight, user correction about planning versus execution, skill-combination lessons, GitHub deletion-scope fallback, and any new route gaps as structured observations when the KB accepts writes.
- [x] 15.3 Define the terminal completion audit that requires every milestone to be complete or explicitly blocked, all validation inputs frozen, and no obvious in-scope action remaining.
- [x] 15.4 Confirm completion now means installation, release, both local deletions, both remote privatizations, a user-owned deletion handoff, and final evidence reconciliation; it does not mean the private repositories were deleted.

Bounded evidence gap: the executable project models use the real FlowGuard `0.55.0` engine and are covered by the final validation contract, but `flowguard project-audit` separately reports `suite_map_missing` because this orchestration repository intentionally does not vendor FlowGuard's 17-skill agent suite and canonical suite map. No broad claim of complete project-level FlowGuard suite adoption is made from this repository.

Post-task closure is deliberately not represented as self-referential checkboxes. After all tracked tasks are complete: install the exact `v1.0.1` projection; run `openspec verify create-logic-writing`, fix and rerun until current; archive the change; strictly validate the archived specs; push and publish the immutable `v1.0.1` repair without moving `v1.0.0`; verify the hosted and installed identities; then mark the long-running goal complete.
