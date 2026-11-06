#!/usr/bin/env python3
"""Validate an investigation review against exact current report spans."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _common import cli_validate
from derive_closure import REQUIRED_DIMENSIONS
from reader_checks import validate_artifact_review_request

OWNER = "investigation"


def validate_investigation_artifact(value):
    return validate_artifact_review_request(value, owner=OWNER,
        label="investigation artifact review request", required_dimensions=REQUIRED_DIMENSIONS[OWNER])


if __name__ == "__main__":
    raise SystemExit(cli_validate(validate_investigation_artifact, __doc__))
