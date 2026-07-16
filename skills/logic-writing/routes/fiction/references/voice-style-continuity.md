# Voice And Style Continuity

Use this reference when Longform Mode needs to keep a novel's narration coherent across chapters, viewpoints, timelines, or revision rounds. Voice/style checks do not decide whether prose is beautiful; they decide whether the requested continuity claim is supported.

## Voice Contract

Record a voice/style contract:

```json
{
  "id": "voice-contract",
  "pov_policy": "limited_third",
  "tense_policy": "past",
  "narration_distance": "close",
  "diction": "precise, tactile, low ornament",
  "sentence_rhythm": "varied but controlled",
  "dialogue_policy": "subtext over exposition",
  "exposition_policy": "embed through action and consequence",
  "pacing_policy": "chapter endings carry unresolved pressure",
  "allowed_variation": ["dream fragments may become more lyrical"],
  "blocked_variation": ["no sudden omniscient explanation"],
  "status": "pass"
}
```

Required fields:

- `id`, `pov_policy`, `tense_policy`, `narration_distance`, `diction`, `sentence_rhythm`, `dialogue_policy`, `exposition_policy`, `pacing_policy`, `allowed_variation`, `blocked_variation`, and `status`.

## Continuity Report

Record per-chapter or per-section checks:

```json
{
  "id": "voice-report-ch03",
  "chapter_id": "chapter-03",
  "contract_ref": "voice-contract",
  "checks": [
    {"field": "pov", "status": "pass", "finding": "No head-hop."},
    {"field": "tense", "status": "pass", "finding": "Past tense stable."}
  ],
  "drift": [],
  "repair_actions": [],
  "overall_status": "pass"
}
```

Required fields:

- `id`, `contract_ref`, `checks`, `drift`, `repair_actions`, and `overall_status`.

Each check uses:

- `field`: pov, tense, narration_distance, diction, rhythm, dialogue, exposition, pacing, cadence, emotional_temperature, or register.
- `status`: pass, partial, drift, blocked, stale, scoped_out, or human_review.
- `finding`: concise evidence-backed note.

## Drift Handling

Classify drift:

- `allowed_variation`: intentional and supported by the contract.
- `minor_drift`: repairable without changing the model claim.
- `blocking_drift`: prevents the requested prose or closure claim.
- `human_review`: subjective voice choice that changes the book's effect.

Required repair action fields:

- `field`;
- `affected_chapters`;
- `repair_type`: revise_prose, update_contract, narrow_claim, or human_review;
- `status`.

## Character Voice Distinction

Voice/style review must include character voice distinction when dialogue, interiority, or multi-character prose is in scope.

For each major character, identify the likely source of voice:

- status, role, age, profession, culture, family, institution, or social position;
- desire, fear, shame, ambition, grief, or self-protection;
- knowledge boundary: what the character knows, refuses to know, or cannot safely say;
- relationship pressure: who they are speaking to and what power is at stake;
- evasion style: silence, joke, precision, vagueness, deflection, over-explanation, command, apology, or contradiction.

Characters may share vocabulary because they share a profession, institution, family, period, culture, or genre register. Shared vocabulary is not failure by itself. It becomes drift when major characters repeatedly speak in the same abstract, author-like summary voice without character-specific pressure, knowledge boundary, or phrasing.

## Explanation Pressure And Dialogue Distinction

Voice/style review must include explanation pressure.

Check whether:

- exposition explains what the scene should make the reader feel or infer;
- multiple characters speak in the same abstract, author-like summary voice;
- dialogue delivers theme instead of character desire, fear, evasion, status, or conflict;
- chapter endings repeatedly use philosophical or structural summary;
- the narrator states the meaning of a fact, relationship beat, clue, world rule, or theme before the scene has made it felt.

Repair by moving meaning into:

- action;
- object handling;
- incomplete dialogue;
- silence;
- contradiction;
- physical or social consequence;
- character-specific word choice.

## Purposeful Voice And Rhythm Variation

Variation in voice, rhythm, register, and exposition should serve story effect. Do not add decorative quirks, catchphrases, dialect markers, or sensory detail merely to look varied.

Pass purposeful variation when it changes pressure, desire, relation, reader interpretation, pacing, or emotional temperature.

Return to voice/style, scene contract, or story contribution when variation is decorative only, or when sameness is not supported as deliberate repetition.

## Register Ownership And Term Drift

Voice/style review must include register ownership when important terms, repeated objects, professional language, document language, local usage, or specialized vocabulary affect the prose.

For each important term or register level, identify the likely owner:

- narrator;
- focal character;
- another character;
- profession or institution;
- document, report, inscription, record, message, or quotation;
- local, family, period, cultural, or story-world usage.

Shared vocabulary is allowed when characters share a profession, institution, family, era, culture, or story setting. It becomes drift when a term appears in a speaker, narrator distance, or document form that the model does not support.

Repair register drift by changing the speaker's wording, moving the term into narration or a document, adding story-world support, or updating the voice/style contract. Do not use global replacement as a substitute for ownership review.

## Longform Closure Link

Chapter closure may pass with no blocking voice/style drift for that chapter. Volume, book, or series closure requires all in-scope chapters to have current voice/style reports or explicit scoped-out boundaries.

Do not let a strong local scene or chapter compensate for unresolved POV, tense, exposition, or cadence drift that affects the stated closure level.
