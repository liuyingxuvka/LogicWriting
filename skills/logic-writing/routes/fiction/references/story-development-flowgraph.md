# Story Development Flowgraph

Use this reference when StorylineDesign needs FlowGuard process evidence. The
flowgraph describes how the work was done. It does not decide whether the plot
is good.

## Purpose

The flowgraph prevents process failures:

- stages run out of order;
- child Guard handoffs are skipped;
- old evidence is reused after prompt, model, prose, fixture, or validator
  changes;
- final claims use progress-only evidence;
- installed copies drift from source;
- skipped checks are hidden as passes.

## Compact Shape

For small tasks, a compact process route may be a short structured note:

```json
{
  "surface": "flowguard_process",
  "status": "passed",
  "evidence_ref": "process-route:compact-note",
  "stages": ["intake", "guard_depth", "model", "draft_or_audit", "closure"],
  "child_guard_handoffs": {
    "traceguard": "not_applicable_with_reason",
    "worldguard": "passed",
    "logicguard": "not_applicable_with_reason",
    "sourceguard": "not_applicable_with_reason"
  },
  "stale_evidence": [],
  "blocks_closure": false
}
```

## Full Shape

For long-form, final, release, or skill-maintenance work, record grouped rows:

- changed artifacts: id, type, path, version or hash, upstream links;
- process steps: stage, status, reads, writes, invalidations, evidence
  produced;
- child Guard handoffs: required, skipped, not applicable, or blocked with
  reason;
- validation requirements: command, scope, required artifacts, status;
- freshness rules: which upstream changes stale which downstream evidence;
- final claim boundary.

## Required Findings

Keep these visible and blocking unless the claim is narrowed:

- `out_of_order_process_step`;
- `missing_child_guard_handoff`;
- `stale_evidence_after_artifact_change`;
- `hidden_skipped_validation_claimed_pass`;
- `failed_validation_claimed_current`;
- `validation_evidence_not_current`;
- `missing_required_revalidation`;
- `final_claim_missing_flowguard_process`;
- `installed_skill_drift`.

## StorylineDesign Consumption

StorylineDesign closure consumes the flowgraph as the `flowguard_process`
surface. It should not copy FlowGuard internals into prose. It should use the
surface to decide whether evidence is current enough to support the requested
story claim.
