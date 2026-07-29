#!/usr/bin/env python3
"""Validate an investigation review against exact current report spans."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _common import cli_validate, require_mapping, validation_result
from reader_pipeline import validate_route_artifact_review

OWNER = "investigation"
REQUIRED_DIMENSIONS = (
    "recoverable_question", "bounded_answer", "evidence_strength",
    "negative_evidence", "alternatives", "conditions", "limitations",
    "fallback_recheck", "conclusion_scope",
)


def validate_investigation_artifact(value):
    request = require_mapping(value, "investigation artifact review request")
    review = validate_route_artifact_review(
        request["review"],
        owner=OWNER,
        route_composition=request["route_composition"],
        artifact_map=request["artifact_map"],
        required_dimensions=REQUIRED_DIMENSIONS,
    )
    return validation_result(
        status="current_pass" if review["status"] == "passed" else "partial",
        route_review=review,
        findings=review["findings"],
        artifact_fingerprint=review["artifact_fingerprint"],
    )


if __name__ == "__main__":
    raise SystemExit(cli_validate(validate_investigation_artifact, __doc__))
