"""Run Logic Writing's current Model-Test Alignment review."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from flowguard import review_model_test_alignment

from model import aligned_plan, broken_missing_actual_artifact_plan


def run_checks():
    aligned = review_model_test_alignment(aligned_plan())
    broken = review_model_test_alignment(broken_missing_actual_artifact_plan())
    return aligned, broken


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    aligned, broken = run_checks()
    if args.json:
        print(
            json.dumps(
                {
                    "artifact_type": "logic_writing_model_test_alignment",
                    "schema_version": "1.0",
                    "aligned": asdict(aligned),
                    "known_bad_missing_actual_artifact": asdict(broken),
                    "claim_boundary": (
                        "This proves structural model-code-test binding and the known-bad rejection. "
                        "It does not replace the frozen validation owner's terminal test receipts."
                    ),
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(aligned.format_text())
        print()
        print(broken.format_text(max_findings=10))
    return 0 if aligned.ok and not broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
