# Migration to Logic Writing 4.0.7

This patch keeps the `logic-writing` entrypoint and four final owners. Use
ResearchGuard 0.5.7 for the three native research members and FlowGuard 0.70.5
for repository model maintenance. WorldGuard uses its explicitly selected
portable skill launcher. No SkillGuard installation or author state is used.

Keep manuscripts, evidence libraries, travel plans and other user material.
Rebuild affected current byte references and reader evidence after changes;
historical receipts do not become current by changing their version text.

## Current maintenance

Use `.flowguard/map.json` to find the existing runtime/schema/test owner and its
native state models. Former writer projection, editorial disposition,
composition graph and artifact audit declarations belong to reader-artifact;
ResearchGuard handoff belongs to research-packet. Run affected ordinary tests
or native checks during development. Freeze source after archive/version edits
and run the stable offline release contract once, including one full pytest.
Live quality experiments and their read-only consumers remain explicit opt-in.

Final reader closure and passing judgment receipts now require the existing
local capture resolver. The captured existing ReaderJudgment JSON must match
its current input identities and substantive output; the orchestrator fills
its execution fingerprint after capture. Plans, caller scores and completion
markers cannot substitute for actual judgment output.

## Installation

Copy `skills/logic-writing` to a temporary sibling of the active directory.
Compare exact source/stage file sets and byte hashes, check required route
resources and the five route smoke scenarios, then replace `logic-writing`.
Retain the previous directory outside the active skill root for rollback.

The old `storyline-design` and `travel-story-planner` ids remain retired with
no runtime aliases. Move any old active directories outside the skill root;
all supported intents enter through `$logic-writing`. Keep separate native
SourceGuard, LogicGuard, TraceGuard, WorldGuard, FlowGuard, Documents and PDF
responsibilities. Source parity, installation, Git tag and hosted Release
identities are checked separately. Predecessor repository deletion remains
user-owned.

Earlier migration details are retained in
[the historical record](docs/history/migration-before-4.0.5.md).
