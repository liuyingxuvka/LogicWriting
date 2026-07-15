# Contributing to Logic Writing

Contributions should strengthen the single public entrypoint without turning
Logic Writing into a duplicate implementation of its specialist skills.

## Design contract

Every change should preserve these boundaries:

1. `$logic-writing` remains the only public skill invocation.
2. Route selection produces exactly one final owner from the terminal
   deliverable: `investigation` or `academic-writing`.
3. An academic route may request bounded investigation work but keeps final
   ownership of the academic artifact.
4. SourceGuard, LogicGuard, TraceGuard, FlowGuard, Documents, and PDF retain
   their native domain decisions and native evidence.
5. `ResearchPacket` remains the default evidence handoff between routes.
6. `ReaderBrief` contains reader needs and safe content, not internal workflow
   vocabulary or agent instructions.
7. Closure is based on the current delivered artifact and current evidence,
   not caller-authored status labels.
8. A missing provider or skipped check remains visible; it is never rewritten
   as success.

See [docs/architecture.md](docs/architecture.md) and
[docs/responsibility-map.md](docs/responsibility-map.md) before changing a
route, adapter, schema, or closure rule.

## Development setup

- Use Python 3.10 or newer.
- Work from a source checkout.
- Keep specialist providers separately installed and configured when a test
  truly requires them.
- Do not create local mock implementations and describe them as native
  specialist execution.

Repository-level documentation belongs at the repository root or under
`docs/`. Only installable runtime material belongs under
`skills/logic-writing/`.

## Change workflow

1. State the observable behavior or contract that should change.
2. Identify the owning route, schema, adapter, or evidence domain.
3. Update the smallest set of source and tests that owns that behavior.
4. Re-run only affected checks while the change is still moving.
5. Freeze source and tool identities before the final full validation owner
   runs.
6. Review the public diff for unsupported maturity, release, installation, and
   retirement claims.
7. Run the semantic privacy gate before proposing publication.

Do not make a report, receipt, or generated progress file a source-authority
input unless the contract explicitly declares that dependency.

## Validation entrypoints

The repository provides these contributor commands:

```sh
python scripts/validate_skill.py --skill-root skills/logic-writing --json
python scripts/check_privacy.py --root . --json
python -m pytest -q
```

Run them against the current checkout. A command listed in this document is an
available check, not evidence that it has passed. When a check is skipped,
blocked, interrupted, or stale, report that state and the affected claim.

Model or multi-skill regression runs need one declared execution owner and a
frozen input identity. Do not accept a still-running background process,
progress message, or duplicated run as terminal evidence. If a launcher is
interrupted, confirm that its process tree has ended before starting a new
owner.

## Test expectations

Add or update focused tests for changes to:

- route selection and the one-final-owner invariant;
- bounded academic-to-investigation handoff;
- schemas, fingerprints, manifests, and stale propagation;
- provider availability and typed degraded states;
- `ResearchPacket` and `ReaderBrief` boundary enforcement;
- actual-artifact diagnostics and reader judgment separation;
- closure strength and no-progress behavior;
- public privacy and installable-skill boundaries.

Do not weaken an invariant merely to make a fixture pass. If the intended
behavior changed, update its contract, implementation, test, and public
explanation together.

## Writing and documentation expectations

Public documentation should:

- explain the reader's problem before internal mechanics;
- use ordinary language and define unavoidable terms;
- distinguish current source facts from planned release or retirement state;
- avoid guarantees such as “complete,” “stable,” “publication-ready,” or
  “fully validated” unless current evidence licenses the exact claim;
- keep the English README and Chinese mirror factually aligned;
- use neutral examples that reveal no private project, person, or case.

## Public repository boundary

Do not commit:

- credentials, tokens, private keys, or private provider configuration;
- personal machine paths, usernames, or environment-specific import paths;
- user papers, reports, source libraries, or customer material;
- private case labels, internal work histories, or recovery archives;
- generated runtime evidence that exposes local context.

Public-safe source, schemas, neutral fixtures, tests, and documentation are in
scope. If a realistic example cannot be made anonymous without losing its
purpose, do not publish it.

## Pull-request description

Describe:

- the problem and affected owner;
- the public behavior before and after the change;
- changed contracts, schemas, and evidence domains;
- checks run, with exact status;
- checks not run and why;
- residual risk and claim boundary;
- privacy review result;
- migration or retirement impact, if any.

Do not describe publication, installation, repository privatization, or
repository deletion as complete until the corresponding external state has
been checked directly. An anonymous 404 for a private repository is not a
deletion receipt.
