# Worked reader chains

Copy the folder of your route, edit the piece and the plan, then rerun.
Run from the skill root; set `route` to investigation, academic, fiction or travel.
These compact examples use honest author self-reviews, not independent quality evidence.
The eight steps (step 3 is writing; here it displays the supplied piece) are:

```sh
route=investigation
example=assets/examples/$route
python scripts/select_route.py --input "$example/route-request.json" --output "$example/route-decision.json"
python scripts/build_reader_brief.py --input "$example/brief-request.json" --output "$example/reader-brief.json"
cat "$example/piece.md" # replace with your own writing
python scripts/build_artifact_map.py --input "$example/map-request.json" --output "$example/artifact-map.json"
python scripts/validate_shared_writing.py --input "$example/shared-writing.json" --output "$example/shared-writing-result.json"
python scripts/audit_reader_output.py --input "$example/audit-request.json" --output "$example/audit.json"
python routes/$route/scripts/validate_${route}_artifact.py --input "$example/route-review.json" --output "$example/route-review-result.json"
python scripts/derive_closure.py --input "$example/closure-input.json" --output "$example/closure.json"
```

`known-bad/expected.json` names the step and code or error for each bad piece.
Replace `piece.md` in a copy with one bad piece and rerun through that step.
Never copy a passing judgment to changed prose: reread it and update its quotations.
The academic citation is Kevin Lynch, *The Image of the City* (MIT Press, 1960), chapter 3.
The travel destination is illustrative; recheck real opening hours and access.
