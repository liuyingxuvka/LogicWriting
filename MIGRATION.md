# Migration to Logic Writing 4.0.8

This patch keeps the `logic-writing` entrypoint and four final owners. The
three native research members need ResearchGuard at or above the minimum
version declared in `skills/logic-writing/scripts/_common.py`; repository
maintenance uses FlowGuard. WorldGuard is found next to `logic-writing` in the
skills root, or through `--provider-root`.

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

Final reader closure needs the deterministic audit, the route review and a
ReaderJudgment from a reader that did not write the text; no execution capture
is required. Plans, caller scores and completion markers cannot substitute for
reading the actual text.

## Installation

Copy `skills/logic-writing` to a temporary sibling of the active directory.
Compare exact source/stage file sets and byte hashes, check required route
resources and the five route smoke scenarios, then replace `logic-writing`.
Retain the previous directory outside the active skill root for rollback.

The old `storyline-design` and `travel-story-planner` ids remain retired with
no runtime aliases. Move any old active directories outside the skill root;
all supported intents enter through `$logic-writing`. Keep separate native
SourceGuard, LogicGuard, TraceGuard, WorldGuard, Documents and PDF
responsibilities. Source parity, installation, Git tag and hosted Release
identities are checked separately. Predecessor repository deletion remains
user-owned.

Earlier migration details are retained in
[the historical record](docs/history/migration-before-4.0.5.md).
