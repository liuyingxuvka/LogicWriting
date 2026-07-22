## Context

Logic Writing has one canonical source at `skills/logic-writing`, one maintenance unit, and eleven semantic checks declared by that target. The source is already a successful public skill, but the maintainer record predates SkillGuard's bounded evidence lifecycle and the repository's FlowGuard adoption trails the installed engine. Generated author contracts, target-native receipts, transient run directories, installed projections, Git, and releases are distinct identities and must not be conflated.

## Goals / Non-Goals

**Goals:**

- Establish one current SkillGuard 0.4.1 author contract without changing Logic Writing's native route or semantic depth.
- Freeze exact execution ownership for the eleven target-declared checks and keep reusable evidence unit-local and identity-exact.
- Bound durable evidence and remove transient/cache material from source and consumer authority.
- Produce a clean consumer projection and prove source, installation, package, Git, tag, and release parity before closure.

**Non-Goals:**

- Adding domain criteria, routes, adapters, or deeper requirements to Logic Writing.
- Making consumers depend on SkillGuard, FlowGuard author models, maintainer receipts, or the private global router.
- Sharing receipts with another maintenance unit or using a stale receipt as a fallback.

## Decisions

1. **Direct current replacement.** The 0.3.4 author identity is replaced by the current contract. A compatibility reader or dual manifest would leave two authorities and make freshness ambiguous.
2. **Target sovereignty.** The compiled contract is derived from the target's existing eleven checks. SkillGuard verifies identity, execution, evidence, freshness, and closure; it does not reinterpret the checks or decide that the target needs more depth.
3. **One durable evidence authority.** Immutable terminal producer evidence is retained through SkillGuard's bounded store. Disposable run/staging roots, logs, caches, and intermediate reports are not source authority and are removed or quarantined only after the current durable receipt and release pins exist.
4. **Affected-first, one final owner.** Development uses affected checks. After source, toolchain, and impact plan freeze, one full validation owner runs all eleven checks once. Equivalent consumers project that receipt and never re-run the owner command.
5. **Clean consumer activation.** Installation is staged and content-verified, then activated transactionally. Consumer content excludes `.skillguard`, author contracts, receipts, FlowGuard author models, caches, and release scratch data.
6. **Separate identity gates.** Source, generated contract, native evidence, installed projection, Python package, Git commit, version tag, and GitHub Release are checked separately and must agree before release closure.

## Risks / Trade-offs

- **Historical receipts may be large or ambiguous** → preserve current terminal evidence first, generate an explicit lifecycle plan, and quarantine/purge only exact non-authoritative paths after process and reference checks.
- **A generated contract may be stale after source edits** → compilation is mandatory before validation; unmapped input changes block instead of triggering a guessed run-all fallback.
- **Installed files may contain cache extras** → use a clean staged projection and transactional activation, then compare complete inventories.
- **Concurrent work may change the source snapshot** → re-check Git and coordination state before the final owner and invalidate the release gate if the frozen identity changes.

## Migration Plan

1. Record the OpenSpec and FlowGuard lifecycle boundary and upgrade the FlowGuard project record to the installed current engine.
2. Adopt SkillGuard 0.4.1 author metadata and regenerate the exact compiled contract and manifest.
3. Run affected model/contract checks, then freeze the final owner plan and execute all eleven target-native checks once.
4. Materialize and verify a clean consumer projection; activate it and verify installed currentness without launching validation.
5. Create current durable evidence/pins, apply the bounded lifecycle to exact obsolete run/cache material, and prove protected business/source files were untouched.
6. Bump the repository version, update public release documentation, commit, push, tag, and publish a source-only GitHub Release.
7. Archive the OpenSpec change only after implementation and post-snapshot release verification are current.

Rollback is release-level: before tag publication, restore the previous clean consumer projection if activation fails. After publication, issue a new correcting release; do not reintroduce the retired author authority.
