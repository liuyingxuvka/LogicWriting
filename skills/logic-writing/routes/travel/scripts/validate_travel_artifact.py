#!/usr/bin/env python3
"""Validate a travel review against exact current guide spans."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _common import cli_validate, require_mapping, validation_result
from reader_pipeline import validate_route_artifact_review

OWNER = "travel-guide"
REQUIRED_DIMENSIONS = (
    "guide_kind", "traveler_fit", "unit_responsibility", "handoffs",
    "narrative_body", "operational_appendix", "risk_fallback",
    "source_recheck", "local_texture",
)


def validate_travel_artifact(value):
    request = require_mapping(value, "travel artifact review request")
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
    raise SystemExit(cli_validate(validate_travel_artifact, __doc__))
