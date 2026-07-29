#!/usr/bin/env python3
"""Build the current byte-level ArtifactMap for a fiction manuscript."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _common import cli_validate, require_mapping, validation_result
from reader_pipeline import build_artifact_map


def build_manuscript_artifact_map(value):
    request = require_mapping(value, "fiction artifact-map request")
    amap = build_artifact_map(
        request["artifact_path"],
        map_id=request["map_id"],
        language=request["language"],
        artifact_format=request.get("artifact_format"),
    )
    return validation_result(
        status="current_pass",
        artifact_map=amap,
        artifact_fingerprint=amap["artifact_fingerprint"],
    )


if __name__ == "__main__":
    raise SystemExit(cli_validate(build_manuscript_artifact_map, __doc__))
