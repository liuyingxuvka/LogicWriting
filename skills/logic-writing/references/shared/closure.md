# Reader closure v2

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
judgment all to pass. Any defect produces a typed repair request for actual
units and preservation duties. After real new bytes exist, rebuild every
dependent record.

Repeated closure calls do not demonstrate work. `no_progress_blocked` requires
two consecutive current repair results with the same lineage and remaining
defect identity, a chained input/output artifact identity, and no actual
progress. It then hands the artifact to human review instead of looping.
