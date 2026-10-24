# ReaderBrief v2

ReaderBrief binds the exact ReaderIntent, content boundaries, whole-artifact
CompositionPlan and selected route extension. Its `writer_input` is the sanitized
projection given to the writing context. Keep internal paths, native-provider
results, raw ledgers and agent instructions in the work room.

ReaderIntent is not a topic summary. Preserve language, audience, purpose,
artifact mode/format, requested or existing structure, locked headings,
list/table policy, style, extent, citations, required/forbidden content,
reference examples and unresolved choices. Material conflicts stop drafting.

Content units carry safe meaning, evidence anchors, alternatives, limitations,
citation duties, exact-preservation duties and prohibited overclaims. They
constrain content without dictating paragraphs or supplying approved sentences.
The CompositionPlan owns the central question and throughline, opening and
conclusion jobs, hierarchy, reader-state changes, downstream relationships,
content/limitation placement, presentation mode and planned extent. Required
outline rows and content must be planned or explicitly dispositioned.

## Source-owned research anchors

A request may name `research_folder`, relative to its JSON file, as a research
folder or `research.yaml`. Its `models.source` points to native source YAML.
The builder reads it without invoking ResearchGuard. Missing anchor ids are
imported; a handwritten id with a different source id or locator fails
`anchor_conflict:<id>`. Matching author-written relation, summary and boundary
stay unchanged. Source dates, roles, uncertainty and wording authority remain
with ResearchGuard; a saved `verdict` is the single research closure report.

With `research_status` (the saved `researchguard status <folder> --json` report,
relative to the request; it needs `research_folder` and must belong to it, see
the identity codes in `closure.md`), an imported anchor takes its `relation` from
the report's `evidence[].directions` for the root claim (`verdict.root_claim.id`):
any `oppose` -> `counter`, else `limit` -> `limit`, else `support` -> `support`.
No direction, no root claim or no `research_status` gives `context`: an unknown
direction is never written as support. A handwritten `relation` may be weaker
than the research; `support` against a research `counter`, or `counter` against
a research `support`, fails `anchor_relation_conflict:<id>` and nothing is
imported. The brief records `research_status`.

The work-room brief retains the research-folder binding when supplied, so
academic closure can require that report. A content boundary is the piece's one
evidence model; it does not duplicate the research engine's source library or
licensing machinery.

## Repeated placement fields

A request may omit repeated dispositions for content already named by planned
units; the builder fills body rows in plan order. It likewise fills body
limitation dispositions from `limitation_ids`, affected content and placement.
Explicit rows remain authoritative and are checked. Unplaced content needs an
explicit disposition; deliberate omissions and hidden placements are never
inferred. Defaults are filled before fingerprints.
