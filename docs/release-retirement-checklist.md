# Release and Predecessor-Retirement Checklist

> **This is a checklist, not a completion record.** An unchecked or listed
> item does not mean it has been run. The document makes no claim that Logic
> Writing has been published, installed, fully validated, or that either
> predecessor repository has been deleted.

Use one evidence record for the exact source snapshot and external state being
changed. Do not convert progress messages, plans, or still-running processes
into completion evidence.

## 1. Freeze the intended public contract

- [ ] Confirm the public name is **Logic Writing** and the skill id is
  `logic-writing`.
- [ ] Confirm `$logic-writing` is the only public invocation.
- [ ] Confirm the terminal deliverable selects exactly one final owner:
  `investigation` or `academic-writing`.
- [ ] Confirm bounded academic-to-investigation work returns only the requested
  `ResearchPacket` slice and cannot close the academic artifact.
- [ ] Confirm SourceGuard, LogicGuard, TraceGuard, FlowGuard, Documents, and PDF
  retain their native responsibilities.
- [ ] Confirm no predecessor alias, forwarding shim, fallback, alternate
  manifest, or automatic receipt migration remains.
- [ ] Reconcile the change specification, implementation tasks, and public docs
  against the same contract.

## 2. Freeze source and validation ownership

- [ ] Freeze the exact governed source, model, schema, test, and tool identities
  for the candidate snapshot.
- [ ] Map each affected source component to its exact validation owner.
- [ ] Assign exactly one primary execution owner to each check and to the final
  full validation.
- [ ] Reuse only immutable terminal-success evidence whose input identity still
  matches; do not reuse stale or partial results.
- [ ] Do not use a still-running background process, scheduled task, unattended
  retry, or progress log as final validation evidence.
- [ ] After an interruption or timeout, confirm the complete descendant process
  tree has ended before accepting evidence or starting another owner.

## 3. Run source and contract checks

- [ ] Run installable-skill static validation.
- [ ] Run schema, route, adapter, fingerprint, stale-propagation, closure, and
  no-progress tests affected by the final snapshot.
- [ ] Run `ResearchPacket`, `ReaderBrief`, actual-artifact audit, and reader
  judgment boundary tests.
- [ ] Run investigation and academic-writing route regression scenarios,
  including bounded child work and provider-unavailable states.
- [ ] Run specialist integration contract checks without replacing the native
  specialist owners.
- [ ] Run the repository privacy scanner and review public prose semantically.
- [ ] Review English and Chinese README copies for factual equivalence.
- [ ] Confirm no private user artifacts, source material, credentials,
  machine-specific paths, or recovery archives are tracked.
- [ ] Record every skipped, blocked, stale, or unavailable check with its claim
  boundary.

Available portable commands include:

```sh
python scripts/validate_skill.py --skill-root skills/logic-writing --json
python scripts/check_privacy.py --root . --json
python -m pytest -q
```

Their presence is not evidence that they passed for a given snapshot.

## 4. Final stable-snapshot validation

- [ ] Freeze the final source and tool identities before starting.
- [ ] Run one full validation under the declared primary execution owner.
- [ ] Confirm model checks, test results, and generated receipts refer to the
  same frozen snapshot.
- [ ] Inspect counterexamples and failures; repair the source or narrow the
  claim rather than weakening an invariant.
- [ ] If the final source changes, invalidate the affected evidence and repeat
  only the required owners before a new final full run.
- [ ] Produce a final validation summary that distinguishes passed, failed,
  blocked, stale, not-run, and unavailable evidence.

## 5. Installation cutover

- [ ] Install `skills/logic-writing` into a clean target.
- [ ] Verify the installed copy matches the frozen installation projection.
- [ ] Confirm required specialist providers are separately discoverable.
- [ ] Invoke one representative investigation request and inspect the selected
  final owner, evidence handoff, reader-facing output, and failure boundaries.
- [ ] Invoke one representative academic-writing request with a bounded
  evidence gap and confirm the academic route keeps final ownership.
- [ ] Confirm internal Guard names, route ids, ledgers, and agent instructions
  do not leak into ordinary final prose.
- [ ] Update active registries, instructions, examples, and automations to call
  `$logic-writing` directly.

## 6. Publish LogicWriting

- [ ] Confirm the public repository boundary and license.
- [ ] Confirm README install commands match the actual source layout.
- [ ] Confirm the source version, changelog wording, intended tag, and intended
  release notes agree without claiming unverified state.
- [ ] Create and inspect the intended Git history and remote configuration.
- [ ] Push the exact validated snapshot to the `LogicWriting` repository.
- [ ] Verify the hosted default branch and public files directly.
- [ ] Test a fresh checkout and source-copy installation from the hosted
  repository.
- [ ] Only then create and verify any intended tag or hosted release.

## 7. Prove zero active predecessor dependence

- [ ] Search active skill registries, prompts, docs, examples, automations, and
  installed skill directories for `research-investigation-workflow`.
- [ ] Search the same surfaces for `academic-thesis-revision-workflow`.
- [ ] Classify every match as an intentional migration-history reference or an
  active dependency; resolve all active dependencies.
- [ ] Confirm no compatibility alias, fallback, dual manifest, or alternate
  success route remains.
- [ ] Confirm predecessor runtime receipts are not accepted as current Logic
  Writing evidence.

Historical names may remain in this migration guide and checklist because they
identify what is being retired. They must not remain as callable authorities.

## 8. Prepare irreversible retirement

- [ ] Capture a separately stored, verified recovery copy for each predecessor
  repository before deletion.
- [ ] Verify each recovery copy can reconstruct the intended Git history and
  public repository content without credentials or private runtime material.
- [ ] Record who owns recovery and where its verification evidence is kept;
  keep those details outside the public repository.
- [ ] Confirm maintainers understand that hosted repository deletion has no
  automatic rollback.
- [ ] Confirm LogicWriting remains healthy and reachable immediately before the
  first deletion.

## 9. Retire predecessors in sequence

- [ ] Remove the installed `research-investigation-workflow` skill after the
  clean cutover check.
- [ ] Delete the hosted `research-investigation-workflow` repository only after
  verifying the recovery copy and current LogicWriting health.
- [ ] Recheck LogicWriting hosting, installation, both routes, and public docs.
- [ ] Stop retirement if that health check fails.
- [ ] Remove the installed `academic-thesis-revision-workflow` skill after the
  second clean cutover check.
- [ ] Delete the hosted `academic-thesis-revision-workflow` repository only
  after verifying its recovery copy and current LogicWriting health.
- [ ] Recheck LogicWriting hosting, installation, both routes, and public docs
  again.

Do not describe either predecessor as deleted until the hosted state has been
checked directly after the deletion operation.

## 10. Close the release and retirement record

- [ ] Record the exact LogicWriting commit, tag or release when applicable,
  installed projection identity, validation summary, and hosted verification.
- [ ] Record the two predecessor deletion results separately.
- [ ] Record residual risks, unavailable external providers, and any checks
  that remain bounded.
- [ ] Re-run the public privacy scan on the final tracked snapshot.
- [ ] Verify that public documentation contains no private recovery location,
  maintainer credential, personal machine path, or user artifact.
- [ ] Preserve the evidence record outside the public repository when it
  contains operational or recovery details.

Completion means every required item has current evidence or a clearly bounded
non-pass disposition. The checklist itself is never proof of completion.
