"""Validate independent, actual-artifact-bound ReaderJudgment v2."""

from __future__ import annotations

from _common import cli_validate, require_mapping, validation_result
from reader_pipeline import validate_reader_judgment


def validate_judgment_receipt(
    value,
    *,
    artifact_map=None,
    reader_brief=None,
    shared_writing=None,
    deterministic_audit=None,
    route_review=None,
    **_ignored,
):
    envelope = require_mapping(value, "ReaderJudgment validation request")
    judgment = envelope.get("judgment", envelope)
    validated = validate_reader_judgment(
        judgment,
        artifact_map=artifact_map or envelope.get("artifact_map"),
        reader_brief=reader_brief or envelope.get("reader_brief"),
        shared_writing=shared_writing or envelope.get("shared_writing"),
        deterministic_audit=deterministic_audit or envelope.get("deterministic_audit"),
        route_review=route_review or envelope.get("route_review"),
    )
    return validation_result(
        status="current_pass" if validated["status"] == "passed" else "partial",
        reader_judgment=validated,
        judgment_fingerprint=validated["judgment_fingerprint"],
        artifact_fingerprint=validated["artifact_fingerprint"],
        required_repairs=validated["required_repairs"],
    )


if __name__ == "__main__":
    raise SystemExit(cli_validate(validate_judgment_receipt, __doc__))


__all__ = ["validate_judgment_receipt"]
