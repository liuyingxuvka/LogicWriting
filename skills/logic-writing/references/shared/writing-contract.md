# SharedWriting v2

SharedWriting records the author's plan-to-text declarations against exact
current bytes. The semantic review checks what those bindings mean using
quotations from the text.

For every required planned unit, record the actual artifact units and locators,
content units, model rows, selected-route surfaces, and current span
fingerprints. Required content that is not bound must have an explicit blocked
or omitted disposition; silence is not coverage.

The shared kernel owns only route-neutral composition and byte identity.
Investigation retains evidence strength and conclusion scope; academic writing
retains research contribution, hierarchy, citations, and provenance; fiction
retains story movement, resistance, continuity, voice, promises, and reveals;
travel retains traveler fit, feasibility, local texture, risk, fallback, source
boundaries, and recheck duties.

Write the whole artifact before judging it. Paragraph boundaries follow the
reader's changing understanding, not the count of findings or model nodes.
Prose-required zones cannot be realized as bullet cards. A generic phrase such
as “this leads to the next section” does not create a missing dependency.

Any byte change invalidates the ArtifactMap and every dependent span,
SharedWriting binding, review, judgment, and closure.

Before filling fingerprints, the scripts check all binding and review-evidence
unit references against the current ArtifactMap. A missing unit error names its
binding or review evidence and the current map range; it does not rebind by
position or rewrite a supplied locator or excerpt.

## Quoted boundary review

Supply `reader_brief` and `shared_writing` to the route review. Each body/note
limitation needs a `limitation_checks` row (`limitation_id`, `status`, `evidence`):
`present` requires a quote in its destination planned unit's bound body units;
`adjacent_unit` also allows the immediately preceding or following body unit.
A `missing` limitation forces repair. Each prohibited overclaim needs an
`overclaim_checks` row: `absent` has no evidence; `present` quotes current body
text and forces repair. Missing or duplicate rows are errors. Update review
status and required repairs accordingly. Optional `forbidden_patterns` are
case-insensitive regular expressions checked by audit as `overclaim_pattern`.
`binding_declared` checks declared bindings, while quoted review checks their
meaning. Audit does not decide whether a fact is true.
