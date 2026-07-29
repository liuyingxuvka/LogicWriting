"""Validate SharedWriting v2 as complete plan-to-current-byte binding."""

from __future__ import annotations

from _common import cli_validate, require_mapping, validation_result
from reader_pipeline import validate_shared_writing as _validate_shared_writing


def validate_shared_writing(value, *, artifact_map=None, reader_brief=None):
    envelope = require_mapping(value, "SharedWriting validation request")
    contract = envelope.get("contract", envelope)
    amap = artifact_map if artifact_map is not None else envelope.get("artifact_map")
    brief = reader_brief if reader_brief is not None else envelope.get("reader_brief")
    validated = _validate_shared_writing(
        contract,
        artifact_map=amap,
        reader_brief=brief,
    )
    return validation_result(
        status="current_pass",
        artifact_fingerprint=validated["artifact_fingerprint"],
        final_owner=validated["final_owner"],
        contract_fingerprint=validated["contract_fingerprint"],
        findings=[],
    )


if __name__ == "__main__":
    raise SystemExit(cli_validate(validate_shared_writing, __doc__))


__all__ = ["validate_shared_writing"]
