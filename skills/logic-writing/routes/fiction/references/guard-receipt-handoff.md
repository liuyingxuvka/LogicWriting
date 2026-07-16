# External Guard Receipt Handoff

StorylineDesign does not execute or reinterpret FlowGuard, TraceGuard,
WorldGuard, LogicGuard, or SourceGuard. Each Guard keeps its native owner.
StorylineDesign may count a Guard surface as passed only by consuming a
content-addressed terminal handoff.

## Required envelope

Each handoff records:

- `schema_version` and `guard_id`;
- `native_owner`, `native_route_id`, and `native_check_id`;
- `tool_version` and `receipt_schema_version`;
- the exact `input_fingerprint` covered by the native run;
- `terminal_receipt_id` and a contained, SHA-256-bound
  `terminal_receipt_ref`;
- `terminal_status` and a bounded `claim_boundary`.

The referenced native receipt must repeat the same identity fields and declare
`terminal: true`, `immutable: true`, and `freshness: current`. Runtime
timestamps, logs, and progress output are evidence metadata; they are not
source authority and do not refresh the receipt's input identity.

The checker opens the referenced receipt, recomputes its hash, confirms that
its owner, route/check, input fingerprint, status, and claim boundary match the
handoff, and rejects missing, changed, non-terminal, or self-authored evidence.

An embedded `passed: true`, a copied child report, a prose sentence, or a path
without a content hash is never a terminal Guard receipt.

`not_applicable_with_reason` is consumable only when the Guard-native terminal
receipt carries that exact status and claim boundary, while the closure row
also states a concrete applicability reason. StorylineDesign verifies that
handoff; it does not manufacture the Guard conclusion.
