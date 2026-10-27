# Structure And Turning Points — detailed checks

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
