# ResearchGuard provider boundary

Logic Writing uses the released ResearchGuard `0.4.11` provider and three
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
output, and supported version must all be `0.4.11`. They do not prove that
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

`experimentguard` and the `researchguard run` umbrella are explicit scope-outs
for Logic Writing `3.0.2`; they execute no provider command.
