# ResearchGuard provider boundary

Logic Writing uses the released ResearchGuard `0.5.1` provider and three
direct semantic member owners. ResearchGuard also has other native members,
but they are not active Logic Writing routes in this patch.
Preflight the selected owner with `scripts/provider_preflight.py`:

| Semantic owner | Console command | Primary path |
| --- | --- | --- |
| LogicGuard | `researchguard logic` | `primary:researchguard:logic` |
| SourceGuard | `researchguard source` | `primary:researchguard:source` |
| TraceGuard | `researchguard trace` | `primary:researchguard:trace` |

Resolve the console from the installed ResearchGuard distribution record, not
from ambient PATH state. The console version probe and selected member help
probe establish provider availability only. The distribution version, console
output, and supported version must all be `0.5.1`. They do not prove that
native domain work ran.

Use exactly one row per handoff. A missing or ambiguous installed console,
failed command, or timeout is `provider_unavailable`. Do not use PATH as a
second resolver, import a former member package, run a module command, supply a
checkout path, retry through another member, or reinterpret a non-pass native
result.

Keep `native_owner` equal to the selected semantic member. Bind executable
route evidence to the exact current primary path and preserve the member's own
native route and receipt fields when the member returns them as an opaque
provider-owned reference. Logic Writing may add its own binding/closure
receipt, but it must not rebuild the ResearchGuard native receipt schema.

For the LogicGuard artifact-synthesis route, the current native result is
`researchguard.logic.synthesis-plan.v1`, produced from the required
`researchguard.logic.synthesis-request.v1`. Pass that result through
`scripts/researchguard_handoff.py` before building a ReaderBrief. The handoff
copies only the ordered argument units, their closure/role bindings, source
branch ids, and complete candidate dispositions into
`researchguard-logic-handoff.schema.json`; it binds the ReaderIntent,
CompositionPlan, and writer projection fingerprints. The native result and any
native receipt remain opaque references. A blocked native status or support
gap produces a blocked handoff and cannot enter the writer projection.

ResearchGuard's native `model_fingerprint` and
`selection_request_fingerprint` are currently emitted as lowercase 64-character
digests without a `sha256:` label. The handoff adapter adds that label only in
the typed Logic Writing fields, while `native_result_fingerprint` continues to
hash the exact native payload. This is a format normalization, not a new
identity or a second provider hash; raw or already-labelled native values must
still be valid lowercase SHA-256 digests.

`experimentguard` and the `researchguard run` umbrella are explicit scope-outs
for Logic Writing `4.0.0`; they execute no provider command.

After a semantic handoff is joined to a current ReaderBrief, the adapter emits
one `researchguard.logic.consumption-binding.v1` artifact. The
`researchguard-consumption-binding.schema.json` contract requires an
exhaustive native-unit to planned-unit mapping and binds the handoff,
ReaderIntent, CompositionPlan, ReaderBrief, and writer projection fingerprints.
Use `bind_handoff_consumption` and `validate_handoff_consumption`; an empty,
partial, stale, blocked, or unknown-unit mapping cannot enter the writing
workspace.
