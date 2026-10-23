# ReaderBrief v2

ReaderBrief is the sanitized handoff from content authority to the selected
final writer. It preserves the exact `ReaderIntent`, terminal deliverable,
content boundaries, whole-artifact `CompositionPlan`, and the selected route
extension.

`ReaderIntent` is not a topic summary. It keeps language, audience, purpose,
artifact mode and format, requested or existing structure, locked headings,
list/table policy, style, extent, citations, required and forbidden content,
reference examples, and unresolved choices. Material conflicts stop drafting.

Content units carry safe meaning, evidence anchors, alternatives, limitations,
citation duties, exact-preservation duties, and prohibited overclaims. These
fields control what may be said; they do not dictate paragraph order or provide
approved sentences to copy.

The `CompositionPlan` controls how the whole artifact works: central question
and throughline, opening and conclusion jobs, hierarchy, reader-state changes,
unit relationships, downstream consumers, content and limitation placement,
presentation mode, and target extent. Every required outline row and content
unit must be planned or explicitly dispositioned.

The brief excludes Guard names, raw ledgers, agent instructions, and status
prose from the reader artifact. Keep those in the audit output.

### Repeated placement fields

A brief request may omit content dispositions for content already named by planned units; the builder fills `body` rows in plan order. It likewise fills body limitation dispositions from `limitation_ids` and the native limitation's affected content and placement. Explicit rows remain authoritative and are checked. Unplaced content requires an explicit disposition; hidden dispositions are never inferred. Defaults are filled once, before fingerprints.
