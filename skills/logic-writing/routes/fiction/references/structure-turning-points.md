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
  "id": "turn-midpoint-001",
  "kind": "turning_point",
  "part": "part_2_reaction",
  "moment": "midpoint",
  "owner_stage": "structure",
  "source_rows": ["premise-main", "scene-006", "promise-central-question"],
  "entry_state": "The protagonist reacts to pressure without controlling the investigation.",
  "structural_event": "The protagonist learns the rival is using the missing map as bait.",
  "choice_or_reveal": "The protagonist chooses to pursue the rival directly.",
  "exit_state": "The protagonist has a new strategy and higher personal risk.",
  "irreversible_change": "The rival now knows the protagonist is involved.",
  "pressure_change": "redirects",
  "arc_links": ["arc-protagonist-agency"],
  "promise_links": ["promise-map-race"],
  "worldguard_claim_links": ["wg-claim-archive-access"],
  "status": "planned",
  "evidence_refs": [],
  "closure_effect": "blocks_full_closure_until_checked"
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

## Midpoint Check

The midpoint redirects the story by changing the meaning, strategy, or stakes of the central problem.

Required evidence:

- a reveal, reversal, victory, defeat, discovery, commitment, or consequence;
- an entry state showing the old strategy or belief;
- an exit state showing the new strategy, knowledge, obligation, or cost;
- promise rows affected by the changed understanding;
- arc rows showing whether agency, belief, relationship, or theme pressure changed.

Pass conditions:

- The midpoint changes the story's operating conditions, not only its intensity.
- Earlier setup and reaction rows support the turn.
- Later attack rows depend on the midpoint's changed state.

Return conditions:

- Return to structure when the midpoint can be removed without changing part 3.
- Return to promises when the midpoint answers, reverses, or escalates a promise without recording that effect.
- Return to WorldGuard mapping when the midpoint depends on an unvalidated world claim.

## Attack Check

Attack converts reaction into active pressure after the midpoint.

Required evidence:

- protagonist or focal-agent strategy after the midpoint;
- opposition escalation or counter-strategy;
- scene contracts that show active attempts, costs, and consequences;
- stakes and promise rows showing what the attack risks or forces;
- causal links from midpoint to second plot point.

Pass conditions:

- The protagonist is no longer only reacting unless the story intentionally models constrained agency.
- Opposition pressure escalates or becomes more specific.
- Each attack unit has a state change or narrows available options.

Return conditions:

- Return to protagonist, opposition, or scenes when agency or pressure is only asserted.
- Return to structure when attack scenes can be reordered arbitrarily without changing cause or escalation.
- Use `user_decision` when the attack path depends on a major strategic choice with multiple valid story directions.

## Second Plot Point Check

The second plot point turns active pressure into final crisis or final commitment.

Required evidence:

- final major reveal, loss, discovery, commitment, reversal, or irreversible cost before climax;
- narrowed options that explain why the story must move to the final confrontation;
- links to unresolved promises, stakes, arcs, and world claims;
- a clear handoff to climax conditions.

Pass conditions:

- The second plot point concentrates the conflict instead of simply adding another obstacle.
- The climax cannot happen in the same way without this turn.
- Open promises are identified as payoff-ready, intentionally deferred, reversed, or blocked.

Return conditions:

- Return to attack when the second plot point has no causal preparation.
- Return to promises when unresolved setups are not assigned to climax, resolution, deferral, or blocker rows.
- Return to WorldGuard mapping when the final crisis depends on a causality, resource, timeline, authority, or norm claim that is absent or non-pass.

## Climax Check

The climax tests the central conflict, choice, or irreversible outcome promised by the structure.

Required evidence:

- final conflict or decisive pressure;
- protagonist or focal-agent action, failure, sacrifice, refusal, discovery, or choice;
- opposition or constraint response;
- payoff rows for central question, stakes, arc, mystery, threat, or emotional contract;
- world claims required for the climax to be possible.

Pass conditions:

- The climax resolves or intentionally transforms the main pressure instead of avoiding it.
- The decisive action follows from prior structure, scene, promise, and world evidence.
- Major promises are paid, reversed, or explicitly deferred with a visible boundary.

Return conditions:

- Return to second plot point when the climax starts without the necessary crisis handoff.
- Return to scenes when the decisive action has no scene contract or irreversible change.
- Return to ledger when the climax depends on unsupported arc, promise, stake, support, or world facts.

## Resolution Check

Resolution records the post-climax state and what the story can safely claim as closed.

Required evidence:

- changed end state compared with setup;
- status for central promise, major subpromises, stakes, protagonist arc, relationship arc, theme, and world claims;
- closure row that says pass, partial, blocked, or human-review;
- reader-native projection boundary for outline, draft, or final prose.

Pass conditions:

- The resolution follows from the climax and does not invent unsupported closure.
- Setup/payoff relationships are visible in ledger rows.
- Any intentionally open ending has a deferral reason and claim boundary.

Return conditions:

- Return to climax when the resolution claims an outcome the climax did not earn.
- Return to promises when payoff coverage is incomplete or hidden.
- Return to revision when prose or outline claims closure not supported by the model.
- Use `user_decision` when the ending class, ambiguity level, or thematic conclusion materially changes the story.

## Model-First Workflow Gates

Before outline:

1. Create or update setup, first plot point, reaction, midpoint, attack, second plot point, climax, and resolution rows.
2. Link each row to premise, scene, promise, arc, support, and WorldGuard claim rows as needed.
3. Mark missing turns as `gap`, `partial`, `blocked`, `skipped`, or `human-review`; do not silently treat them as pass.

Before prose drafting:

1. Confirm structure rows have current evidence.
2. Confirm important scene contracts inherit the correct parent structure role.
3. Confirm unresolved WorldGuard, support, promise, or human-review rows are narrowed or returned.
4. Set `prose_allowed` only for the supported claim boundary.

Before revision closure:

1. Recheck affected turning-point rows after any structural, scene, promise, or world-claim change.
2. Preserve stale evidence until refreshed.
3. Update closure with the latest structure validation refs.
4. Do not let polished prose override a failed structure row.

## Minimal Turning-Point Checklist

For each required moment, ask:

1. What is the entry state?
2. What event, choice, reveal, reversal, or consequence creates the turn?
3. What is the exit state?
4. What changed irreversibly?
5. Which promise, stake, arc, scene, support, or WorldGuard rows does it touch?
6. Does it prepare the next part of the structure?
7. Is the status pass, partial, blocked, gap, skipped, stale, or human-review?
8. Which workflow gate receives a non-pass result?

Full-story closure requires current answers for setup, first plot point, reaction, midpoint, attack, second plot point, climax, and resolution, or an explicit narrowed boundary explaining why a missing moment is out of scope.
