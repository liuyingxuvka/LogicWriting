# Public claim-reading seeds

Portable, reduced inputs from the Round 14 LogicWriting prototype public seeds. `cases.json` keeps the original request, AI-owned prose/meaning, citation/model bindings and expected red/no-red result; `originals/` holds unchanged captured documents and the two saved PhysicsGuard results with their input files. These are public regression examples, not a new blind test.

The first eight cases are the original shipped example without/with captures, the three detected slips, the same-range/different-fact known miss, and two heater notes. The later 29 are `SEEDS` and formerly held-out `HELDOUT` from `make_fresh_seeds.py`. Known misses remain explicit: swapped years, names outside quotations, and “half” without a unit. The derived ferry duration remains red without a linked computed result. No source summary is accepted as a saved original.

Each case also keeps the exact green/red/grey reading counts and exit status recorded by the revised v1 prototype: the first eight from `新种子/public_rerun_new.txt`, the later 29 from the final column of `新种子/seed_table.md`. Tests compare all three counts, including the grey and known-miss controls.
