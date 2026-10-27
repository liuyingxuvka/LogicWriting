# Migration to the current Logic Writing

Keep the `logic-writing` entrypoint, four final owners and existing user material.
ResearchGuard's installed console supplies the research question result and its
three native semantic members. The minimum version has one authority in
`skills/logic-writing/scripts/_common.py`. WorldGuard remains a separate native
owner, found in the skills root or through its explicit `--provider-root`.

SourceRegistry, ClaimSupport and ResearchPacket and their scripts are removed;
a piece's evidence stays in its content boundaries and ResearchGuard research folder.

Brief requests use `research_folder`, relative to their JSON file, for a folder
or `research.yaml`. Source-owned anchor ids, source ids and locators cannot be
silently overridden: conflicting handwritten ownership fails
`anchor_conflict:<id>`, while matching author summaries and dispositions remain.
Save one `researchguard status <folder> --json --output research-status.json` and
name the `researchguard` report in closure. Native errors, stop conditions,
wording limits and live hypotheses remain authoritative; `contested` is a risk,
not a new gate. A source-only stop is not a root-claim assert license.

## Current maintenance

Find the current runtime/schema/test owner in `.flowguard/map.json`. Reader work
is grouped by planning, binding, checking and closure. Supported reader-chain
request wrappers keep their names and input/output flags. ResearchGuard supplies
fresh saved reports and source anchors; CompositionPlan is the sole writing plan.

The CompositionPlan is the piece's one unit tree. Long-form ledgers use planned
unit ids and point to that same plan; one `longform_project` supplies actual
project files to shared closure. Travel uses one itinerary `trip_plan` and the
guide CompositionPlan. World references bind through `world_contract` and
`world_refs`; missing/unknown objects are errors, not guessed replacements.
Do not supply handwritten long-form or itinerary conclusions.

After any edit, rebuild affected byte references, quoted bindings, audits and
reviews. `create_new` may omit provenance and receive the not-applicable default;
`revise_existing` still needs real source bytes and complete treatments.
Quality `passed` requires the actual audit, route review and judgment. A
self-review remains explicit and never grants a broad claim. Broader claims also
need an independent read, applicable native verdicts and disposition of material
live competition. Plans, labels and caller scores do not verify a read.

Use `scripts/show_plan.py` to inspect current plan/text bindings and
`scripts/known_bad.py` for deterministic defects in a disposable copy of the
current piece. They do not generate new prose. Normal development uses affected
checks; final CI runs the complete suite and native gates on the publication
source. Installation, Git tag and hosted Release identities remain separate.

## Installation

Install with `python scripts/install_skill.py --target <skills dir>`; add
`--check` to compare the installed copy with source. This copies the one canonical
skill; project metadata installation does not install it.

The former `storyline-design` and `travel-story-planner` skill ids remain retired
without runtime aliases. Preserve user
manuscripts, libraries and plans when moving old active skill directories out of
the skills root. All supported writing intents enter through `$logic-writing`;
ResearchGuard, WorldGuard, Documents and PDF retain their native responsibilities.

Earlier migration details remain in
[the historical record](docs/history/migration-before-4.0.5.md).
