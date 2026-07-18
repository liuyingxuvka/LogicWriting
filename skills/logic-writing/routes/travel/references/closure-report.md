# Closure Report

Use closure reporting before final travel advice or before claiming skill development completion.

## Runtime Closure Status

- `passed`: required candidates, sources, feasibility, route traces, fallbacks, fit review, recommendation support, and story boundary are current.
- `partial`: useful but missing non-critical evidence.
- `downgraded`: output is valid only at a lower claim level.
- `blocked`: critical evidence or user constraints are missing.
- `human_review`: a meaningful user preference choice is required.
- `skipped_with_reason`: a check is out of scope and does not support a stronger claim.

## Runtime Closure Rows

```text
surface -> owner -> status -> evidence_ids -> missing_or_stale -> downgrade_or_blocker -> next_action
```

Required surfaces are traveler profile, experience candidate pool, source portfolio, negative evidence, candidate feasibility, route traces, route feasibility, lodging strategy when applicable, trip fit, recommendation support, traveler-native guide compiler, story output, reverse-guide review, and final claim boundary.

The current validator owns requested-to-allowed claim derivation and critical surface status. Far-future, past, or undated evidence cannot exceed `initial_plan`; a near-future `bookable` claim requires inspected current sources and forecast-compatible evidence; `day_of` additionally requires day-of chronology and current forecast plus alert evidence. A caller-authored `passed` value cannot override these results.

## Skill Development Closure

Skill development closure needs:

- OpenSpec artifacts complete and verified;
- FlowGuard process checks pass with shortcut counterexamples blocked;
- bundle validator pass;
- good plan validators pass;
- traveler-native text output validator pass;
- failure cases validator pass;
- Travel-owned contract and validation checks pass;
- installed-copy sync pass;
- global router resolution or refresh evidence;
- local git commit containing only relevant upgrade files.

Do not treat any skipped, failed, stale, unrelated, or progress-only evidence as passed.
