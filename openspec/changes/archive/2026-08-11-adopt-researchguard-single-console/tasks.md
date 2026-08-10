## 1. Current provider identity

- [x] 1.1 Bind the three existing direct members to ResearchGuard `0.4.5`, the one `researchguard` console entry point, and their exact primary paths.
- [x] 1.2 Reject distribution/console/version mismatches, unsupported versions, provider-root overrides, timeout retries, and alternate member/module paths.
- [x] 1.3 Make `experimentguard` and the `researchguard run` umbrella an explicit scope-out with no provider execution.

## 2. Consumer and receipt boundary

- [x] 2.1 Update Logic Writing guidance and adapter references without changing the four public route meanings.
- [x] 2.2 Keep ResearchGuard native result/receipt ownership with ResearchGuard; consume only an opaque, fingerprinted provider reference plus Logic Writing's outer binding.
- [x] 2.3 Migrate the 24 current ResearchGuard fiction fixtures to `0.4.5` or mark them fixture-only; do not change WorldGuard's eight fixtures.
- [x] 2.4 Add negative tests for fake, foreign, stale, non-terminal, and mismatched-provider evidence.

## 3. Version, model, and maintenance records

- [x] 3.1 Freeze current Logic Writing source surfaces at `3.0.1` while preserving `3.0.0` history.
- [x] 3.2 Update the existing FlowGuard specialist/release owners and current model/test bindings; do not create a duplicate provider model.
- [x] 3.3 Recompile the SkillGuard contract and check manifest after all source/test inputs are stable.

## 4. Verification and installation

- [x] 4.1 Run focused provider, adapter, fiction, route, and privacy checks and inspect every failure/skip/stale result.
- [ ] 4.2 Run exactly one final full validation owner on the post-archive frozen source snapshot.
- [x] 4.3 Build, verify, and activate the clean `logic-writing` consumer projection; do not install author files or create an updater.

## 5. Release closure

- [x] 5.1 Validate OpenSpec strictly, synchronize current specs, and archive this change only after implementation evidence is current. (Stable specs were synchronized before archive; strict validation passed and the change was archived on 2026-08-11.)
- [ ] 5.2 Commit the owned source snapshot, push `main`, create and push annotated `v3.0.1`, and publish a source-only GitHub Release.
- [ ] 5.3 Verify source, installed projection, package, Git, tag, and GitHub Release identities separately.

## Verification Boundary

The change proves the current provider identity and Logic Writing's binding/closure boundary. It does not claim that provider domain work ran merely because the console is available, and it does not claim that any other computer was upgraded automatically.
