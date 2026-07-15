# Migrating to Logic Writing

This document describes the intended cutover from the two former public skill
entrypoints to Logic Writing. It is a migration guide, not a record that an
installation, hosted repository, or predecessor retirement has already been
completed.

## What changes

Logic Writing provides one public invocation and keeps the former domains as
two internal routes.

| Former public skill or repository | New invocation | Internal route | Final responsibility |
| --- | --- | --- | --- |
| `research-investigation-workflow` | `$logic-writing` | `investigation` | Research report, briefing, evidence package, decision note, or investigated answer |
| `academic-thesis-revision-workflow` | `$logic-writing` | `academic-writing` | Paper, thesis or dissertation unit, literature review, proposal, or substantive academic revision |

The final route is selected from the requested terminal deliverable. An
academic route may open a bounded investigation child for one evidence gap; it
does not transfer ownership of the academic artifact.

## No compatibility layer

The predecessor ids are not aliases, forwarding shims, fallbacks, or alternate
entrypoints for Logic Writing. A current installation should contain the new
skill and update active instructions to invoke `$logic-writing` directly.

There is no automatic conversion of predecessor runtime ledgers or receipts.
An existing paper, source file, or research note may still be supplied as
ordinary user input, but Logic Writing must establish current source,
fingerprint, route, and audit evidence for the new run. Historical status
records do not become current authority merely because their content looks
similar.

## Version meaning

Logic Writing begins a clean `1.0.0` source version line. It does not continue
either predecessor's version sequence. The source version is not, by itself,
evidence of a hosted release or successful installation.

## Recommended cutover sequence

1. Inventory active prompts, skill registries, documentation, automations, and
   local installations that still name either predecessor.
2. Install `skills/logic-writing` into a fresh target using the source-copy
   method in [README.md](README.md).
3. Confirm that the required specialist skills are separately available.
4. Exercise one representative investigation request and one representative
   academic-writing request. Inspect the selected final owner, bounded child
   behavior, evidence handoff, plain-language output, and current failure
   states; do not infer success from invocation alone.
5. Update active instructions to call `$logic-writing`. Do not add an alias for
   either predecessor.
6. Search the active installation and public documentation for predecessor
   references. Resolve each remaining reference deliberately.
7. Run the repository's current validation plan on a frozen source snapshot.
8. Only after the new entrypoint and its recovery material have been verified,
   remove predecessor installations, move both predecessor repositories to
   private visibility in sequence, and hand any later deletion to the user.

The detailed sequence and evidence fields are in
[docs/release-retirement-checklist.md](docs/release-retirement-checklist.md).

## Existing work products

| Existing item | Treatment after migration |
| --- | --- |
| Paper, thesis, report, or source document | Supply it as current user input and fingerprint it again |
| Concrete source material | Preserve or re-import it through the current source-library route |
| Old outline or plan | Treat it as editable material, not proof of current support or quality |
| Old receipt, ledger, progress log, or self-reported pass | Historical context only; rebuild current evidence |
| Machine-specific provider path or credential | Do not copy it into the repository; configure the provider locally |

## Retirement boundary

Removing an active local skill or changing a hosted repository to private is a
separate, state-changing operation. Do it only after the cutover checks have
current evidence. A private repository should remain visible to the
authenticated owner while returning 404 to anonymous API requests; that 404
is privacy evidence, not deletion evidence.

Final repository deletion is a separate user-owned action and has no automatic
rollback. Logic Writing's retirement workflow ends after both repositories are
private, their Git identities remain recoverable, and the deletion handoff has
been recorded.

Maintainer recovery would require recreating the repository from separately
verified backup material. That recovery material is not shipped in this public
repository and must not contain credentials, private user artifacts, or
machine-specific configuration.
