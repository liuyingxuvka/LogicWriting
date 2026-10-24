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

## Bind with quotations

Prefer `anchor_excerpts: ["a unique passage of at least twelve characters"]`
in each binding instead of `artifact_unit_ids` and `artifact_spans`. On every
request, exact quotes resolve against visible current units. No match fails;
several matching units require a longer quote. A quote can follow a moved or
renumbered paragraph. If IDs are also supplied they must agree; supplied spans
still undergo normal freshness checks. Old ID-only requests remain supported.

`python scripts/show_plan.py --input show-request.json` displays the question,
throughline, every planned unit's job and reader states, content and limitations,
and the first sentence of its bound text. Read a brief request or
`reader-brief.json` directly before drafting; units without current text bindings
appear as `UNBOUND`. Later chain JSON files can use the `reader-brief.json` beside
them, or a request can name `reader_brief`, `artifact_map` and `shared_writing`
explicitly. `--json` prints the same tree as JSON. Where a complete map and
binding are supplied, unknown planned-unit ids fail `unit_not_in_plan`; stale or
missing references are not silently omitted. The view does not repair or rewrite
supplied records.

## Native world references

When the route requires a world check, provide `world_contract`. Bind relevant
planned units or current text using `world_refs` that resolve to its objects,
events and conditions. Unknown ids fail `unknown_world_ref`; an unquoted reference
stays a visible `world_ref_unquoted:...` risk. Resolving a reference is not a
WorldGuard pass and never replaces its saved native report.
