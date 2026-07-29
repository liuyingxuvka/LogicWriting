## Context

Logic Writing is one maintained public skill with four terminal routes. Its current shared reader pipeline derives a flat finding sequence and allowed wording from route evidence, audits surface proxies such as first sentences and connector words, and accepts caller-supplied qualitative scores. Fiction and Travel have deeper route models than Investigation and Academic, and current closure baselines do not require the same shared reader evidence across all routes.

The repository is an explicit SkillGuard author source. Official OpenSpec owns requirements artifacts, FlowGuard owns behavior/state/freshness modeling, route-native code owns semantic checks, and SkillGuard owns author-side validation inventory, clean consumer projection, installation, and release supervision. Current replacement forbids compatibility readers and alternate runtime authority.

The FlowGuard project record was upgraded to engine 0.65.1 before this design. The observed model system now has one current authority snapshot and seven registered model owners; its pre-change baseline retains explicit gaps and two failing model regressions that this change must close.

## Goals / Non-Goals

**Goals:**

- Preserve one exact ReaderIntent through the complete reader pipeline.
- Separate content authority from document composition and prose realization.
- Make route-native composition different for investigation, academic, fiction, and travel while sharing identity, binding, audit, repair, and freshness infrastructure.
- Bind every quality claim to the current artifact bytes and exact units.
- Replace proxy quality checks and self-scoring with deterministic checks plus independent, artifact-bound judgment.
- Make non-pass results repairable and make no-progress terminal only after real repair attempts.
- Use one current contract shape and one final owner without aliases, converters, fallback readers, or sibling closure.
- Produce a clean Logic Writing 3.0.0 consumer, transactionally install it, and publish one immutable GitHub release after frozen validation.

**Non-Goals:**

- Prove that an AI aesthetic judgment is objectively true.
- Replace SourceGuard, LogicGuard, TraceGuard, WorldGuard, Documents, PDF, or route-native semantic authority.
- Force every artifact into prose or ban functional lists, tables, appendices, plans, or audits.
- Create separate installed skills for the four routes or a second human-writer owner.
- Migrate unknown external v1 work packages silently during normal runtime.
- Run the final full validation in a background task, scheduled job, retry wrapper, or mutable checkout.

## Decisions

### 1. One shared reader kernel, four route-owned composition contracts

The shared kernel owns ReaderIntent preservation, content-boundary envelope validation, generic CompositionPlan fields, ArtifactMap, SharedWriting binding, deterministic audit, ReaderJudgment envelope validation, repair identity, freshness, and closure composition.

Each final route owns its composition profile, native fields, semantic audit, repair routing, and final closure. The shared kernel checks the selected extension's owner and fingerprint but does not interpret investigation evidence strength, academic contribution, fiction story movement, or travel feasibility.

Alternative considered: one universal section schema. Rejected because it would reproduce the current failure by mapping unlike genres onto one document grammar.

Alternative considered: four separate public skills. Rejected because routing, identity, installation, and shared repair semantics would duplicate, and v2 intentionally established one entrypoint.

### 2. ReaderIntent is a first-class immutable contract

`reader-intent.schema.json` contains:

- `artifact_mode`: `create_new` or `revise_existing`;
- `language`, `audience`, and `purpose`;
- `structure.mode`: `fixed`, `partially_fixed`, or `route_selected`;
- `structure.requested_outline[]`: stable id, parent, order, label, required flag, title lock, and source;
- heading, order, and list policies;
- style, voice, formality, required and forbidden traits;
- minimum, target, and maximum extent;
- artifact format, citation and table policy;
- required and forbidden content;
- reference examples;
- unresolved material choices;
- one `intent_fingerprint`.

Explicit user intent outranks route defaults. Evidence, safety, or format obligations may create a visible conflict but cannot silently replace the user contract.

Alternative considered: keep free-form `constraints`. Rejected because downstream contracts cannot validate or preserve untyped intent.

### 3. Direct current replacement of all reader contracts

Current schemas use version `2.0`; product release uses `3.0.0`. Current validators reject v1. There is no alias, converter, fallback, dual emission, compatibility reader, or legacy closure projection.

Before implementation, the repository inventories persisted v1 work packages. If externally promised packages exist, they become a separately specified explicit migration boundary. Their existence does not authorize a runtime fallback.

### 4. ReaderBrief becomes a clean-room composition packet

ReaderBrief v2 binds:

- RouteDecision and ReaderIntent;
- selected final owner and terminal deliverable;
- `content_boundaries`;
- route-authored `composition_plan`;
- one route extension;
- native content authority receipts and fingerprints;
- its own fingerprint.

Content boundaries use `safe_meaning`, evidence anchors, alternatives, limitations, must-preserve tokens, genuine verbatim obligations, structured citation duties, and prohibited overclaims. They do not expose allowed prose wording.

Composition units have stable parent and order, user-outline sources, reader job, incoming and outgoing reader state, relation to previous units, downstream consumers, content and limitation ids, presentation mode, and target extent. One content unit is never automatically one planned unit.

`build_reader_brief.py` becomes an assembly and validation facade. It does not derive final order from findings or write canned handoffs.

### 5. Route composition schemas are explicit

Investigation profiles: explanatory report, decision analysis, evidence audit, case trace.

Academic profiles: empirical paper, conceptual argument, literature synthesis, research proposal, chapter or section, user-defined.

Fiction declares output room and artifact kind, then plans story movements, scenes or chapters, promises and reveals, voice ownership, resistance or cost, and reader-state changes.

Travel declares guide kind before structure. It separates narrative body, operational appendix, source boundary, and recheck notes.

Investigation and Academic gain route script directories and child artifact models. Fiction and Travel retain their existing native owners and add real artifact mapping and stricter span evidence.

### 6. ArtifactMap is the sole mechanical parser

`artifact-map.schema.json` records the current artifact fingerprint and stable headings, paragraphs, lists, tables, quotes, route units, locators, offsets, and span fingerprints.

The shared builder parses generic text and Markdown. Fiction and Travel may add deterministic route maps for manuscript boundaries and guide zones, but those maps reference the shared artifact identity and do not re-implement semantic judgment.

An edit to current bytes changes the artifact identity and stales every affected binding, audit, judgment, repair result, and closure.

### 7. SharedWriting v2 proves plan-to-byte binding only

The current filename remains `shared-writing-contract.schema.json`, but schema version 2.0 replaces its meaning. It binds final owner, route decision, ReaderBrief, CompositionPlan, route extension, artifact, iteration, and unit bindings.

Each binding names planned units, artifact units, content units, model rows, route surfaces, exact locators, and span fingerprints. The validator proves current identity and required coverage; it does not decide whether a paragraph makes a good contribution.

Alternative considered: remove SharedWriting and rely only on ArtifactMap. Rejected because ArtifactMap is mechanical inventory, while SharedWriting records intentional plan/model realization.

### 8. Three actual-artifact review owners

1. Deterministic ReaderAudit verifies bytes, locked structure, must-preserve and verbatim duties, citation placement, allowed list zones, placeholders, workflow leakage, heading/list density, one-sentence or card-like fragmentation, and SharedWriting coverage.
2. Route-native actual-artifact review verifies investigation, academic, fiction, or travel semantic obligations from current spans.
3. Independent ReaderJudgment evaluates clarity, structure fidelity, coherence, naturalness, reader fit, content fidelity, genre fit, and instruction fidelity.

ReaderJudgment records producer and judge identities, evaluation profile fingerprint, semantic reverse outline, defects, strengths, and required repairs. Routine independent pass requires different producer and judge contexts, real locators and excerpts, no blocking defect, no required repair, and scores of at least four.

The schema proves judgment identity and evidence binding, not objective aesthetic truth. A fixed blind benchmark calibrates the quality boundary.

### 9. Typed repair replaces repeated closure derivation

`reader-repair-request.schema.json` binds the current artifact, reader brief, plan, audits, defect lineage, target units, required changes, preservation boundary, and forbidden shortcuts.

`reader-repair-result.schema.json` binds input and output artifacts, changed units, preservation result, remaining defect identity, and `progressed`, `no_progress`, or `blocked`.

Any edit reruns ArtifactMap, SharedWriting, deterministic audit, route review, and ReaderJudgment. Two consecutive current no-progress results for the same defect lineage produce terminal visible blocking. Calling closure twice never increments repair attempts.

### 10. Revision provenance is route-neutral and conditional

All routes use `artifact_mode`. Create-new explicitly records not applicable. Revise-existing binds source-unit ids to target-unit ids and treatments: preserved, rewritten, moved, split, merged, or omitted. Authorization and meaning or structure delta are required for material changes.

### 11. FlowGuard extends existing owners

The change extends `model:reader-artifact` and C04, C05, and C14. It does not add a second shared writing model. Route selection and final closure remain with their current owners.

The reader model adds intent, composition, integration, artifact map, shared binding, route audit, judgment, repair attempt, defect lineage, no-progress, and revision-applicability states. It adds capture, validate composition, draft, integrate, map, bind, audit, judge, repair, re-audit, and close transitions.

Investigation and Academic receive child artifact models under the lifecycle parent so all four final routes have route-native child closure. C15 and C16 register their external artifact promises without changing the shared C04/C05/C14 owner.

The current BehaviorCommitmentLedger source inventory remains one canonical JSON authority using exact per-commitment source rows. Model authority changes only through one accepted ModelRevisionSet after candidate checks.

### 12. Validation is layered and freshness-aware

Development checks run affected owners only. Route/schema/unit suites may run safely in parallel after their input interfaces freeze. The full FlowGuard model owner and full SkillGuard validation owner run once on the final frozen source.

The test inventory includes current schema rejection, routing, ReaderIntent propagation, composition coverage, ArtifactMap and span identity, shared binding, deterministic audit, independent judgment, repair convergence, closure, four route-native suites, multilingual fixtures, and four route end-to-end success and stale-edit cases.

A blind benchmark contains at least twelve fixed long-form cases, three per route, with Chinese and English coverage. Release requires 100% explicit-structure mapping or visible conflict, no evidence-fidelity regression, and a preferred coherence/naturalness result in at least nine of twelve cases.

### 13. Installation and publication are separate evidence domains

The active v2.1.3 installation remains available until the v3 consumer projection passes. SkillGuard prepares an isolated clean consumer, audits independence, activates transactionally with recovery, and verifies exact source/install projection parity.

Repository commit, tag, GitHub Release, installed consumer identity, and validation receipt remain distinct. OpenSpec is archived before the final stable release gate; because archival changes source identity, the final gate runs after archive and before tag. Published verification and a fresh clone confirm the immutable tag.

## Risks / Trade-offs

- [Risk] The new contracts increase authoring complexity. → Keep shared schemas route-neutral, use builders for fingerprints and receipts, and reject caller-authored identity fields.
- [Risk] Overly mechanical fragmentation metrics may reject intentional style. → Apply them only to prose-required zones and require qualitative route judgment for borderline cases.
- [Risk] Independent AI judgment can still be unreliable. → Bind it to actual spans, separate producer and judge identities, calibrate on fixed blind cases, and retain human review for high-stakes publication.
- [Risk] Four route implementations may drift. → Freeze the shared envelope first, require all four routes in shared E2E tests, and keep route semantics in one selected extension.
- [Risk] Direct replacement breaks saved v1 packages. → Inventory external promises before implementation and block on a separately required migration; do not weaken current runtime with compatibility.
- [Risk] FlowGuard 0.65.1 adoption gaps may obscure product work. → Close model manifest, authority, BCL, field, model-test, and test-mesh gaps as explicit tasks before broad claims.
- [Risk] Other AI or user edits may arrive during work. → Re-read coordination and status at milestones, preserve peer writes, and stale only affected evidence.
- [Risk] Final validation is long. → Run isolated affected checks during development, but reserve exactly one foreground final owner for the frozen snapshot.

## Migration Plan

1. Freeze the v2.1.3 failure benchmark, current producers and consumers, persisted package inventory, source identity, and current installation identity.
2. Complete and strictly validate this OpenSpec change.
3. Update FlowGuard models, behavior commitments, field lifecycle, model-test alignment, TestMesh, regression manifest, and candidate model authority.
4. Replace request, route, reader, binding, audit, judgment, repair, revision, receipt, and closure schemas with current v2 shapes.
5. Implement the shared pipeline and route-specific composition and artifact reviews.
6. Run affected schema, unit, route, adversarial, and E2E checks; repair every failure.
7. Update prompts, references, public docs, version, SkillGuard contract, compiled contract, and check manifest.
8. Complete OpenSpec verification and archive the change.
9. Freeze the post-archive source and run one final full SkillGuard validation owner plus the repository release gate.
10. Prepare and activate the clean local consumer transactionally; verify source/install parity and recover the prior active installation if activation checks fail.
11. Commit the exact release tree, tag `v3.0.0`, push main and tag, publish the GitHub Release, verify target commit and metadata, and validate a fresh clone.

Rollback before publication restores the previous active consumer transaction and leaves the v3 source available for forward repair. Rollback after publication never moves or replaces the published tag; corrections use a new version.
