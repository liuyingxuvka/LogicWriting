# Guard Depth Policy

Use this reference after intake to decide how much model and Guard evidence a
StorylineDesign task needs. Depth scales with artifact size, dependency count,
and claim strength. It does not remove Guard consideration.

## Depth Tiers

### Compact

Use for a premise, small scene, micro story, quick audit, bounded outline fix,
or sample prose where no final readiness claim is made.

Required evidence:

- target artifact and claim boundary;
- compact FlowGuard process route;
- one compact story movement model: starting state, change, ending state;
- main promise/payoff or explicit no-promise boundary;
- TraceGuard, WorldGuard, LogicGuard, and SourceGuard status or
  `not_applicable_with_reason`;
- compact closure report with gaps and next actions.

### Short Story

Use for complete short-story plans, short-story repair, complete short prose,
or final readiness claims for one bounded story.

Required evidence:

- compact FlowGuard process route with stale-evidence rules;
- story ledger or equivalent rows for structure, scenes, promises, continuity,
  and support;
- TraceGuard storyline evidence when chronology, causality, mystery, or
  reveal order matters;
- WorldGuard story claims when rules, access, capability, resources, norms, or
  consequences affect payoff;
- LogicGuard theme support when the ending or moral claim matters;
- SourceGuard canon/source support when supplied material constrains output;
- reverse outline or postwrite observation when prose exists;
- closure aggregation.

### Intermediate

Use for chapter plans, chapter batches, novella sections, continuity repair, or
multi-scene arcs that are not full book closure.

Required evidence:

- all short-story surfaces;
- adjacent scene or chapter interfaces;
- reader-state before/after for important handoffs;
- voice/style continuity when prose exists;
- explicit stale-evidence handling after prose/model edits.

### Longform

Use for novels, books, volumes, series, chapter sequences, series bibles, and
final manuscript claims.

Required evidence:

- FlowGuard process route with child Guard handoffs and validation freshness;
- novel ledger as root index;
- story contribution rows;
- chapter interfaces and prose blueprints;
- promise/payoff rows for key and major promises;
- continuity rows for character_state, relationship_state, object, timeline,
  world_rule, clue_state, place, resource, POV, voice, style, and canon;
- TraceGuard storyline surfaces for true chronology, investigation order, and
  reader revelation order when material;
- WorldGuard story-claim surfaces for internal rules and world consistency;
- LogicGuard theme support when theme/ending interpretation is material;
- SourceGuard canon/source support when supplied material constrains output;
- reverse outlines from actual prose;
- aggregate long-form closure.

### Final Manuscript

Use when the user asks whether the final text is complete, high-quality,
publishable, ready to read, ready to deliver, or equivalent.

Additional evidence:

- original user requirements or accepted requirement matrix;
- final artifact path or durable id;
- final artifact hash;
- artifact-bound semantic review that read the same artifact hash;
- current postwrite reverse outline;
- current Guard surfaces after the last prose change.

## Depth Escalators

Escalate depth when any of these are present:

- mystery, time logic, hidden past, or staged revelation;
- fictional world rule affecting event order, capability, resource, authority,
  access, causality, or payoff;
- strong theme, moral, philosophical, or ending-interpretation claim;
- user-provided canon, previous draft, adaptation source, or external facts;
- multi-chapter dependency;
- final/complete/high-quality/publishable claim;
- evidence changed after previous review.

## Downgrade Rule

If the current evidence is too shallow for the requested claim, downgrade the
claim instead of hiding the missing work. Examples:

- complete short story -> outline only;
- final chapter -> scene sample;
- final manuscript -> repair plan;
- book closure -> chapter or volume closure only.
