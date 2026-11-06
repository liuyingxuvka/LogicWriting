#!/usr/bin/env python3
"""Validate a travel review against exact current guide spans."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _common import cli_validate
from derive_closure import REQUIRED_DIMENSIONS
from reader_checks import validate_artifact_review_request

OWNER = "travel-guide"


def validate_travel_artifact(value):
    return validate_artifact_review_request(value, owner=OWNER,
        label="travel artifact review request", required_dimensions=REQUIRED_DIMENSIONS[OWNER])


if __name__ == "__main__":
    raise SystemExit(cli_validate(validate_travel_artifact, __doc__))
