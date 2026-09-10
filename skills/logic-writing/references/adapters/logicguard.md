# LogicGuard adapter

LogicGuard owns source-library preservation, argument licensing, structured
artifact review, citation semantics, model depth, and artifact synthesis.

Invoke the semantic owner through `researchguard logic`. Choose one internal
LogicGuard route when clear:

- source library for concrete source intake and reuse;
- structured artifact for papers, sections, pages, and paragraph hierarchy;
- model deepening for important shallow nodes;
- artifact synthesis for story plans and paragraph blueprints;
- main LogicGuard route for mixed or ambiguous argument work.

These five capabilities are internal LogicGuard routes. They are not separate
installed skills or alternate execution paths. Bind the provider handoff to
`primary:researchguard:logic`; a failed route remains visible and is not retried
through another member.

LogicGuard checks structural support, not factual truth. Its model or story plan
is not final prose and cannot satisfy an audit of the actual delivered artifact.
The current provider identity is ResearchGuard `0.5.1`; preserve its native
result and receipt as an opaque reference rather than fabricating a local
LogicGuard-native receipt.

The artifact-synthesis handoff has one current typed bridge:
`researchguard.logic.synthesis-plan.v1` →
`assets/schemas/researchguard-logic-handoff.schema.json` → `ReaderBrief.writer_input`.
`scripts/researchguard_handoff.py` verifies the native model/request identity,
body-unit order, predecessor order, argument closure, and candidate
dispositions before it emits the reader projection. The bridge preserves
`reader_intent_fingerprint`, `composition_plan_fingerprint`, and
`writer_input_fingerprint` together with opaque native result/receipt
locators. It does not turn a native handoff into a quality or final-closure
pass; `blocked_support_gap`, `blocked_budget`, `blocked_invalid_request`,
stale identity, or missing provider evidence remain non-passing.
The parent hierarchy is closed before this bridge is emitted: parent links and
predecessor links must resolve to known units and contain no cycles. The
consumer binding must also cover every current planned unit, so a mapping that
mentions every native unit but leaves a reader unit unreachable is rejected.
