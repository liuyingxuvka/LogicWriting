from __future__ import annotations

import argparse
import json
from pathlib import Path

from travel_contract import review_plan_file, validate_composition_refs, issue


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate one current Travel Story Planner plan.")
    parser.add_argument("plan")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--composition", help="travel route composition JSON whose ids must exist in the plan")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    plan_path = Path(args.plan)
    derived = review_plan_file(plan_path, repository_root=Path(args.repository_root))
    issues = list(derived["issues"])
    if args.composition and not issues:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        composition = json.loads(Path(args.composition).read_text(encoding="utf-8"))
        reference = composition.get("trip_plan")
        if not isinstance(reference, str) or not reference:
            issues.append(issue("travel_composition.trip_plan.missing", "Travel composition requires trip_plan."))
        elif (Path(args.composition).parent / reference).resolve() != plan_path.resolve():
            issues.append(issue("travel_composition.trip_plan.mismatch", "Composition trip_plan must identify the plan being validated."))
        issues.extend(validate_composition_refs(plan, composition))
    result = {"ok": not issues, "plan": str(plan_path), "issues": issues,
              "allowed_claim_level": derived.get("allowed_claim_level", "initial_plan"),
              "allowed_claim_reason": derived.get("allowed_claim_reason", "unavailable_plan"),
              "derived": derived.get("derived", {})}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("pass" if result["ok"] else "fail")
        for row in issues:
            print(f"- {row['code']}: {row['message']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
