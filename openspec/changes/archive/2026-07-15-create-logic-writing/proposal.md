## Why

The two predecessor skills split one real user journey across separate entrypoints and duplicate orchestration rules, yet both can still produce shallow research, internal AI jargon, weak handoffs, and completion claims that are not tied to the latest sources or artifact. A single reader-centered orchestration skill is needed now so investigation and academic writing reinforce each other while the existing Guard tools retain their specialist authority.

## What Changes

- Add one public Codex skill named **Logic Writing** with skill id `logic-writing` and two internal routes: `investigation` and `academic-writing`.
- Keep Logic Writing as a thin upper shell: it selects routes, coordinates handoffs, compiles a reader brief, writes or revises reader-facing prose, and derives final wording from current specialist receipts.
- Bind source discovery to SourceGuard, argument modeling and artifact planning to LogicGuard, temporal/causal reconstruction to TraceGuard, process freshness and closure to FlowGuard, DOCX work to Documents, and PDF work to PDF.
- Add a typed `ResearchPacket` handoff so investigation results can feed academic writing without copying hidden state or promoting candidates into facts.
- Add explicit reader-language gates that reject internal workflow labels, ledger dumps, unsupported certainty, unexplained acronyms, weak transitions, and paragraph sequences with no visible conceptual progression.
- Add content-addressed source, artifact, adapter, and validation receipts with automatic staleness propagation and honest terminal states.
- Add current OpenSpec, FlowGuard, and SkillGuard governance, adversarial fixtures, end-to-end route tests, installation verification, bilingual public documentation, an immutable initial `v1.0.0`, and a source-only `v1.0.1` repair release.
- **BREAKING**: replace `academic-thesis-revision-workflow` and `research-investigation-workflow` as user-facing entrypoints; after verified installation and release, remove both old installed skills and move both old GitHub repositories out of the public surface by changing them to private. The authenticated owner keeps access, anonymous API access must return 404, and the user owns any later irreversible deletion. Recoverable Git bundles and uncommitted patches remain outside the public repository.

## Capabilities

### New Capabilities

- `unified-routing`: Select exactly one final-owner route, invoke only the required specialist adapters, and prevent ownership loops or hidden fallback engines.
- `investigation-route`: Run deep, gap-driven investigation from question framing through source discovery, trace analysis, argument adjudication, and a reader-ready report or a bounded research handoff.
- `academic-writing-route`: Create or revise papers, theses, literature reviews, and related DOCX/PDF artifacts while preserving structure, source support, authorial continuity, and visible revision boundaries.
- `reader-facing-synthesis`: Compile internal evidence into natural, coherent prose for a declared reader, language, genre, and length without leaking AI-internal terminology.
- `evidence-freshness-closure`: Validate typed handoffs, track exact input identities, propagate staleness after source or artifact changes, and derive terminal claims only from current owner receipts.

### Modified Capabilities

None. This is a new repository with no prior OpenSpec capability authority.

## Impact

- New repository: `liuyingxuvka/LogicWriting`.
- New installed skill: `$CODEX_HOME/skills/logic-writing`.
- Dependencies remain external and authoritative: SourceGuard, LogicGuard and its satellites, TraceGuard, FlowGuard, Documents, and PDF.
- Global SkillGuard routing will move from two blocked predecessor entries to one current `logic-writing` entry.
- Existing references in installed Guard skill documentation that point to the academic predecessor must be updated to the new upper route after installation.
- GitHub visibility retirement is state-changing but reversible before deletion; it occurs only after backup verification, clean release publication, fresh-clone validation, installation parity, and route smoke tests succeed. An anonymous 404 is recorded as privacy evidence, never as a deletion receipt. Final repository deletion is an explicit user-owned follow-up outside this change's execution scope.
