# Closure Report

Use this reference when a StorylineDesign run needs to state what the current story artifact can safely claim after workflow, ledger, structure, scene, promise/payoff, WorldGuard, prose-native, validation, and review checks have been considered. A closure report is the final synthesis surface. It does not replace those checks, and it must not hide partial, blocked, skipped, stale, or downgraded evidence behind polished prose.

## Boundary

StorylineDesign closure reporting owns:

- the final claim boundary for the requested artifact;
- the distinction between passed, partial, blocked, downgraded, deferred, skipped, stale, and human-review work;
- links from closure language to script evidence, validation output, review findings, PM disposition, and unresolved gaps;
- next actions for repair, recheck, user decision, or narrowed delivery.

Closure reporting does not own the detailed rules for workflow stages, ledger row shapes, WorldGuard mappings, turning-point checks, scene contracts, promise/payoff records, or prose projection. It cites those surfaces and summarizes their current evidence instead of duplicating their full content.

For final long-form prose, closure reporting also cites model-prose binding evidence. The report should state whether important prose spans bind to model rows, whether key or major model rows have prose evidence, whether duplicate binding or length-outlier drift remains, and whether reader-state simulation, resistance/friction, and register ownership were reviewed against the same final artifact.

## Closure Outcomes

Use exact outcome language.

- `passed`: The requested claim is supported by current evidence for the stated boundary.
- `partial`: Some requested work is supported, but the final claim is narrowed by explicit gaps, skipped checks, stale evidence, deferred rows, or scope limits.
- `blocked`: A required model surface, script check, review decision, or user choice prevents the requested claim.
- `downgraded`: The run originally targeted a stronger claim but must deliver a weaker supported artifact, such as audit notes instead of final prose, a scene sample instead of a chapter, or a partial outline instead of complete-story closure.
- `human_review`: A material creative or scope decision is required before pass, partial, blocked, or downgraded closure can be assigned.

Do not use `passed` when the report depends on unresolved key promises, non-pass WorldGuard claims, missing scene contracts, stale structure rows, unsupported prose, skipped required validators, or hidden reviewer/PM blockers.

## Closure Report Shape

Record closure as a structured report in the ledger `closure` object, a linked validation row, or a run-local report artifact.

```json
{
  "schema_version": "storyline-design.closure_report.v1",
  "project_id": "short-story-001",
  "report_id": "closure-report-001",
  "requested_artifact": "short_story",
  "closure_outcome": "partial",
  "claim_boundary": "Scene cards and outline are current; final prose is not claimed ready.",
  "completed_evidence": [
    {
      "surface": "scene_contract",
      "status": "passed",
      "evidence_refs": ["validation/scene_contracts.json"]
    }
  ],
  "unresolved_gaps": [
    {
      "surface": "worldguard",
      "status": "blocked",
      "gap": "Archive access claim is not_run.",
      "blocks": "complete-story prose closure",
      "next_action": "run_worldguard_or_scope_out_claim"
    }
  ],
  "deferred_or_downgraded_work": [
    {
      "surface": "prose_native",
      "downgrade_from": "final_story_prose",
      "downgrade_to": "scene_sample",
      "reason": "Promise payoff and WorldGuard evidence are partial."
    }
  ],
  "script_evidence": [
    {
      "command_or_check": "validate_storyline_ledger",
      "status": "partial",
      "evidence_ref": "validation/ledger_validate.json",
      "covered_rows": ["scene-001", "promise-main-question"],
      "skipped_checks": []
    }
  ],
  "reviewer_pm_disposition": {
    "reviewer_status": "pending",
    "pm_status": "pending",
    "required_decisions": []
  },
  "limitations": [
    "No final prose closure is claimed until promise and WorldGuard gaps are resolved."
  ],
  "next_actions": [
    "Return to WorldGuard adapter for wg-claim-archive-access."
  ]
}
```

Required fields:

- `schema_version`: `storyline-design.closure_report.v1`.
- `report_id`: stable closure report id.
- `requested_artifact`: artifact the run was asked to produce.
- `closure_outcome`: passed, partial, blocked, downgraded, or human_review.
- `claim_boundary`: one sentence naming what is and is not supported.
- `completed_evidence`: evidence-backed work that is current enough to claim.
- `unresolved_gaps`: blockers, stale rows, skipped checks, open promises, non-pass world claims, review findings, or user decisions.
- `deferred_or_downgraded_work`: work intentionally postponed, narrowed, or reduced from the requested target.
- `script_evidence`: validation commands or deterministic checks, with output refs and covered scope.
- `reviewer_pm_disposition`: reviewer and PM status when present.
- `limitations`: plain-language boundaries on the final claim.
- `next_actions`: concrete repair, recheck, user-decision, or delivery steps.

## Evidence Separation Rules

Separate completed evidence from unresolved work.

Completed evidence may say:

- which workflow gates reached `continue`;
- which ledger rows are current;
- which structure and turning-point checks passed;
- which scene contracts are keep or narrowed revise;
- which promises are paid, fairly inverted, abandoned_with_reason, explicitly deferred, or human-reviewed;
- which WorldGuard claims passed or were explicitly scoped out;
- which prose-native checks found no workflow-label leakage;
- which scripts, validators, manual reviews, or runtime checks produced current evidence.

Unresolved gaps must name:

- the owning surface: workflow, ledger, structure, scene_contract, promise_payoff, WorldGuard, prose_native, validation, reviewer, PM, or user_decision;
- the exact status: partial, blocked, skipped, stale, downgraded, human_review, not_run, unsupported, forbidden_use, boundary_exceeded, missing_handoff, or authority_cycle;
- the affected claim boundary;
- the required next action.

Do not blend these into vague language such as "mostly ready", "should be fine", "appears complete", or "can be finalized later" unless the report also names the concrete gap and narrowed boundary.

## Alignment Links

### Workflow Link

Closure reports read workflow gate outcomes and must preserve `continue`, `return`, and `user-decision` distinctions.

Report `partial`, `blocked`, or `human_review` when:

- any required workflow gate returned to an earlier stage;
- a user-decision gate is unresolved;
- closure depends on a skipped stage not allowed by the artifact boundary.

### Ledger Link

Closure reports read the ledger as the source of truth.

Return to ledger when:

- closure claims rely on prose paragraphs without ledger rows;
- validation evidence exists but the affected ledger rows are missing or stale;
- generated assumptions are counted as user-approved facts;
- the closure object does not name blocking, deferred, or stale rows.

### WorldGuard Link

Closure reports cite WorldGuard adapter evidence for generic world claims.

Report a narrowed boundary when:

- a WorldGuard status is fail, gap, boundary_exceeded, stale_source, forbidden_use, authority_cycle, missing_handoff, not_run, or human_review;
- a world claim was intentionally scoped out and therefore cannot support a stronger story-world claim;
- prose or outline introduced a new world fact after the last WorldGuard check.

### Structure And Turning Points Link

Closure reports cite structure and turning-point evidence for story shape.

Report partial or blocked when:

- setup, first plot point, reaction, midpoint, attack, second plot point, climax, or resolution is missing for a complete-story claim;
- parent structure rows are stale after scene, promise, or prose changes;
- local scene coherence is being used to claim parent structure closure.

### Scene Contract Link

Closure reports cite scene-contract outcomes for required scenes.

Report partial or blocked when:

- a required scene is revise, cut, human_review, stale, unsupported, or lacks a current contract;
- prose changes entry state, exit state, irreversible change, conflict, desire, obstacle, turn, or promise handling without updating the scene card;
- scene evidence is only aesthetic feedback rather than model evidence.

### Promise Payoff Link

Closure reports cite promise/payoff status for key and major promises.

Report partial, blocked, or downgraded when:

- a key promise is open, setup-only, payoff_planned without validation, partial, blocked, stale, unsupported, or human_review;
- a payoff lacks setup evidence;
- an inversion lacks fair setup;
- a promise is abandoned without an accepted reason and decision source;
- a late key promise has not passed the guardrail outcome.

### Prose Native Link

Closure reports cite prose-native evidence only for projection quality and leakage control.

Report partial or downgraded when:

- prose is a sample, style test, partial scene, or draft but the model does not support final prose closure;
- reader-facing prose leaks workflow labels, validation ids, ledger fields, checklist terms, or review jargon;
- reader-facing prose leaks planning, audit, chapter-purpose, author-forecast, or next-step language as reader-room contamination;
- reader-native prose has unresolved explanation pressure or variation pressure for the requested claim;
- prose is polished but model evidence remains partial, blocked, stale, skipped, or human_review.

## Script Evidence Requirements

Every closure claim should point to evidence that can be replayed or inspected.

For each script, validator, or manual check, record:

- check name or command label;
- run timestamp or evidence version when available;
- covered rows and artifact scope;
- status: passed, partial, blocked, skipped, stale, downgraded, or human_review;
- output path, result id, reviewer note, or PM disposition id;
- skipped checks with reasons;
- stale triggers and rerun requirements.

If no script exists for a required surface, say so directly and classify the check as manual, skipped_with_reason, partial, or blocked. Do not imply deterministic validation happened.

## Downgrade Rules

Use `downgraded` when the report deliberately lowers the delivery claim.

Examples:

- complete story downgraded to outline because promise/payoff closure is partial;
- final chapter downgraded to scene sample because WorldGuard claims are not_run;
- ready-to-publish prose downgraded to revision plan because scene contracts are stale;
- full closure downgraded to audit because reviewer or PM disposition is unresolved.

Each downgrade must name:

1. the original requested claim;
2. the supported replacement claim;
3. the evidence that supports the replacement;
4. the gaps that prevent the original claim;
5. next actions to regain the stronger claim.

## Terminal Replay And Disposition

A closure report is usable for terminal replay when a later operator can reconstruct why the run ended.

Include:

- final outcome and claim boundary;
- files, report ids, validation refs, and reviewer/PM disposition refs;
- commands or check names that produced evidence;
- skipped checks and reasons;
- limitations and downgraded work;
- unresolved blockers and exact next actions;
- whether the final artifact is reader-native prose, planning output, audit output, or mixed.

Reviewer and PM disposition should be able to accept, repair, defer, or reject the result from the closure report without reading every upstream reference first. The report should name upstream evidence surfaces, not copy their full rules.

## Closure Language Guard

Use conservative report language.

Allowed:

- "The outline is supported inside this boundary."
- "Final prose is not claimed ready because WorldGuard evidence is partial."
- "The run is downgraded from full story to scene sample."
- "Promise payoff review is passed for key promises and deferred for supporting promise rows listed below."

Forbidden unless fully supported:

- "Complete", "final", "ready", "closed", or "validated" without current evidence refs.
- "No issues" when skipped, stale, deferred, partial, or human-review rows remain.
- "WorldGuard passed" when only StorylineDesign checks ran.
- "Promise paid" when payoff evidence is planned but not checked.
- "Prose ready" when reader-native leakage or model evidence gaps remain.

## Minimal Closure Report Checklist

Before delivering a closure report, answer:

1. What artifact was requested?
2. Is the outcome passed, partial, blocked, downgraded, or human_review?
3. What exact claim boundary is supported?
4. Which workflow gates reached continue, return, or user-decision?
5. Which ledger rows are current, stale, blocked, deferred, or scoped out?
6. Which structure and turning-point evidence supports the claim?
7. Which scene contracts are keep, revise, cut, or human_review?
8. Which promises are paid, inverted, abandoned_with_reason, deferred, partial, blocked, stale, unsupported, or human_review?
9. Which WorldGuard claims are pass, scoped out, non-pass, stale, or not_run?
10. Which prose-native checks passed, and is any prose only a sample or draft?
11. Which scripts, validators, reviews, or runtime checks produced evidence?
12. Which checks were skipped, and why?
13. What limitations and unresolved gaps remain?
14. What next action should repair, recheck, defer, downgrade, or request a user decision?

Do not claim closure until these answers are explicit. If any answer is missing for the requested artifact, report partial, blocked, downgraded, or human_review with the earliest failed surface and next action.

## Longform Closure Compatibility

For novel, book, volume, series, chapter_batch, or chapter_draft artifacts, closure reports must name the closure level:

- chapter;
- volume;
- book;
- series;
- none, when the output is only planning or audit.

Add long-form completed evidence and gap surfaces:

- `novel_ledger`;
- `story_contribution`;
- `chapter_interface`;
- `voice_style`;
- `reverse_outline`;
- `reader_native_manuscript_review`;
- `variation_review`;
- `longform_closure`;
- `installed_parity` when reporting skill-package completion.

Chapter closure requires current chapter interface and voice/style evidence. Book closure requires aggregate hierarchy, key/major promises, story contribution, continuity, and child chapter or volume reports. Series closure requires book-level child reports and explicit boundaries for deferred series promises.

For final prose claims, artifact-bound semantic review must include reader-native manuscript review and variation review. Report partial, blocked, downgraded, or human_review when current final prose has unresolved reader-room contamination, author-facing chapter endings, explanation pressure, repeated chapter contribution without changed effect, weak character voice distinction, or unsupported payoff. Do not turn this into a genre-specific schema; state the functional story risk and the earliest surface to revisit.

Do not let a passed short-form scene, local outline, or polished chapter prose imply higher-level long-form closure. Report the supported level and the gaps that prevent the stronger claim.
