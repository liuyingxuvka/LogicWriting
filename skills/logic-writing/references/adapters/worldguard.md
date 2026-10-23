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
`references/worldguard-contracts.md`. Bind each claim to the model with `claim.asserts` (WorldGuard's `references/guard-inputs.md` shows one row per Guard); a claim without `asserts` comes back `GAP` with gap code `CLAIM_NOT_BOUND`, and a false row comes back `FAIL` with `CLAIM_ASSERTION_FALSE`. The default output is a short JSON summary with status, checked (the Guards and claim rows checked), gaps (one row per problem, each with its code) and scope_limits; add --json only when the full report is needed.
`scripts/provider_preflight.py worldguard` finds the `worldguard` skill installed
next to `logic-writing`; pass `--provider-root <dir>` only when it is installed
elsewhere.

Report WorldGuard's own status unchanged. In route ledgers write it in lower
case: `PASS` -> `pass`, `FAIL` -> `fail`, `GAP` -> `gap`,
`BOUNDARY_EXCEEDED` -> `boundary_exceeded`; use `not_run` when WorldGuard did
not run.

Exit code 0 means PASS, 1 means a non-pass verdict (read status and gaps), 2 means the input could not be read; a non-zero exit is a result, not a crash.

Save the native report: `python <skills>/worldguard/scripts/run_worldguard.py check --contract <contract> > worldguard-check.json`. List `{"provider":"worldguard","path":"worldguard-check.json"}` in the closure input's `provider_reports`.
