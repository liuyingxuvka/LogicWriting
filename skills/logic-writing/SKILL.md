---
name: logic-writing
description: "Use for a finished piece for real readers: a source-backed investigation report, an academic paper or revision, fiction or a story plan, or an evidence-heavy travel guide. Not for checking claims, sources or causal timelines on their own; use researchguard."
---

# Logic Writing

## Start from the model

Store the user's request once, as received, in the brief's request; each required unit names its source (request with a verbatim quote, research, or ai), and closure lists the ai units for the user.

The plan (CompositionPlan) is the model of the piece. Read it back before choosing a route or a command:

- A plan exists (`reader-brief.json` or any later chain file): run `python scripts/show_plan.py --input <file>`, read its summary line, and continue from `UNBOUND` units and units with findings. Discuss the work on planned units.
- A research question is involved: read `researchguard status <folder>` first (one hypothesis: `--hypothesis <id>`), save it with `--json --output research-status.json`, and name `research_folder` and `research_status` in the brief request.
- A story or trip world is involved: read WorldGuard's `timeline --contract <world>` first (`--mesh` for a tree).
- No plan yet: choose one final route and build the brief from the example in `assets/examples/<route>/`; that plan is the model.
- When one planned unit gets too big, split it into child units (parent_unit_id), and plan and check only the units the target text needs.

Logic Writing has one entrypoint and four focused routes. It investigates hard
questions, builds defensible academic artifacts, plans and repairs fiction,
builds operational travel guides, and translates internal analysis into
language a reader can follow. It owns routing, bounded handoffs, freshness,
reader-facing translation and final closure, never a specialist's native judgment.

## Choose the final route

Select exactly one final owner by the terminal deliverable (`investigation`,
`academic-writing`, `fiction-writing` or `travel-guide`), not by the first
action or the subject. Other routes send bounded requests; the final owner keeps
closure. Ask one focused question when the deliverable is materially ambiguous.
Read [references/router.md](references/router.md) for routing details.

## The plan is the model of the piece

- Node: a planned unit of the CompositionPlan; a failing unit shows its counterexample: the quoted span with the audit or review finding.
- Parent: `parent_unit_id` (book > volume > chapter > scene; guide > day > section).
- Known-bad: `scripts/known_bad.py` edits of the current text (no citation, dropped token, leak, overclaim, removed limitation, truncation, swapped sibling units, removed world reference, removed live alternative); each one must be caught, and closure lists uncaught ones.
- Real binding: exact unique quotes in the current text (SharedWriting `anchor_excerpts`), `world_refs` into the WorldGuard contract, and anchors from one ResearchGuard research folder whose saved report must belong to it. Each required unit of a researched piece cites an anchor that is not only counter, or states unsupported_reason.
- Test binding: the deterministic audit, the route review with quoted spans, and an independent reader for broad claims.
- Readback: `scripts/show_plan.py` (a summary line, then the plan tree beside its bound text with each unit's findings).
- Current vs target: the text, and for a revision its source-unit manifest, is the current model; the plan is the target, and the revised text replaces the current one when closure passes.

## Commands

Run existing text with `python scripts/run_chain.py <folder> [--refresh-providers]`.
See [reader-chain commands and inputs](references/shared/reader-chain.md) for
step selection, native refresh, expert commands and saved reports.

## Hard Gates

- Do not write a confident final answer while a critical claim has no usable
  support; bound it or report it.
- A broad quality claim needs the complete current artifact-quality chain, an
  independent read, a passing ResearchGuard `verdict` for investigation and for
  academic work with live alternatives or `research_folder`, and WorldGuard for
  travel or fiction with `world_check_required`. Material live competition
  must be adjudicated or explicitly bounded before a
  broad claim. Preserve native wording limits; no stop decision is an assert license.
- `contested` adds `research:contested` risk rather than a new blocking rule.
  A passing self-review stays explicit (`SELF`, `broad_claim_allowed: false`);
  it cannot be presented as independent confirmation.
- Long-form and itinerary findings are derived from their actual files. Keep
  unknown/unquoted world references, remaining project gaps and `toothless:`
  known-bad findings in the current closure; never fill their verdicts by hand.
- Do not let one sibling route call another or issue its closure.
- Do not route LogicGuard, SourceGuard, or TraceGuard through any executable
  other than the single `researchguard` console.
- Do not convert a missing provider, stale result, skipped check, partial
  search, failed rendering, or unsupported claim into success.
- Do not expose internal workflow vocabulary in ordinary final prose.

## Output Requirements

Return the requested reader-facing artifact first. When the work is not fully
closed, add a short, plain-language audit note containing these exact fields:

- `failures`: checks that ran and failed;
- `blockers`: missing authority, access, provider, evidence, or user choice;
- `skipped_checks`: checks that did not run, with the reason;
- `residual_risk`: uncertainty that remains after completed checks;
- `claim_boundary`: what the current evidence does and does not license.

Keep those fields out of normal prose when every required gate passes and the
user did not request an audit record. Never describe an output as complete when
one of the five fields contains a material unresolved item.
