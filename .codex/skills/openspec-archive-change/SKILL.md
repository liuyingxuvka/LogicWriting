---
name: openspec-archive-change
description: Archive a completed change after task and verification hard gates pass.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.6.0"
---

Archive a completed OpenSpec change after hard gates pass.

**Store selection:** If the user names a store (a store is a standalone OpenSpec repo registered on this machine) or the work lives in one, run `openspec store list --json` to discover registered store ids, then pass `--store <id>` on the commands that read or write specs and changes (`new change`, `status`, `instructions`, `list`, `show`, `validate`, `verify`, `archive`, `doctor`, `context`). Other commands do not take the flag. Hints printed by commands already carry the flag; keep it on follow-ups. Without a store, commands act on the nearest local `openspec/` root.

**Input**: Optionally specify a change name. If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

**Core rule**

Archive is a hard-gated finalization step. Do not archive with incomplete artifacts, incomplete or missing tracked tasks, missing verification, failed verification, blocked verification, stale verification evidence, or anything short of a current passing verification report. The `--yes` and `--no-validate` flags may skip prompts or spec validation only; they must not bypass task or verification gates.

**Steps**

1. **Select the change**

   If no change name is provided:
   - Run `openspec list --json`
   - Use the AskUserQuestion tool to let the user select one active change
   - Show only active changes, not already archived changes

   Do not guess when several changes are plausible.

2. **Check artifact completion**

   ```bash
   openspec status --change "<name>" --json
   ```

   Parse:
   - `schemaName`
   - `planningHome`, `changeRoot`, `artifactPaths`, and `actionContext`
   - `artifacts`: list of artifacts and whether each is `done`

   If any artifact is not `done`, STOP and list the missing/blocked artifacts. Do not ask for confirmation to bypass this.

3. **Check tracked tasks**

   Read the tracked tasks file from the status/apply context, typically `tasks.md`.

   STOP if:
   - the tracked tasks file is missing
   - it contains zero checkbox tasks
   - any task remains `- [ ]`

   Task completion is required but not sufficient. Completed tasks only mean the change may proceed to verification.

4. **Run verification immediately before archive**

   ```bash
   openspec verify "<name>" --json
   ```

   STOP if the command fails or the JSON `status` is not `pass`.

   If the contract is missing, invalid, has no required evidence, relies only on task checkboxes, has failed required checks, or was run with `--no-run`, treat archive as blocked.

5. **Archive through the CLI**

   Use the CLI command so the built-in archive hard gates run again:

   ```bash
   openspec archive "<name>"
   ```

   If running non-interactively is appropriate:

   ```bash
   openspec archive "<name>" --yes
   ```

   Do not manually move the change directory. Manual moves bypass spec sync, task checks, verification freshness, and archive target collision checks.

6. **Report the result**

   On success, summarize:
   - change name
   - schema
   - verification report path
   - archive location shown by the CLI
   - spec sync result shown by the CLI

**Output On Success**

```
## Archive Complete

**Change:** <change-name>
**Schema:** <schema-name>
**Verification:** passed (<reportPath>)
**Archive:** <path from CLI output>
```

**Output When Blocked**

```
## Archive Blocked

**Change:** <change-name>
**Reason:** <artifact/task/verification issue>

### Required Fixes
- <specific next action>

Run `openspec verify <change-name>` again after fixes, then retry archive.
```

**Guardrails**
- Use `openspec archive`; do not move directories by hand
- Do not bypass incomplete artifacts or tasks with confirmation
- Do not bypass missing, failed, blocked, skipped, not-run, or stale verification
- Run verification as close to archive as possible so watched source hashes are current
- If archive reports stale verification, rerun `openspec verify <name>` and retry only after it passes
- If delta specs exist, let `openspec archive` perform its existing spec update assessment and prompts

<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose
Bind each OpenSpec skill run to the declared integration mode, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers openspec-archive-change plus explicitly routed local materials; no unrelated repos, private files, external services, publication, or release claims unless requested and routed.
## Local Material Routing
Use the active OpenSpec store, change artifacts, repository files, and configured tool directories returned by OpenSpec commands. Keep private machine paths local and public instructions portable.
## Entrypoint Acceptance Map
Use SkillGuard as the runtime contract executor for missing gates around the target OpenSpec workflow. It enforces missing contract gates through the native OpenSpec command flow; duplicate SkillGuard-owned execution paths are invalid. Declared gates/routes: select change, read artifacts, execute or verify, closure.
## Use When
Use when the request matches openspec-archive-change and needs this governed workflow, materials, checks, or handoff behavior.
## Do Not Use When
Do not use outside the OpenSpec workflow domain, without required materials, when a more specific skill owns the work, or for tiny direct answers.
## Required Workflow
Select the target-owned native route/check surface, run the SkillGuard contract gates around the native workflow, collect evidence, run checks, fix failures, then report.
## Hard Gates
Do not skip phases, do not replace required evidence with prose, do not treat stale reports as current, do not weaken validation to pass, and do not claim completion when blockers remain.
## Output Requirements
Report evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary; distinguish checked, unchecked, blocked, and uncertain.
## SkillGuard Maintenance
Keep generated OpenSpec skills compatible with downstream SkillGuard control roots, contracts, checks, evidence, and ledgers; rerun SkillGuard after entrypoint, route, evidence, or closure changes.
<!-- END SKILLGUARD CONTRACT LAYER -->
