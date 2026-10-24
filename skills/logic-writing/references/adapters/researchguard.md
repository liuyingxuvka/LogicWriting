# ResearchGuard research and writing boundary

Use ResearchGuard for evidence discovery, argument licensing and temporal or
causal research. Preflight the selected semantic owner through the single
installed console:

| Owner | Command | Primary path |
|---|---|---|
| Research question | `researchguard status` | `primary:researchguard:status` |
| SourceGuard | `researchguard source` | `primary:researchguard:source` |
| LogicGuard | `researchguard logic` | `primary:researchguard:logic` |
| TraceGuard | `researchguard trace` | `primary:researchguard:trace` |

`scripts/provider_preflight.py researchguard` probes `researchguard status --help`.
The three member preflights remain available. Resolve the console from the
ResearchGuard distribution in the running Python, or the version-matching console
on PATH when installed elsewhere. Availability and help probes do not establish
that any native domain work ran. Missing, ambiguous, failed or timed-out consoles
stay `provider_unavailable`; do not use former packages, module commands,
checkout locators, alternate members or a non-pass retry.

## One question and one saved answer

Keep one question in a ResearchGuard research folder. `research.yaml` joins native
source, logic, trace and experiment models by shared ids. Configure the native
stop decision there, for example:

```yaml
search: {budget: 3, scope_sufficient: false}
```

After the native research work, save exactly one closure report:

```sh
researchguard status <folder> --json --output research-status.json
```

List `{"provider":"researchguard","path":"research-status.json"}` under the
closure input's `provider_reports`. Closure reads its saved `verdict`; it never
executes ResearchGuard. The five keys are `search`, `root_claim`,
`live_hypotheses`, `contested`, `errors`. Errors or a search decision other than
`stop_sufficient` prevent passing. Other live hypotheses require a real root
claim with an `assert` license; brief alternatives must agree with native live
hypotheses. `alternative_status_conflict:<id>` is a failure. `contested` contributes
`research:contested` residual risk and does not itself block the result.
A source-only question may have no root-claim license; stopping search never
turns that absence into assert wording. Keep the missing license visible.

The saved report must belong to the brief's `research_folder`. After the
folder's question, hypotheses, models or source anchors change, save the report
again; otherwise closure reports `research_report_mismatch:<field>`.

Investigation always needs this report. Academic work needs it when there are
live alternatives or the request names a research folder. Preserve native
`withhold` and `qualify` boundaries even when the reader-facing artifact passes.

## Import source-owned anchors

A brief request names `research_folder`, relative to the request JSON, pointing
to the folder or `research.yaml`. The source YAML is the index's `models.source`.
The reader imports missing anchors using native source ids, locators, summaries,
text and source boundaries. A handwritten anchor with the same id but a different
source id or locator fails `anchor_conflict:<id>`; it cannot override its owner.
For matching identities, author-written `relation`, `boundary` and
`observed_summary` remain unchanged. Import only reads files; it performs no
retrieval or provider call.

Steps: first save `researchguard status <folder> --json --output research-status.json`;
the brief request names `research_folder` and `research_status`
(`research-status.json`); the closure input's `provider_reports` lists the same
file. With `research_status`, imported anchors take their `relation` from the
report's direct directions for the root claim (`counter`, `limit`, `support`,
else `context`); without it they are `context`. A handwritten `relation` that
contradicts the research direction fails `anchor_relation_conflict:<id>`.
ResearchGuard's `references/research-tree.md` defines which evidence is direct;
LogicWriting does not recompute directions.

## Native member responsibilities

SourceGuard owns source discovery, next searches, source roles, lineage, access
constraints, anchor extraction and evidence depth. Only observed source content
with resolvable lineage can support factual statements. Preserve candidate,
planning-only, bounded, inaccessible and provider-unavailable states; never invent
retrieval work or a native result.

LogicGuard owns argument support, source-library preservation, structured-artifact
and citation semantics, model depth and an argument-ordered unit plan
(`synthesize`). Its internal library, structured-artifact, deepening and synthesis
routes remain part of the one ResearchGuard skill. It checks structural support,
not factual truth. A model or argument plan is not final prose and cannot replace
an audit of the delivered artifact. Writing tools own finished outlines,
paragraph plans and delivery.

TraceGuard owns timelines, execution/effect chains, competing causal storylines,
counterfactuals and prediction boundaries. Supply stable claims, events, actors,
sources, time clues and the bounded question. Preserve native uncertainty,
unresolved links and future/holdout limits: earlier-than is not caused-by and a
plausible mechanism is not execution evidence.

ExperimentGuard remains outside LogicWriting's provider routes; it only recommends
finite experiments in its own native domain. The retired umbrella run command is
not an execution path.

## Preserve the synthesis bridge

The stable bridge remains `researchguard.logic.synthesis-request.v1` → native
`researchguard.logic.synthesis-plan.v1` →
`assets/schemas/researchguard-logic-handoff.schema.json` → `ReaderBrief.writer_input`.
Give `scripts/build_reader_brief.py` the native plan, its opaque
`native_result_locator` and an exhaustive `native_handoff_mapping`.
`scripts/researchguard_handoff.py` checks native model/request identity, complete
body-unit order, acyclic parent/predecessor links, argument closure, source-branch
bindings and candidate dispositions. The mapping covers every native unit and
every current planned reader unit; empty, partial, unknown-unit or blocked mappings
cannot enter the writer workspace. A blocked support/budget/request result stays
blocked and never becomes a quality or final-closure pass.

Native `model_fingerprint` and `selection_request_fingerprint` are lowercase
64-character digests. Only the typed LogicWriting fields add a `sha256:` label;
`native_result_fingerprint` still hashes the exact native payload. Raw and labelled
values must be valid lowercase SHA-256 digests. Preserve ReaderIntent,
CompositionPlan and writer-projection bindings together, native payload bytes and
opaque result locators. Do not change this bridge to manufacture a pass.
