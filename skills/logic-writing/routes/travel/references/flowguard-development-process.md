# FlowGuard Development Process

Use FlowGuard DevelopmentProcessFlow when building, changing, installing, syncing, or claiming completion for this skill.

## Required Modes

- `plan_detailing`: OpenSpec proposal, design, spec, verification contract, and tasks are explicit.
- `agent_workflow`: SourceGuard, WorldGuard, TraceGuard, LogicGuard, the shared reader kernel, FlowGuard, and SkillGuard responsibilities are ordered.
- `execution_freshness`: changed files, validators, installed copy, global router refresh or resolution, and git commit are checked against current evidence.
- `traveler_native_projection`: final guide text is compiled after model surfaces, hides model-room labels, and is reverse-reviewed from the delivered artifact.

## Freshness Rules

- Changes to `SKILL.md` stale bundle validation, contract validation, install sync, and global router checks.
- Changes to `references/*.md` stale bundle validation, plan validation, failure fixture validation, and runtime contract evidence.
- Changes to traveler-native projection references or text validators stale final text-output validation and reverse-guide review evidence.
- Changes to `scripts/*.py` stale all validator results that use those scripts.
- Changes to examples stale plan and failure-case validation.
- Changes to `.skillguard/contract-source.json`, `.skillguard/compiled-contract.json`, or `.skillguard/check-manifest.json` stale SkillGuard validation and global router evidence. Former SkillGuard v1 names are forbidden residuals, not fallback inputs.
- Changes after install stale installed-copy match evidence.
- Changes after global router refresh stale router evidence.
- Changes after commit stale final git closure evidence.

## Forbidden Shortcuts

- user request -> story output;
- SourceGuard candidates -> final recommendation without TraceGuard and WorldGuard;
- TraceGuard route trace -> final route without WorldGuard route stress check;
- WorldGuard candidate pass -> route pass without assembled-route check;
- model-room route cards -> traveler-facing guide without traveler-native projection and reverse-guide review;
- story polish -> evidence boundary;
- repository edits -> installed-copy claim without sync check.

Do not claim FlowGuard completion from project adoption logs alone. Use current command evidence and final adoption notes.
