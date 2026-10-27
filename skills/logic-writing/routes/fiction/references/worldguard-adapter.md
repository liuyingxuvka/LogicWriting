# WorldGuard Story Adapter

Use this reference when a StorylineDesign ledger row needs world-consistency review. The adapter translates story-engineering rows into generic WorldGuard-checkable claims while keeping literary concepts in StorylineDesign artifacts.

## Boundary

StorylineDesign owns literary semantics:

- chapter, scene, beat, plot point, turning point, structure role;
- protagonist, antagonist, character arc, relationship arc, theme;
- promise, payoff, clue, reveal, mystery, emotional contract;
- reader-native outline, prose projection, voice, pacing, and revision lane.

WorldGuard owns generic world-claim validation:

- events and temporal order;
- agents, roles, capabilities, intentions, and constraints;
- spaces, resources, access, and availability;
- causality, conflicts, norms, consequences, and authority;
- model status, evidence status, counterexamples, gaps, stale evidence, and boundary findings.

Do not add story-specific fields to WorldGuard core files, schemas, guard families, statuses, or model mesh semantics. If a story needs a literary field, store it in the StorylineDesign ledger and map only the generic world claim to WorldGuard.

## Native world references

Add `world_refs` to the world contract; see [the native WorldGuard adapter](../../../references/adapters/worldguard.md).

## Mapping Targets

### Events

Use event claims for what happened, when it happened, and whether the order is possible.

Map from:

- scene entry and exit states;
- turning points;
- reveals, discoveries, reversals, and consequences;
- timeline promises and payoff rows.

WorldGuard-facing claim examples:

- `event`: the city bridge collapses before the evacuation scene.
- `temporal_order`: scene-002 happens before scene-004.
- `state_change`: the archive becomes inaccessible after the fire.

### Motives And Agents

Use motive and agent claims for ability, intent, knowledge, obligation, and decision pressure.

Map from:

- protagonist and opposition rows;
- scene desire, obstacle, and decision fields;
- relationship and character arc rows;
- norm, threat, or moral-pressure promises.

WorldGuard-facing claim examples:

- `agent`: the rival knows the map location before the protagonist.
- `capability`: the child witness cannot open the vault alone.
- `intent`: the mayor hides the flood warning to prevent panic.

WorldGuard can check consistency of the claim boundary. It does not decide whether the motive is artistically compelling; that remains a StorylineDesign review question.

### Spaces

Use space claims for locations, access, containment, distance, and movement constraints.

Map from:

- scene setting fields;
- structure rows that depend on travel or access;
- support rows with geography, architecture, or continuity facts.

WorldGuard-facing claim examples:

- `space`: the archive has one public entrance and one service tunnel.
- `access`: the protagonist cannot enter the observatory without a keycard.
- `distance`: the ferry crossing takes longer than the warning window.

### Resources

Use resource claims for availability, possession, scarcity, transfer, or loss.

Map from:

- stakes rows;
- promise/payoff rows involving objects, information, allies, or time;
- opposition pressure and scene obstacle fields.

WorldGuard-facing claim examples:

- `resource`: only one vial of antidote remains.
- `possession`: the rival has the map during scene-005.
- `availability`: the radio cannot transmit after the battery fails.

### Causality

Use causal claims for why one world state creates or prevents another.

Map from:

- turning points;
- scene irreversible changes;
- escalation rows;
- payoff rows that depend on prior setup.

WorldGuard-facing claim examples:

- `causal_link`: the false alarm causes the guard rotation to change.
- `precondition`: the engine must be repaired before the airship can leave.
- `consequence`: breaking the treaty triggers the border closure.

### Conflicts

Use conflict claims for mutually incompatible goals, actions, resource uses, or constraints.

Map from:

- opposition rows;
- scene conflict pressure;
- stakes and resource rows;
- competing promises or norms.

WorldGuard-facing claim examples:

- `conflict`: the protagonist needs the witness public, but the witness must remain hidden to survive.
- `resource_conflict`: two factions need the same bridge at the same time.
- `norm_conflict`: the oath requires silence, but the rescue requires warning the town.

### Norms

Use norm claims for laws, social rules, contracts, rituals, taboos, professional obligations, or moral constraints that affect world behavior.

Map from:

- support rows describing rules;
- promise rows that imply consequences;
- opposition pressure and authority rows;
- closure rows that depend on social or legal outcome.

WorldGuard-facing claim examples:

- `norm`: pilots are forbidden to leave before storm clearance.
- `authority`: the council can revoke the protagonist's license.
- `consequence`: breaking the ritual exile rule triggers public pursuit.

## Status Handling

Preserve WorldGuard outcomes exactly as downstream evidence. Do not convert a non-pass into story pass.

- `pass`: the generic world claim is currently supported.
- `fail`: the claim conflicts with current world evidence; return to the earliest affected ledger row.
- `gap`: required support is missing; block full closure or narrow the claim boundary.
- `boundary_exceeded`: the request asks WorldGuard to judge literary semantics directly; report an adapter boundary gap.
- `stale_source`: cited evidence is outdated; refresh support before closure.
- `forbidden_use`: evidence cannot be used for the requested claim; replace or scope out.
- `authority_cycle`: claim authority depends on itself or a circular handoff; repair ownership.
- `missing_handoff`: required upstream model or evidence is absent; return to ledger or support intake.
- `not_run`: keep as open until checked or explicitly scoped out.
- `human_review`: ask for the specific user or reviewer decision.

Each non-pass status must write a ledger validation row and update closure with `partial`, `blocked`, or `human-review`.

## Return Paths

WorldGuard outputs return to the StorylineDesign workflow instead of bypassing it.

- Return to `ledger` when ownership, authority, support, or row shape is wrong.
- Return to `structure` when the world claim changes story order, causality, escalation, or resolution.
- Return to `scenes` when the inconsistency is local to setting, access, resource, motive, conflict, or consequence.
- Return to `promises` when a world claim breaks setup/payoff credibility.
- Return to `revision` when the model is correct but outline or prose introduced an unsupported claim.
- Use `user-decision` when multiple repairs materially change the story direction.

## Creative Judgement Boundary

WorldGuard evidence can say whether a world claim is supported, inconsistent, stale, or outside boundary. It cannot by itself say that the scene is emotionally satisfying, the prose is strong, the theme is subtle, or the ending is artistically right.

StorylineDesign must combine WorldGuard evidence with ledger, structure, scene, promise/payoff, reader-native, and closure checks before claiming a story output is ready.

## Minimal Adapter Checklist

Before running or citing a WorldGuard check:

1. Identify the StorylineDesign source row.
2. Write a generic non-literary `claim_text`.
3. Fill `claim_type`, `worldguard_input`, and `authority_scope`.
4. Confirm literary fields remain in StorylineDesign.
5. Run or record the WorldGuard status.
6. Preserve non-pass, stale, forbidden, authority, and missing-handoff outcomes.
7. Write the status back to ledger validation and closure rows.
8. Route failures to ledger, structure, scenes, promises, revision, or user-decision gates.
