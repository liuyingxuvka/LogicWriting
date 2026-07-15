# Documents adapter

Use Documents for DOCX, Word, or Google Docs reading and mutation; real tracked
changes; comments; styles and layout; document rendering; and page inspection.

Logic Writing supplies revision content, provenance decisions, semantic
constraints, and the artifact fingerprint. Documents owns file mutation and
visual document evidence. If its dependency loader or LibreOffice is
unavailable, return `dependency_unavailable` or `render_not_run`. Textual work
may still be boundedly deliverable, but visual-quality, layout-correctness, and
submission-ready claims remain prohibited.
