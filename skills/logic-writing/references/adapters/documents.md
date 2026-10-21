# Documents adapter

Use Documents for DOCX, Word, or Google Docs reading and mutation; real tracked
changes; comments; styles and layout; document rendering; and page inspection.

Check availability with `python scripts/provider_preflight.py documents
--provider-root <skills root>/docx`; a skill named `docx` or `documents` is
accepted. Add `--require-render` when page rendering is needed.

Logic Writing supplies revision content, provenance decisions, semantic
constraints, and the artifact fingerprint. Documents owns file mutation and
visual document evidence. If its dependency loader or LibreOffice is
unavailable, return `dependency_unavailable` or `render_not_run`. Textual work
may still be boundedly deliverable, but visual-quality, layout-correctness, and
submission-ready claims remain prohibited.

The v2 automatic reader closure accepts only UTF-8 text/markdown. A projected
text pass describes that text layer only; it does not establish closure of the
original binary bytes or rendered pages. Preserve the native binary path/hash
checks and required render/visual evidence. Unfinished binary or render duties
remain explicitly bounded or partial, with `render_not_run` or
`dependency_unavailable` where applicable. The requested document-format route
remains supported; a complete binary reader bridge is a separate capability.
