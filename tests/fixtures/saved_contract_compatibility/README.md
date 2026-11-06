# Small saved-contract compatibility inputs

`single_report/` is an unchanged copy of the released heater fixture at
`ada2fd96490ec1bc2c82bce67b7ff9cac846713b` (4.3.1) and
`97c0738fd4a4b6871cef3bb1fbd31670736197b5` (4.3.2):
`tests/fixtures/claim_readings/originals/heater/`. The report, question, audit and
snapshot bytes are identical at both commits. One copy serves both releases.
The compatibility test checks the existing single-report `pg:<row-id>` use and
actual stale-input refusal. It does not claim a new PhysicsGuard execution or a
new entity binding for these legacy scalar rows.

`v3.0.2-reader-brief.json` was generated for this regression using the exact
released source `bd634b7` and its original `tests/v2_support.py:make_reader_chain`
protocol fixture. The historical production builder and historical schema
accepted it before freezing. It is a historical format example, not a saved
independent review or writing-quality result. Its original required-field shape
lacks writer_input and request; the current schema must reject it without
inventing fields or verification. MIGRATION.md gives the rebuild path from real
request, plan and source material.

`v4.3.2-reader-brief.json` is a positive format control generated with that
released production builder and its protocol fixture; current schema validation
must keep accepting it without rewriting it or producing a new quality verdict.

`provenance.json` pins the original commits, paths and exact file digests. No
application, old runtime copy, automatic converter or validation ledger is added.
