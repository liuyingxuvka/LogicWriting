# ResearchPacket

A ResearchPacket is the only default evidence handoff between routes. It binds:

- route decision and request fingerprint;
- exact SourceRegistry and ClaimSupport manifests;
- important claims and numbers;
- supporting, limiting, and counter-evidence;
- alternatives, confounders, lineages, and independence status;
- execution, effect, causal, or forecast chains when applicable;
- unresolved gaps and access failures;
- safe wording and prohibited overclaims;
- current native receipt ids and fingerprints;
- packet status and packet fingerprint.

Status is verifier-derived. Every manifest member must exist and match its
fingerprint. Candidates, search plans, progress logs, outlines, and caller
status fields cannot satisfy evidence obligations. A receiver checks the exact
packet fingerprint and requested `gap_id` before use.
