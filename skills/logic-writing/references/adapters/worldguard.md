# WorldGuard adapter

Invoke WorldGuard when a material claim depends on whether events, agents,
spaces, resources, capabilities, conflicts, authority, or norms can coexist in
the proposed world. This applies to fictional settings as well as real travel
plans; “fictional” does not mean “consistency does not matter.”

Supply the exact world claims, relevant actors and spaces, resource and access
constraints, governing norms, time boundary, and the artifact fingerprint.
Consume WorldGuard's native result as `world_consistency` evidence. Preserve
unsupported, conditional, contradictory, stale, or not-run states exactly.
Logic Writing may explain the result to a reader, but must not recreate the
world judgment or upgrade it into success.

Run WorldGuard through its portable launcher:
`python <skills root>/worldguard/scripts/run_worldguard.py check --contract <contract.yaml>`.
The contract shape is described in WorldGuard's own
`references/worldguard-contracts.md`. Write the full output to a file and read
only `status`, `semantic_status`, `gaps`, and `scope_limits`.
`scripts/provider_preflight.py worldguard` finds the `worldguard` skill installed
next to `logic-writing`; pass `--provider-root <dir>` only when it is installed
elsewhere.

Report WorldGuard's own status unchanged. In route ledgers write it in lower
case: `PASS` -> `pass`, `FAIL` -> `fail`, `GAP` -> `gap`,
`BOUNDARY_EXCEEDED` -> `boundary_exceeded`; use `not_run` when WorldGuard did
not run.
