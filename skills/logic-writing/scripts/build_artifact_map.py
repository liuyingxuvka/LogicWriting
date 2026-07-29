"""Build the deterministic current ArtifactMap for UTF-8 text or Markdown."""

from __future__ import annotations

from _common import cli_validate, require_mapping, validation_result
from reader_pipeline import build_artifact_map


def validate_request(value):
    request = require_mapping(value, "ArtifactMap build request")
    artifact_map = build_artifact_map(
        request.get("artifact_path"),
        map_id=request.get("map_id"),
        language=request.get("language"),
        artifact_format=request.get("artifact_format"),
    )
    return validation_result(
        status="current_pass",
        artifact_map=artifact_map,
        artifact_fingerprint=artifact_map["artifact_fingerprint"],
        map_fingerprint=artifact_map["map_fingerprint"],
    )


if __name__ == "__main__":
    raise SystemExit(cli_validate(validate_request, __doc__))


__all__ = ["build_artifact_map"]
