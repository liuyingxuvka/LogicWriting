# ResearchGuard provider boundary

Logic Writing uses ResearchGuard (minimum version checked by
`scripts/provider_preflight.py`) and three
direct semantic member owners. ResearchGuard also has other native members,
but they are not active Logic Writing routes in this patch.
Preflight the selected owner with `scripts/provider_preflight.py`:

| Semantic owner | Console command | Primary path |
| --- | --- | --- |
| LogicGuard | `researchguard logic` | `primary:researchguard:logic` |
| SourceGuard | `researchguard source` | `primary:researchguard:source` |
| TraceGuard | `researchguard trace` | `primary:researchguard:trace` |

Resolve the console from the ResearchGuard distribution installed in the
running Python; when ResearchGuard is installed in another environment (pipx or
a separate venv), use the `researchguard` command on PATH. The console version
probe and selected member help probe establish provider availability only. The
console version must meet the minimum and, when the running Python has the
distribution, match it. They do not prove that native domain work ran.

Use exactly one row per handoff. A missing or ambiguous installed console,
failed command, or timeout is `provider_unavailable`. Do not import a former
member package, run a module command, supply a checkout path, retry through
another member, or reinterpret a non-pass native result.

Keep the selected member's own route and status unchanged; Logic Writing never
rewrites a member result.

For the LogicGuard artifact-synthesis route, the current native result is
`researchguard.logic.synthesis-plan.v1`, produced from the required
`researchguard.logic.synthesis-request.v1`. Pass that result through
`scripts/researchguard_handoff.py` before building a ReaderBrief. The handoff
copies only the ordered argument units, their closure/role bindings, source
branch ids, and complete candidate dispositions into
`assets/schemas/researchguard-logic-handoff.schema.json`; it binds the ReaderIntent,
CompositionPlan, and writer projection fingerprints. The native result remains
an opaque reference. A blocked native status or support
gap produces a blocked handoff and cannot enter the writer projection.

ResearchGuard's native `model_fingerprint` and
`selection_request_fingerprint` are currently emitted as lowercase 64-character
digests without a `sha256:` label. The handoff adapter adds that label only in
the typed Logic Writing fields, while `native_result_fingerprint` continues to
hash the exact native payload. This is a format normalization, not a new
identity or a second provider hash; raw or already-labelled native values must
still be valid lowercase SHA-256 digests.

`experimentguard` and the `researchguard run` umbrella are explicit scope-outs
for Logic Writing; they execute no provider command.

`scripts/build_reader_brief.py` takes the semantic handoff as `native_handoff`
with a `native_handoff_mapping` that maps every native unit to planned units
and covers every planned unit; an empty, partial, blocked, or unknown-unit
mapping cannot enter the writing workspace.
