## Context

Logic Writing `1.0.2` has one public entrypoint, two final-owner routes, a typed ResearchPacket and ReaderBrief chain, actual-artifact audit, verifier-derived closure, five FlowGuard child models, eleven Behavior Commitments, eight SkillGuard checks, and a recoverable release/retirement flow. Storyline Design adds story contribution, promises, scene and chapter interfaces, continuity, reader-state simulation, model-prose binding, semantic review, and final-manuscript identity. Travel Story Planner adds traveler profile, time-sensitive source modes, weather/alert evidence, feasibility, route traces, lodging, fit, negative evidence, reachable fallbacks, traveler-native projection, and reverse-guide closure.

The three sources are not equally current. LogicWriting is clean at public `v1.0.2`. Travel's public and installed `v0.2.0` surfaces agree, while its older local worktree is not release authority. Storyline has a public `v0.4.0`, a newer installed projection, and a large uncommitted `harden-executable-story-closure` worktree with checked tasks and evidence outputs but no frozen release identity. The merge must therefore use an explicit source-disposition ledger rather than copying one directory wholesale.

The repository now carries the current FlowGuard 0.56.0 17-member agent suite required by its project contract. Existing product models remain the primary path and will be extended, partitioned, and reattached rather than replaced by a parallel framework.

## Goals / Non-Goals

**Goals:**

- Preserve one public skill id and exactly one final owner per non-trivial writing request.
- Add fiction and travel-guide final-owner routes without weakening investigation or academic behavior.
- Extract only behavior-equivalent shared kernels and keep genre-specific schemas and judgments with their route owners.
- Make reader-native quality observable through unit contribution, reader-state movement, explanation pressure, register ownership, variation pressure, model-artifact binding, and reverse audit of actual bytes.
- Preserve SourceGuard, LogicGuard, TraceGuard, WorldGuard, FlowGuard, Documents, and PDF as native specialist owners.
- Rebuild current FlowGuard, SkillGuard, installation, global-router, fresh-clone, release, and repository-retirement evidence.
- Privatize the two predecessor repositories only after a recoverable public replacement is proven.

**Non-Goals:**

- Creating a universal skill for all casual writing, marketing copy, grammar fixes, poetry, or quick travel suggestions.
- Forcing ResearchPacket fields into fiction or forcing story/travel fields into investigation and academic artifacts.
- Deterministically scoring literary beauty, originality, factual truth, or traveler satisfaction.
- Reimplementing any Guard-family specialist inside Logic Writing.
- Keeping compatibility aliases, dual manifests, old skill ids, fallback launchers, or two successful route authorities.
- Deleting the predecessor repositories.

## Decisions

### 1. One thin entrypoint owns four internal final routes

`SKILL.md` stays concise and routes by terminal deliverable to `investigation`, `academic-writing`, `fiction-writing`, or `travel-guide`. Route playbooks, shared contracts, schemas, examples, and validators remain progressively disclosed. Each request records one fingerprinted route decision; child work cannot issue parent closure.

Alternative rejected: expose four separately installed skills. That preserves duplicated activation boundaries and defeats the requested contraction.

### 2. Shared kernels are neutral contracts, not a mega-packet

The shared layer owns route decision, artifact identity, sanitized reader/audience brief base, structural contribution rows, reader-state interfaces, model-artifact binding, reader-room language review, reverse audit, receipt authority, freshness, and closure composition. Investigation keeps ResearchPacket, fiction keeps StoryModel/Canon and narrative ledgers, and travel keeps TravelPlan/Evidence and feasibility/fit records.

Alternative rejected: one universal JSON payload. It would make unrelated route fields mandatory, weaken route-specific semantics, and turn every change into whole-suite invalidation.

### 3. Travel consumes a neutral reader-projection kernel, not the fiction route

The existing Travel-to-Storyline projection becomes `shared.reader-native-projection`. Fiction and travel both consume it, while fiction owns story semantics and travel owns travel semantics. No sibling final route invokes another sibling final route.

Alternative rejected: keep Storyline Design as a hidden child skill. That would retain a second installation and create circular ownership after consolidation.

### 4. Genre-aware plain-language quality has a common base and route profiles

Common checks cover internal-language leakage, concrete referents, point-first structure, concept introduction, real handoffs, explanation pressure, register ownership, repeated contribution, variation pressure, and actual-artifact identity. Route profiles add evidence/citation fit for investigation and academic writing, dramatization/voice/payoff for fiction, and date/operability/fallback proximity for travel.

Alternative rejected: one prose rubric for every genre. Academic qualification and fictional dramatization often require opposite surface choices.

### 5. Storyline source authority is reconciled feature by feature

Public `v0.4.0`, installed current files, and the dirty executable-closure worktree receive frozen identities and a disposition matrix. A dirty feature is adopted only when its target-owned verification contract passes on a frozen snapshot; task checkboxes and old receipts alone are not authority. Public/installed behavior remains the minimum preservation baseline.

### 6. Validation uses balanced semantic owners

The target declares route, specialist authority, shared reader kernel, investigation, academic, fiction, travel, final closure, contract calibration, installation/release integrity, and predecessor retirement checks. Storyline's exact known-bad cases remain named fixtures even when several are executed by one semantic family owner. Travel's monolithic plan validator is partitioned behind route-owned modules while retaining one canonical composition owner. SkillGuard freezes and supervises the target-declared inventory without inventing domain semantics.

### 7. FlowGuard models form a parent/child mesh

The parent lifecycle model delegates disjoint partitions to routing/guard authority, evidence/research, shared reader artifact, fiction, travel, operation/freshness closure, and release/retirement children. Shared receipt/identity state is explicitly `shared_kernel`; route-owned fields and side effects do not overlap. Model-Test Alignment binds each commitment to one code contract and current test evidence. TestMesh owns routine/focused/release evidence and exact owner receipts.

### 8. Release is a major source-only release with dependency-ordered retirement

The version becomes `2.0.0`. The source release is committed, tagged, pushed, released, and verified from a new anonymous clone before active old skills are removed and before repository visibility changes. The old travel repository is made private first because it consumes Storyline Design; replacement health is checked; then the Storyline repository is made private. Each visibility step requires authenticated `PRIVATE` evidence and anonymous non-visibility. Any failure stops the sequence and restores the last changed repository to public.

## Risks / Trade-offs

- [Uncommitted Storyline work is treated as released truth] → freeze identities, run its native verification on an isolated snapshot, and adopt only verified rows.
- [The consolidated skill becomes too broad and activates for casual work] → keep terminal-deliverable routing, explicit skip cases, and adversarial activation fixtures.
- [Shared schemas erase genre semantics] → share base identity/handoff fields only; preserve route-specific packets and validators.
- [Reader-quality checks become cosmetic regexes] → combine deterministic leak/identity checks with artifact-bound semantic judgment and route-native reverse audits.
- [A copied FlowGuard suite drifts from its canonical source] → bind the suite-map hash, verify all 17 members, and treat future suite updates as explicit project maintenance.
- [Large merged validation becomes slow or opaque] → partition by semantic owner, freeze a TestMesh inventory, run focused checks during edits, and run exactly one final full owner on the frozen snapshot.
- [Privatization breaks remaining public users] → publish migration guidance, validate fresh installation without old ids, privatize the dependent travel repository first, and retain rollback to public.
- [Public release leaks local paths or dirty-worktree evidence] → install projection and public repo exclude run records, local backup manifests, absolute paths, caches, and private coordination material; run privacy checks before commit and release.

## Migration Plan

1. Freeze repository, public release, installed projection, dirty-worktree, FlowGuard, SkillGuard, and GitHub identities.
2. Complete and strictly validate this OpenSpec package; reconcile every provider task to a FlowGuard obligation/check owner.
3. Update the Behavior Commitment Ledger, parent/child models, architecture-reduction dispositions, model-test alignment, and TestMesh plan before production edits.
4. Implement the shared kernel and four route playbooks/modules; import only source-disposition rows marked verified.
5. Run affected checks, repair failures, freeze source/tool/inventory identities, and execute one full release validation owner.
6. Update public docs and version to `2.0.0`, archive the change, and rerun the stable repository release contract on the post-archive snapshot.
7. Install transactionally, refresh the global router, remove old active skill directories to recoverable quarantine, and run installed behavior checks.
8. Commit, tag, push, create the GitHub Release, and verify a fresh anonymous clone and install.
9. Make `travel-story-planner` private, verify replacement health, then make `storyline-design-skill` private and verify again.

Rollback preserves the prior active installation, local repository bundles, predecessor local worktrees, and public visibility until each downstream gate passes. No runtime compatibility route is retained.

## Open Questions

None. Route ids, release version, source authority, validation ownership, and repository-retirement order are fixed by the approved plan; route-local literary or travel judgments remain explicit run-time `human_review` outcomes.
