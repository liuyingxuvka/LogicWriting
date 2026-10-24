# Chapter Interface And Prose Blueprint

Use this reference when Longform Mode needs to bind chapters together, draft chapter prose, or verify that drafted prose still matches the planned chapter sequence.

## Chapter Interface Shape

Record interfaces in `chapter_interfaces` or a standalone JSON artifact:

```json
{
  "id": "iface-ch03",
  "previous_output": "The protagonist realizes the archive key belongs to the rival.",
  "current_input": "She enters chapter 3 with proof of the rival's access but no safe way to confront him.",
  "promise_movements": [
    {
      "promise_id": "promise-map-race",
      "role": "escalation"
    }
  ],
  "arc_movements": [
    {
      "arc_id": "arc-agency",
      "movement": "chooses risk instead of waiting"
    }
  ],
  "hook_role": "pressure_forward",
  "evidence_refs": [
    "reverse-outline.json#chapter-03"
  ],
  "planned_unit_id": "chapter-03"
}
```

Required domain fields are `id`, `planned_unit_id`, previous output/current
input, promise and arc movements, hook role and evidence references. Read
adjacency, reader states and open questions from the canonical unit plan.
Prose blueprints and reverse outlines also point through `planned_unit_id`;
there is no copied chapter tree, status or model-alignment declaration.

Generic handoffs such as "continues the story" or "sets up the next chapter" are not enough. The interface must name what changed and what the reader carries forward.

## Prose Blueprint Shape

A chapter prose blueprint translates model rows into reader-native writing instructions without leaking workflow labels into final prose:

```json
{
  "id": "blueprint-ch03",
  "source_interface_id": "iface-ch03",
  "prose_scope": "chapter",
  "pov": "limited_third",
  "tense": "past",
  "required_reader_experience": [
    "pressure",
    "choice",
    "cost"
  ],
  "must_include": [
    "archive key",
    "public exposure",
    "rival's warning"
  ],
  "must_not_include": [
    "the map's true location"
  ],
  "voice_style_refs": [
    "voice-style-report.json#voice-contract"
  ],
  "planned_unit_id": "chapter-03"
}
```

Required fields: `id`, `planned_unit_id`, `source_interface_id`, `prose_scope`, `pov`, `tense`, `scene_order`, `required_reader_experience`, `must_include`, `must_not_include`, `voice_style_refs`, and `status`.

## Reader-Native Brief

When handing the model to prose generation, use a reader-native brief:

- what the chapter should feel like to the reader;
- what the focal character wants and fears;
- what changes by the end;
- which questions stay open;
- what voice/style constraints matter.

Do not include field names, ids, validation statuses, or checklist language in the final prose.

## Story-World Chapter Ending

A chapter interface may describe what the next chapter must inherit, but final prose must not explain the chapter's function or forecast the next chapter from an author-facing position.

A reader-native chapter ending should land on one of:

- an action;
- a concrete object;
- a character reaction;
- a choice;
- a new pressure;
- a sensory image;
- an unresolved story-world fact;
- a consequence that changes the reader's expectation.

If the ending says what the chapter accomplished, what the next chapter will do, or how the structure has turned, return to prose projection and rewrite the ending inside the story world.

## Chapter Rhythm And Variation

Chapter interface review should include variation pressure when prose exists or chapter prose is being planned. Record rhythm and variation notes in the interface, prose blueprint, reverse outline, or validation row rather than adding mandatory top-level schema fields.

Check whether adjacent or clustered chapters repeat the same:

- opening movement;
- information path;
- dominant scene or location pressure;
- event function;
- explanation mode;
- emotional temperature;
- ending rhythm;
- reader-state change.

Repetition is acceptable when it creates escalation, contrast, inversion, cost, deliberate rhythm, or changed reader interpretation. Unsupported sameness should return to story contribution, chapter interface, voice/style, or prose projection.

## Reverse Outline Shape

After prose exists, create a reverse outline from the actual drafted chapter:

```json
{
  "id": "reverse-ch03",
  "source_draft_ref": "drafts/chapter-03.md",
  "observed_events": [],
  "observed_reader_state_after": [],
  "observed_promise_movements": [],
  "observed_arc_movements": [],
  "shared_writing_refs": [],
  "binding_drift": [],
  "drift": [],
  "planned_unit_id": "chapter-03"
}
```

Closure can consume prose only after reverse outline evidence shows whether the actual chapter matched the planned interface and prose blueprint.

Reverse outlines should also record reader-facing drift such as reader-room contamination, authorial chapter-function explanation, unsupported or premature reveal, repeated chapter contribution, weak SharedWriting quote binding, unbound prose spans, unrealized model rows, duplicate binding, missing resistance/friction, premature reader-state collapse, register ownership drift, explanation pressure, variation pressure, or dialogue collapsing into one author voice.

Reverse outlines must include `observed_events`, `observed_reader_state_after`, `observed_promise_movements`, and `observed_arc_movements`. A broad chapter summary, prose excerpt, or validation label is shallow evidence and cannot replace event-and-state rows from the actual draft.

When final prose or major revision is in scope, reverse outlines should point to SharedWriting span evidence through `shared_writing_refs` or an equivalent validation row. Unresolved `binding_drift` blocks positive chapter-interface validation.

## Model-Prose Binding And Length Outliers

Chapter interface review should treat SharedWriting quote binding as the bridge between planned chapter function and actual manuscript text.

Check:

- which model rows each important prose span realizes;
- which key or major model rows are missing from prose;
- whether repeated spans bind to the same function without changed reader state, cost, resistance, contrast, inversion, rhythm, or downstream use;
- whether a long or short chapter is justified by distinct binding rows or is only repeating the same function.

Length is not a hard pass/fail metric. It triggers review. A long chapter may pass when its binding rows carry distinct story functions and transitions.

## Failure Conditions

Return to chapter interface or prose revision when:

- adjacent handoff is missing or generic;
- reader state before/after is missing;
- unresolved tension disappears without payoff;
- promise movement contradicts the novel ledger;
- prose blueprint bypasses voice/style constraints;
- reverse outline shows events, promises, or reader state that the model did not support;
- SharedWriting quote binding is missing, stale, or shows unresolved binding drift for a final-prose claim;
- reader-native prose ending explains chapter function or forecasts the next chapter from an author-facing position;
- adjacent chapter rhythm or function repeats without purposeful escalation, contrast, inversion, cost, or changed reader interpretation.
