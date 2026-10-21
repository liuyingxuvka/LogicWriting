"""Run the required finite native models once, with no nested pytest or receipt mesh."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".flowguard"))
from models.owners._native_checks import FACTORY_IDS, check_plan
from models._known_bad import run_known_bad_proofs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("full",), default="full")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    results = [check_plan(model_id) for model_id in FACTORY_IDS]
    broken = run_known_bad_proofs()
    known_bad = {name: not report.ok and bool(report.violations) for name, report in broken.items()}
    report = {"ok": all(row["ok"] for row in results) and all(known_bad.values()),
              "models": results, "known_bad": known_bad,
              "claim_boundary": "Finite state/scenario checks and actual known-bad counterexamples; no prose quality or external execution claim."}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
