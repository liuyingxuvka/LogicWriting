"""Validate independent, actual-artifact-bound ReaderJudgment v2."""

from __future__ import annotations

from _common import ValidationError, cli_validate, require_mapping, validation_result
from reader_pipeline import validate_reader_judgment


def _resolve_judge_execution_record(
    envelope: dict,
    *,
    execution_record=None,
    reader_execution_records=None,
):
    """Return the one current judge record supplied by the execution owner.

    A judgment envelope may carry one record directly or the execution list
    used by closure.  The wrapper must not silently ignore that list: doing so
    would turn a real execution receipt into a missing execution and would
    make it tempting for a caller to restore the old self-filled pass path.
    Ambiguous or non-judge records are rejected instead of guessing.
    """

    direct = execution_record
    if direct is None:
        direct = envelope.get("execution_record")
    if direct is None:
        direct = envelope.get("reader_execution_record")

    records = reader_execution_records
    if records is None:
        records = envelope.get("reader_execution_records")
    if records is not None:
        if not isinstance(records, list):
            raise ValidationError("reader_execution_records must be an array")
        judges = [row for row in records if isinstance(row, dict) and row.get("role") == "judge"]
        if direct is None:
            if len(judges) != 1:
                raise ValidationError(
                    "exactly one judge ReaderExecutionRecord is required"
                )
            direct = judges[0]
        elif judges and direct not in judges:
            raise ValidationError(
                "execution_record does not match the judge record in reader_execution_records"
            )

    if direct is None:
        return None
    if not isinstance(direct, dict):
        raise ValidationError("execution_record must be an object")
    if direct.get("role") != "judge":
        raise ValidationError("ReaderJudgment requires a judge ReaderExecutionRecord")
    return direct


def validate_judgment_receipt(
    value,
    *,
    artifact_map=None,
    reader_brief=None,
    shared_writing=None,
    deterministic_audit=None,
    route_review=None,
    execution_record=None,
    reader_execution_records=None,
    execution_resolver=None,
    **_ignored,
):
    envelope = require_mapping(value, "ReaderJudgment validation request")
    judgment = envelope.get("judgment", envelope)
    execution = _resolve_judge_execution_record(
        envelope,
        execution_record=execution_record,
        reader_execution_records=reader_execution_records,
    )
    validated = validate_reader_judgment(
        judgment,
        artifact_map=artifact_map or envelope.get("artifact_map"),
        reader_brief=reader_brief or envelope.get("reader_brief"),
        shared_writing=shared_writing or envelope.get("shared_writing"),
        deterministic_audit=deterministic_audit or envelope.get("deterministic_audit"),
        route_review=route_review or envelope.get("route_review"),
        execution_record=execution,
    )
    # ``validate_reader_judgment`` checks the immutable envelope and the
    # declared independence marker.  That marker alone is not execution
    # evidence: a protocol fixture can carry the same shape and say
    # ``verified``.  A current-pass receipt therefore needs the local
    # capture resolver as a second, byte-level proof of the provider run.
    if validated["status"] == "passed":
        if execution is None:
            raise ValidationError(
                "current-pass ReaderJudgment requires one judge execution record"
            )
        if execution_resolver is None:
            raise ValidationError(
                "current-pass ReaderJudgment requires a local execution capture resolver"
            )
        from reader_execution import validate_execution_record

        resolved = validate_execution_record(execution, execution_resolver)
        if not resolved.get("verified"):
            raise ValidationError(
                "current-pass ReaderJudgment requires a verified local execution capture"
            )
    return validation_result(
        status="current_pass" if validated["status"] == "passed" else "partial",
        reader_judgment=validated,
        judgment_fingerprint=validated["judgment_fingerprint"],
        artifact_fingerprint=validated["artifact_fingerprint"],
        execution_record_fingerprint=(execution or {}).get("record_fingerprint"),
        required_repairs=validated["required_repairs"],
    )


if __name__ == "__main__":
    raise SystemExit(cli_validate(validate_judgment_receipt, __doc__))


__all__ = ["validate_judgment_receipt"]
