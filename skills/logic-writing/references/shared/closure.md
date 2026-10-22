# Reader closure v2

The executable v2 reader closure covers UTF-8 text/markdown. A text projection
does not establish closure of its source DOCX/PDF or rendered pages; preserve
native Documents/PDF evidence and explicit unresolved binary/render boundaries.

Closure accepts only one complete current identity chain:

`WritingRequest -> ReaderIntent -> RouteDecision -> CompositionPlan -> selected
route composition -> ReaderBrief -> ArtifactMap -> SharedWriting ->
deterministic audit -> route artifact review -> ReaderJudgment (judge_kind) ->
conditional revision provenance -> closure`

All byte-bound records must identify the same current artifact. All
intent-bound records must identify the same ReaderIntent and CompositionPlan.
Only the selected final route may close the artifact; bounded investigation
children never inherit final ownership.

Creation records revision provenance as explicitly `not_applicable`. Revision
records it as required and accounts for source-unit treatments. Neither case
may omit the field or infer applicability from the final owner.

A pass requires the deterministic audit, route review, and reader judgment all
to pass; otherwise closure is `needs_repair`. A broad claim additionally requires
`judge_kind: independent_context`, with different producer and judge IDs. After real new bytes
exist, rebuild every dependent record.

The route review and the eight reader dimensions may be assessed together by
one reader that did not write the text (a fresh sub-agent or a separate
session). Preserve both results, all route dimensions, the reverse outline and
the quoted actual spans. If no separate context is available, self-review is
allowed with `"judge_kind": "self_review"` in the judgment. Closure records that
kind and an explicit self-review risk; even a passing self-review never allows
a broad claim. Self-review may use the same or different IDs, without claiming
to verify who actually wrote the judgment. A
caller-authored `verified` marker does not license pass.

If the audit or the reader judgment reports defects, revise the actual text,
rebuild the ArtifactMap and rerun the audit and the read. If a revision round
fixes none of the reported defects, stop and return the artifact with the audit
note. Repeated closure calls do not demonstrate work.
