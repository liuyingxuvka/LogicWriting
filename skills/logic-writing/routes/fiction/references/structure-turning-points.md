# Structure And Turning Points

Use this reference when a StorylineDesign task needs to test whether a story structure is strong enough to support outline, draft, review, revision, or closure. The checks are model-first: record structural commitments in the story-engineering ledger before projecting them into prose.

## Boundary

StorylineDesign owns structure terms such as act, part, sequence, chapter, beat, turning point, climax, resolution, setup, reaction, and attack. These terms stay in the StorylineDesign ledger and references.

WorldGuard may review generic world claims created by structural turns, such as event order, causality, access, resources, conflict, norms, and authority. Do not move literary structure fields into WorldGuard core models.

The turning-point checks do not decide whether a scene is beautifully written. They decide whether the current model has enough structural evidence to proceed or whether the workflow must return to ledger, structure, scenes, promises, WorldGuard, revision, or user decision.

## Ledger Row Shape

Record structure checks in the ledger `structure` section or a linked `validation` row.

```json
{
  "part": "part_2_reaction",
  "moment": "midpoint",
  "owner_stage": "structure",
  "source_rows": [
    "premise-main",
    "scene-006",
    "promise-central-question"
  ],
  "structural_event": "The protagonist learns the rival is using the missing map as bait.",
  "choice_or_reveal": "The protagonist chooses to pursue the rival directly.",
  "irreversible_change": "The rival now knows the protagonist is involved.",
  "pressure_change": "redirects",
  "arc_links": [
    "arc-protagonist-agency"
  ],
  "promise_links": [
    "promise-map-race"
  ],
  "worldguard_claim_links": [
    "wg-claim-archive-access"
  ],
  "evidence_refs": [],
  "closure_effect": "blocks_full_closure_until_checked",
  "planned_unit_id": "turn-midpoint-001"
}
```

Required fields:

- `id`: stable row id.
- `kind`: `structure_unit`, `turning_point`, or `structure_validation`.
- `part`: `part_1_setup`, `part_2_reaction`, `part_3_attack`, or `part_4_resolution`.
- `moment`: setup, first_plot_point, reaction, midpoint, attack, second_plot_point, climax, resolution, or custom.
- `entry_state`: story state before the structural moment.
- `structural_event`: what happens in story-world terms.
- `choice_or_reveal`: decision, reveal, reversal, consequence, or pressure that creates the turn.
- `exit_state`: story state after the moment.
- `irreversible_change`: what cannot remain the same after the turn.
- `pressure_change`: introduces, escalates, redirects, reverses, concentrates, releases, or resolves.
- `promise_links`: setup, escalation, payoff, reversal, or deferral rows affected by the moment.
- `status`: planned, pass, partial, blocked, gap, skipped, stale, or human-review.
- `closure_effect`: continue, return_to_ledger, return_to_structure, return_to_scenes, return_to_promises, return_to_worldguard, return_to_revision, user_decision, or scoped_out.

## Four-Part Structure Map

Use the four-part map as a check surface, not as a formula that every story must obey in the same page count.

| Part | Required structural job | Required turning-point evidence |
| --- | --- | --- |
| Part 1: Setup | Establish the starting state, protagonist pressure, stakes, promise surface, and disruption path. | Setup row plus first plot point row. |
| Part 2: Reaction | Show consequences of the first plot point and force defensive movement, confusion, pursuit, or adaptation. | Reaction row plus midpoint row. |
| Part 3: Attack | Convert reaction into active pressure, stronger opposition, cost, and narrowing options. | Attack row plus second plot point row. |
| Part 4: Resolution | Drive final confrontation, payoff, and changed end state. | Climax row plus resolution row. |

Each part must have:

- an entry state and exit state;
- a pressure movement;
- at least one linked promise, stake, arc, or world claim unless explicitly scoped out;
- a status and closure effect;
- an evidence reference or a visible gap.

## Setup Check

The setup defines the story state that later turns must change.

Required evidence:

- premise row with dramatic question, starting state, disruption pressure, success condition, and failure condition;
- protagonist or focal-agent row with desire, limit, and agency rule;
- opposition or pressure row with a credible source of conflict;
- stakes row showing what can be lost or gained;
- at least one promise row for the central question, emotional contract, mystery, clue, threat, or thematic setup;
- world boundary or support rows for facts that later structure depends on.

Pass conditions:

- The opening state is specific enough that later change can be measured.
- The first major pressure is tied to a ledger row, not only a prose paragraph.
- Setup promises are linked to future payoff, reversal, deferral, or blocker rows.

Return conditions:

- Return to ledger when premise, stakes, promise, protagonist, or opposition rows are missing.
- Return to WorldGuard mapping when setup depends on a world fact, timeline, resource, access rule, or norm that is not represented as a generic claim.
- Use `user_decision` when two or more starting premises, protagonists, conflict sources, or promise priorities would create materially different stories.

## First Plot Point Check

The first plot point moves the story from setup into committed movement.

Required evidence:

- a triggering event, choice, reveal, consequence, or external pressure;
- a before/after state change;
- a reason the protagonist cannot simply return to the setup state;
- affected promise, stake, arc, or scene rows;
- any required world claim for event order, access, resource transfer, capability, or causality.

Pass conditions:

- The turn creates a new story direction rather than only adding information.
- The protagonist, opposition, or story world must respond to the change.
- The turn has a ledger link to later reaction and midpoint rows.

Return conditions:

- Return to structure when the first plot point repeats setup without changing pressure.
- Return to scenes when the scene containing the turn has no irreversible change.
- Return to promises when the turn opens a question with no planned payoff, reversal, or deferral.

## Reaction Check

Reaction shows how the story absorbs the first plot point before the protagonist can fully control the problem.

Required evidence:

- scenes or structure units showing consequence, confusion, pursuit, avoidance, survival, investigation, or adaptation;
- pressure movement from first plot point toward midpoint;
- character desire and obstacle rows for major reaction scenes;
- promise and stake updates showing what the reaction tests or delays.

Pass conditions:

- Reaction is not filler; each reaction unit changes knowledge, pressure, relationship, resource state, or risk.
- The protagonist's choices are constrained by setup and first plot point evidence.
- Reaction prepares the midpoint rather than jumping to it without cause.

Return conditions:

- Return to scenes when reaction scenes do not change state.
- Return to structure when reaction has no causal bridge to midpoint.
- Return to ledger when reaction relies on a new assumption not recorded in support, premise, or WorldGuard rows.

Detailed checks continue in [structure-turning-points-details](structure-turning-points-details.md).

## Midpoint Check

See [Midpoint Check](structure-turning-points-details.md#midpoint-check).

## Attack Check

See [Attack Check](structure-turning-points-details.md#attack-check).

## Second Plot Point Check

See [Second Plot Point Check](structure-turning-points-details.md#second-plot-point-check).

## Climax Check

See [Climax Check](structure-turning-points-details.md#climax-check).

## Resolution Check

See [Resolution Check](structure-turning-points-details.md#resolution-check).

## Model-First Workflow Gates

See [Model-First Workflow Gates](structure-turning-points-details.md#model-first-workflow-gates).

## Minimal Turning-Point Checklist

See [Minimal Turning-Point Checklist](structure-turning-points-details.md#minimal-turning-point-checklist).
