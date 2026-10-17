# PDF adapter

Use PDF for extraction, PDF creation, page rendering, and visual inspection.
Bind every receipt to the exact PDF fingerprint and distinguish:

- text/content extraction;
- structural parsing;
- render success;
- page-level visual inspection.

One class cannot stand in for another. Extracted text does not prove layout,
and a rendered page does not prove semantic source fit. Missing providers stay
`dependency_unavailable` or `render_not_run`.

The v2 automatic reader closure accepts only UTF-8 text/markdown. A projected
text pass describes that text layer only; it does not establish closure of the
original binary bytes or rendered pages. Preserve the native binary path/hash
checks and required render/visual evidence. Unfinished binary or render duties
remain explicitly bounded or partial, with `render_not_run` or
`dependency_unavailable` where applicable. The requested document-format route
remains supported; a complete binary reader bridge is a separate capability.
