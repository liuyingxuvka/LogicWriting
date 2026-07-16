# Prose Native Contract

Use this reference when a StorylineDesign task needs to turn checked scene cards into reader-facing prose without leaking workflow labels. The prose-native contract protects two boundaries at once: prose must be grounded in the current story model, and prose must read like story text rather than exposing ledger rows, workflow labels, validation status, or review jargon to the reader.

Prose is a model-first output of checked scene cards, not a substitute for scene, promise, structure, or WorldGuard validation.

## Boundary

StorylineDesign owns the projection from model artifacts into native prose:

- scene card intent, entry state, exit state, conflict, desire, obstacle, turn, and closure effect;
- promise/payoff expectations and payoff evidence;
- structure-turning-points roles and pressure movement;
- WorldGuard evidence status for generic world claims;
- reader-facing voice, point of view, continuity, pacing, imagery, and dialogue choices.

The reader-facing prose must not leak internal workflow labels such as `scene_contract`, `contract_outcome`, `worldguard_status`, `closure_effect`, `return_to_ledger`, `human_review`, `prose_allowed`, validation ids, evidence refs, ledger ids, route node ids, packet ids, or checklist language.

Internal notes may mention those fields only in planning, audit, review, or revision reports. They do not belong inside final story prose unless the user explicitly asks for a mixed planning/prose artifact.

## Input Readiness

Generate complete scene prose only from approved scene cards. A scene card is ready for prose when:

- the card has `entry_state`, `exit_state`, `irreversible_change`, `conflict_pressure`, `character_desire`, `obstacle`, and `turning_point`;
- `contract_outcome` is `keep`, or `revise` with a narrowed drafting boundary;
- parent structure and turning-point rows are current enough for the requested artifact;
- key promise/payoff rows touched by the scene are paid, planned, inverted, deferred, abandoned_with_reason, or visibly narrowed;
- required WorldGuard claims are pass, scoped out, or explicitly marked as gaps that the prose must not hide;
- workflow gate state allows drafting inside the current claim boundary.

Do not draft complete prose directly from user intent, a rough outline, or an attractive premise when required scene cards or model checks are missing. Produce a planning artifact, scene card, or blocker instead.

## Projection Row Shape

Record prose projections in a ledger `validation` row or a linked `prose_projection` section.

```json
{
  "id": "prose-projection-scene-006",
  "kind": "prose_projection",
  "source_scene_id": "scene-006",
  "source_scene_card_version": "scene-006:v3",
  "projection_scope": "single_scene",
  "reader_visibility": "reader_native",
  "allowed_model_inputs": [
    "scene_contract",
    "structure_turning_point",
    "promise_payoff",
    "worldguard_claim",
    "support"
  ],
  "blocked_internal_terms": [
    "scene_contract",
    "worldguard_status",
    "closure_effect",
    "human_review"
  ],
  "voice_contract": {
    "point_of_view": "limited_third",
    "tense": "past",
    "style_notes": "urgent but controlled"
  },
  "continuity_requirements": [
    "The archive door is locked before the scene starts.",
    "The protagonist does not know the rival planted the clue until the reveal."
  ],
  "promise_requirements": [
    "Escalate promise-map-race without paying it yet."
  ],
  "world_claim_requirements": [
    "wg-claim-archive-access"
  ],
  "prose_status": "drafted",
  "projection_result": "ready_for_review",
  "evidence_refs": []
}
```

Required fields:

- `id`: stable prose projection id.
- `kind`: `prose_projection`.
- `source_scene_id`: source scene card.
- `source_scene_card_version`: current scene card version or evidence id.
- `projection_scope`: beat, scene, chapter, sequence, sample, outline_excerpt, or full_story.
- `reader_visibility`: reader_native, mixed, planning, or audit.
- `allowed_model_inputs`: model surfaces the prose may consume.
- `blocked_internal_terms`: terms that must not appear in reader-native prose.
- `voice_contract`: point of view, tense, style notes, and any user constraints.
- `continuity_requirements`: facts that must remain true in prose.
- `promise_requirements`: promise/payoff obligations the prose must preserve.
- `world_claim_requirements`: WorldGuard claim rows the prose depends on.
- `prose_status`: not_started, sample_only, drafted, revised, final_candidate, blocked, or human_review.
- `projection_result`: ready_for_review, return_to_scene, return_to_promises, return_to_structure, return_to_worldguard, return_to_revision, user_decision, or scoped_out.

## Native Prose Rules

Reader-native prose should:

- show scene state through action, perception, dialogue, description, and consequence;
- express the scene's desire, obstacle, conflict, and turn as lived experience rather than checklist labels;
- preserve setup/payoff expectations without naming them as promise rows;
- preserve world facts without citing WorldGuard status;
- keep prose consistent with the current point of view, tense, genre, tone, and user constraints;
- avoid bracketed implementation notes, validation notes, unresolved TODOs, and model-field names.

Reader-native prose should not:

- name workflow stages such as intake, ledger, structure, scenes, WorldGuard checks, outline, draft, review, revision, or closure;
- expose field names such as `entry_state`, `exit_state`, `irreversible_change`, `promise_links`, or `worldguard_claim_links`;
- say that a scene is `keep`, `revise`, `cut`, `human_review`, `blocked`, `stale`, or `unsupported`;
- turn validation evidence into dialogue or narration;
- claim final closure when the model only supports a sample, partial draft, or narrowed scene.

## Model Link Checks

### Model-Prose Binding Link

Reader-native prose is not complete merely because it avoids workflow labels. For long-form final prose or major revision claims, important prose spans must bind back to model rows, and key or major model rows must bind forward to actual prose.

Return to the model room when:

- a prose span changes pacing, reader attention, plot state, character state, object state, promise state, or theme pressure but has no model row or scoped reason;
- a key or major model row has no prose evidence;
- two prose spans bind to the same model function without escalation, contrast, inversion, cost, resistance, deliberate rhythm, changed reader interpretation, or downstream use;
- a chapter is much longer or shorter than its neighbors and no binding-density review explains whether the length carries distinct functions;
- a reveal, discovery, relationship turn, or payoff advances without resistance, cost, counter-interpretation, obstacle, delay, consequence, or scoped rhythm;
- important terms drift between narrator, document, profession, institution, local usage, and character speech without register ownership.

This is a semantic binding rule, not a genre-specific schema. Do not require suspect tables, clue matrices, romance beats, battle beats, magic-rule tables, fixed locations, object palettes, or motif lists unless the user's story requires them.

### Scene Contract Link

Before prose projection, confirm the source scene card is current.

Return to scene contracts when:

- the source scene has no contract;
- entry state, exit state, irreversible change, conflict, desire, obstacle, or turn is missing;
- prose changes the scene's function without updating the scene card;
- a `revise`, `cut`, or `human_review` scene is drafted as if it were closed.

### Promise Payoff Link

Before prose projection, confirm the prose does not hide promise state.

Return to promise/payoff review when:

- prose opens a new key promise without a ledger row;
- prose pays a promise differently than the promise record says;
- prose treats open, partial, blocked, stale, unsupported, or human_review promises as resolved;
- prose uses an inversion without setup evidence;
- prose abandons a promise without an accepted reason and boundary.

### Structure-Turning-Points Link

Before prose projection, confirm the scene's structure role.

Return to structure when:

- prose moves a scene to a different setup, reaction, attack, climax, or resolution function without updating structure rows;
- prose adds a turning point that is not recorded;
- prose removes the pressure movement required by the current structure row;
- prose claims parent structure closure from a local scene pass alone.

### WorldGuard Link

Before prose projection, confirm world-claim boundaries.

Return to WorldGuard when:

- prose depends on event order, causality, agent capability, access, resources, conflict, norms, or authority that is not mapped or checked when world consistency matters;
- prose hides a non-pass, stale, forbidden, boundary, authority, or missing-handoff WorldGuard finding;
- prose adds a new world fact that invalidates current WorldGuard evidence.

WorldGuard evidence can support whether a world claim is consistent. It does not choose voice, imagery, emotional intensity, theme, or aesthetic quality.

### Workflow Gate Link

Before drafting:

1. Confirm scene card readiness.
2. Confirm structure, promise/payoff, support, and WorldGuard links are current or narrowed.
3. Confirm the requested artifact scope allows prose.
4. Set a prose boundary: sample, scene, chapter, sequence, or final_candidate.

Before review:

1. Compare prose against the source scene card and linked model rows.
2. Flag invented facts, hidden promises, missing payoff, changed turn, stale WorldGuard claims, and workflow label leakage.
3. Assign ready_for_review, return_to_scene, return_to_promises, return_to_structure, return_to_worldguard, return_to_revision, or user_decision.

Before final revision or closure:

1. Recheck affected scene cards after prose changes.
2. Recheck affected promises, structure turns, support rows, and WorldGuard claims.
3. Remove workflow labels from reader-native prose.
4. Preserve the claim boundary when any linked row remains partial, blocked, stale, unsupported, skipped, or human_review.

## Leakage Guard

Treat these as hard reader-native prose failures unless the artifact is explicitly mixed planning/prose:

- visible JSON, YAML, table columns, ids, or validation refs;
- labels such as "Scene Contract", "WorldGuard", "ledger", "closure", "promise payoff", or "human review";
- status language such as pass, blocked, stale, unsupported, not_run, or scoped_out;
- comments telling the reader what the scene should accomplish;
- bracketed instructions such as `[pay off promise]` or `[WorldGuard gap]`;
- meta narration that explains the workflow instead of dramatizing the story.

When leakage appears, return to revision or regenerate the prose from the approved scene card.

## Reader-Room Contamination

Reader-native prose fails when it exposes author-facing or workflow-facing language that is not justified by the story-world form.

High-risk contamination includes:

- "this chapter" when it explains chapter function rather than appearing as a legitimate title, quotation, or fictional device;
- "next chapter" when it forecasts author plan rather than a story-world object or utterance;
- "this batch" or "next batch";
- "the real task now is" when it describes author work rather than character pressure;
- "the chapter ends by";
- "the midpoint turn is";
- "the next step is";
- "the answer must pass through" when used as planning logic rather than character speech grounded in scene.

These are not regex-banned phrases. They are allowed when the fictional form itself justifies them, such as metafiction, a character writing a chapter plan, a visible document inside the story, a chapter title, or a mixed planning/prose artifact explicitly requested by the user.

Otherwise, rewrite reader-room contamination as:

- a character action;
- a concrete object;
- a sensory detail;
- a decision;
- a withheld fact;
- a pressure entering the scene;
- a visible consequence;
- silence, contradiction, or incomplete dialogue.

## Explanation Pressure

Reader-native prose should not repeatedly explain what the scene should make the reader feel, infer, or judge when action, object, dialogue, perception, silence, contradiction, or consequence can carry the meaning.

Return to prose projection, scene contracts, promise/payoff, or voice/style when:

- the narrator states the meaning of a clue, relationship beat, world rule, or theme before the scene earns it;
- a paragraph only explains what the chapter has accomplished;
- dialogue delivers clean thematic summary instead of character desire, fear, evasion, status, or conflict;
- a chapter ending repeatedly relies on philosophical or structural summary rather than story-world pressure.

## Variation Clean Pass

Variation pressure is sameness without changed effect. It is not a demand for random variety.

During the clean pass, check whether actual prose repeatedly uses the same:

- character voice or author-summary diction;
- scene or location pressure;
- event function;
- information or reveal method;
- emotional temperature;
- paragraph or chapter-ending rhythm;
- concrete carrier or image pattern without new meaning;
- reader-state movement.

Repetition may pass when it creates escalation, contrast, inversion, cost, deliberate rhythm, pattern recognition, or changed reader interpretation. If it does not, return to story contribution, scene contract, chapter interface, promise/payoff, or voice/style instead of polishing sentences.

Variation review is genre-neutral. Do not require any manuscript to use another story's profession, plot structure, place type, object family, clue system, or image set.

## Minimal Prose Projection Checklist

Before delivering reader-native prose, answer:

1. Which scene card or approved model rows are the source?
2. What prose scope is allowed?
3. What point of view, tense, tone, and user constraints apply?
4. Which scene contract fields must be dramatized?
5. Which promises must be preserved, paid, inverted, deferred, or left open?
6. Which structure turn or pressure movement must remain visible?
7. Which WorldGuard claims constrain the prose?
8. Which internal labels are forbidden in reader-facing text?
9. Does the prose introduce unsupported facts or new promises?
10. Does the prose stay inside the current closure boundary?

Do not claim prose is final when these answers are missing. Return to the earliest failed model surface, or deliver a visibly narrowed sample when that is the supported artifact.

## Longform Two-Room Prose Compiler

For long-form chapters, keep two rooms separate:

- Model room: novel ledger, story contribution, chapter interface, scene cards, promises, continuity, voice/style report, and WorldGuard evidence.
- Reader room: final chapter prose that contains only story-facing language.

Before drafting a chapter, prepare a reader-native chapter brief from the model room:

- current chapter input;
- reader state before;
- focal desire, pressure, and cost;
- required promise movement;
- voice/style constraints;
- chapter exit state and unresolved tension.

After drafting, run reader-room and variation clean passes before reverse outline. Then create a reverse outline from the actual prose and build model-prose binding evidence from the same draft. Compare both to the chapter interface and prose blueprint. If the reverse outline or binding surface shows invented facts, missing promise movement, broken reader-state handoff, reader-room contamination, unbound prose, unrealized model rows, duplicate binding, missing resistance/friction, premature reader-state collapse, register ownership drift, explanation pressure, variation pressure, or voice/style drift, return to the model room before revising prose.

Do not claim chapter closure from attractive prose alone. Long-form prose needs reverse-outline evidence, and final long-form prose needs model-prose binding evidence, before aggregate closure can consume it.
