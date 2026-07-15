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
