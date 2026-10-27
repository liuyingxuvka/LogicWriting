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

The saved report's `input_digests` must match the current `research_folder`.
After an input file changes, save the report again; otherwise closure reports
`research_report_stale:<path>`. Closure compares raw hashes and does not parse research YAML.

Investigation always needs this report. Academic work needs it when there are
live alternatives or the request names a research folder. Preserve native
`withhold` and `qualify` boundaries even when the reader-facing artifact passes.

## Import source-owned anchors

A request with `research_folder` must also name `research_status`. First save a fresh
native report with the command above. Anchor imports read only its `evidence` rows:
`anchor`, `source`, `locator`, `summary`, `boundary` and native `directions`.
Logic Writing compares raw input digests before importing; it never parses the native
research or source YAML. Empty report boundaries keep the scoped default “Use only
what the quoted passage says.” Handwritten identity or support/counter conflicts fail
atomically, while authored summaries and narrower boundaries remain intact.

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
