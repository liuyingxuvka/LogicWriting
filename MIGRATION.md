# Migration to Logic Writing 2.0

Version `2.0.0` keeps one public skill id, `logic-writing`, and expands the
internal final-owner set from two routes to four. It directly replaces the
separately installed Storyline Design and Travel Story Planner skills. There
are no runtime compatibility aliases or fallback launchers.

## Intent mapping

| Previous public skill or route | New invocation | Final owner |
| --- | --- | --- |
| Logic Writing investigation | `$logic-writing` | `investigation` |
| Logic Writing academic writing | `$logic-writing` | `academic-writing` |
| `storyline-design` / Storyline Design | `$logic-writing` | `fiction-writing` |
| `travel-story-planner` / Travel Story Planner | `$logic-writing` | `travel-guide` |

The router chooses from the terminal deliverable. Research, source intake,
world checks, traces, document mutation, or reader projection do not transfer
final ownership.

## What was preserved

Fiction preserves compact, short-story, long-form, and final-manuscript depth;
story contribution, turning points, scene/chapter interfaces, promises,
continuity, voice, Guard lifecycle, model mesh, real manuscript identity,
semantic review, and model-prose binding.

Travel preserves traveler profile, source portfolio, dated weather/alert
modes, candidates, WorldGuard feasibility, TraceGuard route mesh, lodging,
traveler fit, recommendation support, negative evidence, reachable fallbacks,
traveler-native guide compilation, actual-artifact hash, and reverse-guide
closure.

Investigation and academic writing keep their existing evidence, citation,
revision-provenance, Documents, PDF, and final-owner gates, while gaining the
shared reader-state and model-artifact contract.

## What changed

- Travel's former Storyline Design projection dependency is now the neutral
  shared reader projection. Travel does not call the fiction route.
- WorldGuard is a first-class native adapter for both real and fictional world
  consistency.
- The shared writing contract checks concrete contribution, reader-state
  movement, explanation pressure, specific handoff, register ownership,
  effect-aware variation, exact artifact identity, and model-span binding.
- FlowGuard now has disjoint fiction and travel children plus Travel-first,
  Storyline-second retirement order.
- SkillGuard's sole current contract declares all four routes and their shared
  kernel.

## Installation cutover

1. Validate and release the exact `2.0.0` source snapshot.
2. Stage and activate `skills/logic-writing` transactionally.
3. Refresh the global router and confirm all four supported intent families
   resolve to `logic-writing`.
4. Move active `storyline-design` and `travel-story-planner` directories to a
   recoverable quarantine outside the active skill root.
5. Run installed behavior and content-parity checks.
6. Verify a fresh anonymous clone and fresh installation of `LogicWriting`.
7. Make `travel-story-planner` private and verify replacement health.
8. Make `storyline-design-skill` private and verify replacement health again.

Repository deletion is not part of the automated migration. The user may
delete the private predecessor repositories later.

## Existing user material

Papers, notes, story ledgers, manuscripts, travel plans, and guides may still be
supplied as source material. Their old runtime receipts, completion flags,
manifests, or installation identities do not count as current Logic Writing
evidence. Import the material, recompute current artifact identities, and run
the selected route's current contracts.

Internal legacy schema strings retained inside frozen regression fixtures are
historical test identities only. They are not installable skill ids, public
routes, aliases, or alternate success paths.

## Rollback

Before each destructive-looking cutover step, preserve the prior active
installation and predecessor source bundles. If installation, global routing,
fresh-clone verification, privacy proof, or replacement health fails, stop the
sequence and restore the last changed visibility or installation state. Never
continue to the second repository after a failed first-repository health check.
