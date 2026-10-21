# Reader closure v2

The executable v2 reader closure covers UTF-8 text/markdown. A text projection
does not establish closure of its source DOCX/PDF or rendered pages; preserve
native Documents/PDF evidence and explicit unresolved binary/render boundaries.

Closure accepts only one complete current identity chain:

`WritingRequest -> ReaderIntent -> RouteDecision -> CompositionPlan -> selected
route composition -> ReaderBrief -> ArtifactMap -> SharedWriting ->
deterministic audit -> route artifact review -> independent ReaderJudgment ->
conditional revision provenance -> closure`

All byte-bound records must identify the same current artifact. All
intent-bound records must identify the same ReaderIntent and CompositionPlan.
Only the selected final route may close the artifact; bounded investigation
children never inherit final ownership.

Creation records revision provenance as explicitly `not_applicable`. Revision
records it as required and accounts for source-unit treatments. Neither case
may omit the field or infer applicability from the final owner.

A pass requires the deterministic audit, route review, and independent
judgment all to pass; otherwise closure is `needs_repair`. After real new bytes
exist, rebuild every dependent record.

The route review and the eight reader dimensions may be assessed together by
one reader that did not write the text (a fresh sub-agent or a separate
session). Preserve both results, all route dimensions, the reverse outline and
the quoted actual spans. If no separate context is available, self-review is
allowed but must be reported as self-review in the audit note. A
caller-authored `verified` marker does not license pass.

If the audit or the independent read reports defects, revise the actual text,
rebuild the ArtifactMap and rerun the audit and the read. If a revision round
fixes none of the reported defects, stop and return the artifact with the audit
note. Repeated closure calls do not demonstrate work.
