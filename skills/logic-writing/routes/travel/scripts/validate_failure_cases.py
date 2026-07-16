from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fixture_mutation import MutationError, apply_mutations
from travel_contract import validate_plan


CASE_SCHEMA = "travel-story-planner.failure-case.v2"


def run_case(path: Path, repository_root: Path) -> dict[str, Any]:
    try:
        case = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"case": str(path), "ok": False, "error": f"case_invalid:{exc}"}
    if not isinstance(case, dict) or case.get("schema_version") != CASE_SCHEMA:
        return {"case": str(path), "ok": False, "error": "case_schema_invalid"}
    expected = case.get("expected_issue_codes")
    if not isinstance(expected, list) or not expected or any(not isinstance(code, str) or not code for code in expected):
        return {"case": str(path), "ok": False, "error": "expected_issue_codes_invalid"}
    base_path = (repository_root / str(case.get("base_plan", ""))).resolve()
    try:
        base = json.loads(base_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"case": str(path), "ok": False, "error": f"base_invalid:{exc}"}
    base_issues = validate_plan(base, plan_path=base_path, repository_root=repository_root)
    if base_issues:
        return {"case": str(path), "ok": False, "error": "base_not_current", "base_issues": base_issues}
    try:
        mutated = apply_mutations(base, case.get("mutations", []))
    except MutationError as exc:
        return {"case": str(path), "ok": False, "error": f"mutation_invalid:{exc}"}
    issues = validate_plan(mutated, plan_path=path, repository_root=repository_root)
    actual = sorted({row["code"] for row in issues})
    expected_codes = sorted(set(expected))
    return {
        "case": str(path),
        "case_id": case.get("case_id"),
        "ok": actual == expected_codes,
        "expected_issue_codes": expected_codes,
        "actual_issue_codes": actual,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run exact current Travel failure mutations.")
    parser.add_argument("--cases-dir", required=True)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.repository_root).resolve()
    paths = sorted(Path(args.cases_dir).glob("*.json"))
    results = [run_case(path, root) for path in paths]
    result = {"ok": bool(results) and all(row.get("ok") for row in results), "case_count": len(results), "results": results}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("pass" if result["ok"] else "fail")
        for row in results:
            print(f"- {row.get('case_id', row['case'])}: {'pass' if row.get('ok') else 'fail'}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
