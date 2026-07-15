"""Evaluate Logic Writing's target-owned deep/shallow calibration pair.

This is a source-level capability gate.  It proves that the native contract
inventory accepts a representative complete case and detects one exact
important omission.  It is not a production execution-depth receipt.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


IMPORTANT_OBLIGATIONS = (
    "obligation:logic-writing:routing",
    "obligation:logic-writing:specialist-authority",
    "obligation:logic-writing:investigation-evidence",
    "obligation:logic-writing:academic-provenance",
    "obligation:logic-writing:reader-actual-artifact",
    "obligation:logic-writing:final-closure",
    "obligation:logic-writing:release-integrity",
)
REQUIRED_CAPABILITIES = (
    "capability:one-entry-two-routes",
    "capability:typed-specialist-receipts",
    "capability:reader-brief-boundary",
    "capability:actual-artifact-audit",
    "capability:minimum-content-closure",
)
EXPECTED_SHALLOW_OMISSION = "obligation:logic-writing:reader-actual-artifact"


def _load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"JSON object required: {path}")
    forbidden = {
        "expected_status",
        "expected_blocker_code",
        "observed_status",
        "observed_blocker_code",
    }
    if forbidden.intersection(value):
        raise ValueError("fixtures may describe evidence, not expected or observed outcomes")
    return value


def evaluate(value: Mapping[str, Any]) -> dict[str, Any]:
    obligations = tuple(str(item) for item in value.get("covered_obligation_ids", ()))
    capabilities = tuple(str(item) for item in value.get("capability_ids", ()))
    missing_obligations = tuple(item for item in IMPORTANT_OBLIGATIONS if item not in obligations)
    missing_capabilities = tuple(item for item in REQUIRED_CAPABILITIES if item not in capabilities)
    extra_obligations = tuple(item for item in obligations if item not in IMPORTANT_OBLIGATIONS)
    duplicate_obligations = len(obligations) != len(set(obligations))
    if duplicate_obligations or extra_obligations or missing_capabilities:
        return {
            "status": "SHALLOW_BLOCKED",
            "blocker_code": "invalid_calibration_universe",
            "missing_obligation_ids": list(missing_obligations),
            "missing_capability_ids": list(missing_capabilities),
        }
    if missing_obligations:
        return {
            "status": "SHALLOW_BLOCKED",
            "blocker_code": "important_obligation_missing",
            "missing_obligation_ids": list(missing_obligations),
            "missing_capability_ids": [],
        }
    return {
        "status": "CONTRACT_DEPTH_PASS",
        "blocker_code": "none",
        "missing_obligation_ids": [],
        "missing_capability_ids": [],
    }


def validate_pair(positive_path: Path, shallow_path: Path) -> dict[str, Any]:
    positive = evaluate(_load(positive_path))
    shallow = evaluate(_load(shallow_path))
    ok = (
        positive["status"] == "CONTRACT_DEPTH_PASS"
        and shallow["status"] == "SHALLOW_BLOCKED"
        and shallow["blocker_code"] == "important_obligation_missing"
        and shallow["missing_obligation_ids"] == [EXPECTED_SHALLOW_OMISSION]
    )
    return {
        "artifact_type": "logic_writing_contract_calibration_result",
        "schema_version": "1.0",
        "ok": ok,
        "positive": positive,
        "shallow": shallow,
        "claim_boundary": (
            "Source-level calibration only; this does not prove a production run "
            "or SkillGuard EXECUTION_DEPTH_PASS."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--positive", type=Path, required=True)
    parser.add_argument("--shallow", type=Path, required=True)
    args = parser.parse_args()
    result = validate_pair(args.positive, args.shallow)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
