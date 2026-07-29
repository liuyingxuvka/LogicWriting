## Why

Logic Writing can preserve strong research and model evidence while still producing reader-facing artifacts that feel like disconnected findings, short card-like paragraphs, or route-default structures that overwrite the user's requested shape. The current pipeline loses material reader intent after routing, turns safe findings into a fixed information sequence, and can approve prose through metadata, connector words, or caller-authored scores without proving whole-artifact composition or a real repair cycle.

## What Changes

- **BREAKING** replace the free-form request constraints, RouteDecision v1, ReaderBrief v1, SharedWriting v1, ReaderAudit v1, ReaderJudgment v1, revision provenance, and closure bindings with current v2 contracts; reject old shapes with no alias, fallback, converter, or dual reader.
- Preserve one `ReaderIntent` from request through routing, brief, composition, artifact binding, audit, judgment, repair, and closure. User-specified structure, language, voice, length, format, and list policy remain authoritative unless a visible material conflict blocks drafting.
- Separate content authority from composition. Route-native evidence defines safe meanings, anchors, limitations, alternatives, exact-preservation duties, and prohibited overclaims; a whole-artifact `CompositionPlan` determines how those materials serve the reader.
- Stop treating one finding or model row as one paragraph by default. Allow several content units to support one planned unit and allow one important content unit to be developed across several artifact units.
- Add deterministic `ArtifactMap` and SharedWriting v2 bindings from required planned units and route model rows to exact current artifact spans and fingerprints.
- Split actual-artifact review into deterministic checks, route-native semantic checks, and independent reader judgment. Connector words, caller-authored pass fields, and self-scores cannot substitute for current artifact-bound evidence.
- Add typed repair requests and repair results. Every non-pass returns to the selected final route, preserves declared content boundaries, rebuilds affected evidence after edits, and terminates only after two genuine consecutive no-progress repair results.
- Add route-specific composition and actual-artifact checks for investigation, academic, fiction, and travel output without introducing new public skill entrypoints or one universal document template.
- Make revision provenance conditional on `artifact_mode`: new artifacts record explicit not-applicable status, while revisions bind source units to target units and treatments.
- Align all four route baselines with the shared reader chain while keeping each route's native evidence and sole final-owner authority.
- Upgrade FlowGuard project adoption, model authority, behavior commitments, field lifecycle, model-test alignment, and regression ownership to the current installed FlowGuard contract.
- Release the completed incompatible change as Logic Writing 3.0.0 after OpenSpec archival, one frozen final SkillGuard validation, transactional local installation, source/install parity, Git publication, and published-release verification.

## Capabilities

### New Capabilities

None. The new contracts and repair loop deepen the existing reader-facing and route capabilities rather than creating another public capability or skill.

### Modified Capabilities

- `unified-routing`: preserve ReaderIntent and structure authority while continuing to choose exactly one final owner by terminal deliverable.
- `reader-facing-synthesis`: replace finding-sequence prose generation with content boundaries, whole-artifact composition, actual-byte binding, independent judgment, and typed repair.
- `investigation-route`: add investigation composition profiles and artifact-bound report review.
- `academic-writing-route`: add academic composition profiles, hierarchy and paragraph contribution planning, artifact-bound review, and conditional revision provenance.
- `fiction-writing-route`: distinguish planning from reader-native prose, bind model obligations to real manuscript spans, and repair route-native prose defects.
- `travel-guide-route`: select a guide kind before composition, separate narrative body from operational appendix, and bind risk, fallback, weather, and traveler-fit duties to real spans.
- `evidence-freshness-closure`: require the same ReaderIntent, plan, final owner, and artifact identity across the shared reader chain; propagate edits and repair history; derive no-progress only from real repair results.

## Impact

- Schemas under `skills/logic-writing/assets/schemas/` and all current producers, validators, fixtures, and tests that consume the replaced contracts.
- Shared scripts for routing, ReaderBrief construction, artifact mapping, shared-writing binding, deterministic audit, independent judgment, repair, staleness, and closure.
- Route-specific references, scripts, fixtures, and native regressions for investigation, academic, fiction, and travel.
- FlowGuard models, behavior commitment ledger, field lifecycle inventory, model-test alignment, TestMesh, model regression manifest, authority snapshot, and release process evidence.
- SkillGuard author contracts, check manifest, clean consumer projection, transactional local installation, package version, Git tag, and GitHub Release.
- Existing saved v1 work packages are not accepted by the v3 runtime. If an externally persisted v1 package is discovered during inventory, it remains an explicit blocked migration requirement rather than activating a compatibility reader.
