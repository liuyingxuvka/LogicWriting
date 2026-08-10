# SkillGuard evidence lifecycle — Logic Writing 3.0.1

This record fixes the evidence boundary for the 3.0.1 release. It is a
maintenance record, not a consumer dependency and not an automatic updater.

## Current authority

- The maintained source is `skills/logic-writing`.
- The current author projections are the target's generated
  `.skillguard/compiled-contract.json`, `check-manifest.json`, and
  `contract-source.json`.
- The final full-validation receipt will be created under the ignored
  `run-artifacts/validation-receipts/` root after OpenSpec archival. That
  receipt is evidence for this release snapshot; it is not source authority.
- The activated consumer projection is outside this repository under the
  user's Codex skills directory. Its SkillGuard transaction and parity report
  are installation evidence, not author-state files to copy into the
  consumer.

## Non-authoritative material

The following locations are runtime or scratch material and are excluded by
the repository privacy/release contract:

- `run-artifacts/**` and `validation-receipts/**` — validation attempts and
  receipts;
- `.flowguard/evidence/**` and `.flowguard/adoption_log.jsonl` — FlowGuard
  runtime evidence and adoption logs;
- `skills/logic-writing/.skillguard/runs/**` — SkillGuard transient runs;
- `work/**`, `scratch/**`, `__pycache__/**`, and `.pytest_cache/**` — local
  tooling or interpreter caches.

These paths must not refresh source authority, be copied into the consumer,
or be used as a substitute for a current owner receipt.

## 3.0.1 lifecycle decision

1. Current generated author projections and the final owner receipt are
   retained as the release evidence chain.
2. Historical run roots were inspected before release. No safe, unreferenced
   path was identified whose removal would improve the public source without
   risking historical evidence references.
3. Therefore this release performs no destructive deletion and no blind
   quarantine. Historical runtime material remains ignored and outside public
   source authority; a later cleanup may move an explicitly enumerated path
   only after reference checks and a recoverable backup are recorded.
4. Source files, model files, protected evidence, active processes, and the
   activated consumer projection are not cleanup targets.

## Verification boundary

This record proves that the lifecycle was classified and bounded. It does not
claim that a provider-domain investigation ran, that another computer was
upgraded, or that historical ignored files are current release evidence.
