## 1. Specify and model the repair

- [x] 1.1 Add the stable-contract, post-archive-gate, and immutable-patch requirements.
- [x] 1.2 Backfeed the v1.0.1 fresh-clone failure into FlowGuard as an archive-path lifecycle model miss.
- [x] 1.3 Bind the new bad-case family to Model-Test Alignment and TestMesh.

## 2. Implement one current release authority

- [x] 2.1 Add `openspec/verification-contract.yaml` as the sole live release contract.
- [x] 2.2 Repoint repository instructions, wrappers, public/privacy admission, tests, FlowGuard TestMesh, and commitment lookup to the stable path.
- [x] 2.3 Add a regression that scans live source for forbidden active-change contract references while permitting immutable archived history.
- [x] 2.4 Advance public source metadata and release checks to v1.0.2.

## 3. Verify before archival

- [x] 3.1 Run focused archive-lifecycle tests and FlowGuard alignment/TestMesh checks.
- [x] 3.2 Run strict OpenSpec validation for this change.
- [x] 3.3 Run the full active-change verification contract and fix every failure.

## 4. Freeze the archive and release handoff

- [x] 4.1 Confirm the active-change report is current and archive is blocked without that terminal pass.
- [x] 4.2 Bind the post-archive full gate, strict canonical-spec validation, immutable older tags, GitHub publication, fresh-clone replay, installed-route checks, predecessor privacy checks, handoff receipt, and predictive-KB postflight into the stable release plan.

The archive, post-archive validation, GitHub publication, fresh-clone replay,
installed-route checks, predecessor privacy checks, receipt update, and KB
postflight execute from the repository release plan after this OpenSpec change
is archived; they cannot be claimed by pre-archive evidence.
