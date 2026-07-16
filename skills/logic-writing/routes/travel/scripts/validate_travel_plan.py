from __future__ import annotations

import argparse
import json
from pathlib import Path

from travel_contract import validate_plan_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate one current Travel Story Planner plan.")
    parser.add_argument("plan")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    plan_path = Path(args.plan)
    issues = validate_plan_file(plan_path, repository_root=Path(args.repository_root))
    result = {"ok": not issues, "plan": str(plan_path), "issues": issues}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("pass" if result["ok"] else "fail")
        for row in issues:
            print(f"- {row['code']}: {row['message']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
