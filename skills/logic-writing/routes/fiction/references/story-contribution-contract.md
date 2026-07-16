# Story Contribution Contract

Use this reference when Longform Mode needs to decide whether a chapter, scene, arc, thread, promise, clue, subplot, or continuity row actually earns its place in a larger story. A story unit is not valid merely because it is written well; it must contribute to a parent unit or have an explicit terminal treatment.

## Unit Shape

Record story contribution rows in `story_units` or an equivalent structured surface:

```json
{
  "id": "chapter-03",
  "kind": "chapter",
  "parent_id": "volume-01",
  "importance": "major",
  "status": "pass",
  "contribution": "Forces the protagonist to trade secrecy for access to the archive.",
  "downstream_use": ["chapter-04", "promise-archive-cost", "arc-agency"],
  "terminal_treatment": "keep",
  "repair_action": "",
  "evidence_refs": ["chapter-interfaces.json#iface-ch03"]
}
```

Required fields:

- `id`: stable unit id.
- `kind`: book, volume, chapter, scene, arc, thread, promise, clue, relationship, continuity, or support.
- `parent_id`: owning book, volume, chapter, arc, thread, or closure level.
- `importance`: key, major, supporting, optional, or background.
- `status`: pass, weak, orphan, duplicate, unsupported, stale, blocked, scoped_out, or human_review.
- `contribution`: what changes in the parent because this unit exists.
- `downstream_use`: later units, promises, arcs, continuity rows, or closure checks that depend on this unit.
- `terminal_treatment`: keep, revise, cut, merge, defer, scoped_out, or human_review.
- `repair_action`: required for any non-pass status except scoped_out with reason.

## Contribution Checks

### Parent Contribution

Pass when the unit changes at least one parent-level surface:

- plot state;
- character or relationship arc;
- promise, clue, mystery, or payoff state;
- stakes or resource state;
- theme pressure;
- continuity or world constraint;
- reader knowledge or expectation;
- pacing function that supports a declared parent role.

Fail as orphan when the unit has no parent, no contribution, and no scoped-out reason.

### Downstream Use

Pass when at least one later surface depends on the unit, or the unit is a terminal payoff/resolution.

Fail as weak or orphan when:

- the unit can be removed without changing any later row;
- downstream use is a generic placeholder such as "adds flavor";
- the unit repeats another unit's job without new state movement.

### Duplicate Function

Mark `duplicate` when two units perform the same parent contribution and downstream use without deliberate contrast, escalation, inversion, or rhythm.

When prose exists, treat duplicate function as a model-prose binding failure, not a wording similarity test. Two passages are duplicate when they bind to the same model function and create the same reader-state movement without escalation, contrast, inversion, cost, resistance, deliberate rhythm, changed interpretation, or downstream use.

Required repair actions:

- merge;
- cut one unit;
- change one unit's function;
- mark as intentional parallel with evidence.

### Terminal Treatment

Use terminal treatment when a unit does not continue downstream.

Allowed:

- `keep`: contribution and downstream use are valid.
- `revise`: unit remains but needs a specific repair.
- `cut`: remove and refresh affected rows.
- `merge`: combine with another row and refresh ids.
- `defer`: move outside current claim boundary with deferral level.
- `scoped_out`: not part of the current artifact.
- `human_review`: user must choose.

Do not leave a key or major unit as terminal without payoff, deferral boundary, or human-review decision.

## Post-Draft Contribution Review

After prose exists, contribution must be checked from the actual draft or reverse outline, not only from the plan.

For each chapter or scene, ask:

1. What did the reader learn, feel, fear, expect, or reinterpret after this unit?
2. Which later unit would weaken or break if this unit were removed?
3. Does this unit repeat a previous unit's job without escalation, contrast, inversion, cost, deliberate rhythm, or new reader-state movement?
4. Does the prose itself prove the contribution, or does a report merely claim it?

If the actual prose does not change plot state, reader state, character or relationship state, promise/payoff state, continuity, stakes, theme pressure, or pacing function, return to revise, merge, cut, or narrow the claim.

For long-form final prose, run the post-draft contribution review against model-prose binding rows:

1. Which prose span realizes this contribution?
2. Which model refs does that span bind to?
3. Which later unit depends on this exact span?
4. Does any other span bind to the same model function?
5. If so, does the later span add resistance, cost, escalation, contrast, inversion, rhythm, or changed reader interpretation?

If the answer is no, repair the model or prose by merging, cutting, compressing, or changing one unit's function. Do not solve duplicate binding by polishing both passages.

## Variation Pressure Review

Variation pressure is a contribution problem when repeated material does not change effect. It is genre-neutral and should not require a specific story carrier.

Check whether adjacent or clustered units repeat the same:

- unit function;
- information or reveal method;
- scene or location pressure;
- character action strategy;
- dialogue/exposition role;
- emotional temperature;
- chapter-ending rhythm;
- concrete carrier or image pattern without changed meaning.

Repair actions include:

- merge;
- cut;
- compress;
- change one unit's function;
- turn repetition into escalation;
- turn repetition into contrast or inversion;
- add cost or consequence;
- shift scene pressure or action strategy;
- move information from exposition into action, object, dialogue, silence, or consequence.

Purposeful repetition may pass when it creates escalation, contrast, inversion, cost, pattern recognition, deliberate rhythm, or changed reader interpretation. Record that purpose in the contribution row, reverse outline, or validation note.

Do not require genre-specific tables, clue systems, suspect roles, romantic beats, battle beats, location classes, object palettes, or fixed image systems unless the user's story or source material requires them.

## Closure Link

Long-form closure must fail or downgrade when a key or major story unit is orphan, duplicate, unsupported, stale, blocked, or human_review without accepted boundary. Optional or background units may be scoped out only when the claim boundary says they are not part of the current closure.
