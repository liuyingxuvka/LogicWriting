#!/usr/bin/env python3
"""Validate a travel review against exact current guide spans."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _common import cli_validate, require_mapping, validation_result
from derive_closure import REQUIRED_DIMENSIONS
from reader_fill import fill_check_fingerprints
from reader_checks import validate_route_artifact_review

OWNER = "travel-guide"


def validate_travel_artifact(value):
    request = fill_check_fingerprints(require_mapping(value, "travel artifact review request"))
    review = validate_route_artifact_review(
        request["review"],
        owner=OWNER,
        route_composition=request["route_composition"],
        artifact_map=request["artifact_map"],
        required_dimensions=REQUIRED_DIMENSIONS[OWNER],
        reader_brief=request.get("reader_brief"),
        shared_writing=request.get("shared_writing"),
    )
    return validation_result(
        status="current_pass" if review["status"] == "passed" else "partial",
        route_review=review,
        findings=review["findings"],
        artifact_fingerprint=review["artifact_fingerprint"],
    )


if __name__ == "__main__":
    raise SystemExit(cli_validate(validate_travel_artifact, __doc__))
