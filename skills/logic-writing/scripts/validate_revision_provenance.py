"""Validate route-neutral, artifact-mode-aware revision provenance v2."""

from __future__ import annotations

from _common import cli_validate, require_mapping, validation_result
from reader_pipeline import validate_revision_provenance as _validate_revision


def validate_revision_provenance(value, *, target_artifact_fingerprint=None, **_ignored):
    envelope = require_mapping(value, "revision provenance validation request")
    provenance = envelope.get("provenance", envelope)
    target = target_artifact_fingerprint or envelope.get("target_artifact_fingerprint") or provenance.get("target_artifact_fingerprint")
    validated = _validate_revision(
        provenance,
        target_artifact_fingerprint=target,
    )
    return validation_result(
        status="current_pass",
        applicability=validated["applicability"],
        provenance_fingerprint=validated["provenance_fingerprint"],
        target_artifact_fingerprint=validated["target_artifact_fingerprint"],
    )


if __name__ == "__main__":
    raise SystemExit(cli_validate(validate_revision_provenance, __doc__))


__all__ = ["validate_revision_provenance"]
