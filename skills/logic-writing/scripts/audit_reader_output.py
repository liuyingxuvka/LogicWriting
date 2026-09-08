"""Run deterministic ReaderAudit v2 against exact current artifact units."""

from __future__ import annotations

from _common import cli_validate, require_mapping, validation_result
from reader_pipeline import build_reader_audit, validate_reader_audit_current


def audit_reader_output(value, *, receipt_root=None):
    del receipt_root
    request = require_mapping(value, "ReaderAudit request")
    audit = build_reader_audit(
        audit_id=request.get("audit_id"),
        artifact_map=request.get("artifact_map"),
        reader_brief=request.get("reader_brief"),
        shared_writing=request.get("shared_writing"),
        audited_at=request.get("audited_at"),
    )
    return validation_result(
        status="current_pass" if audit["status"] == "passed" else "partial",
        reader_audit=audit,
        audit_fingerprint=audit["audit_fingerprint"],
        artifact_fingerprint=audit["artifact_fingerprint"],
        findings=audit["findings"],
    )


def validate_audit_current(value):
    request = require_mapping(value, "ReaderAudit currentness request")
    audit = validate_reader_audit_current(
        request.get("reader_audit", request.get("audit")),
        artifact_map=request.get("artifact_map"),
        reader_brief=request.get("reader_brief"),
        shared_writing=request.get("shared_writing"),
        rules_version=request.get("rules_version", "reader-audit-rules.v2"),
    )
    return validation_result(status="current_pass", reader_audit=audit, audit_fingerprint=audit["audit_fingerprint"])


if __name__ == "__main__":
    raise SystemExit(cli_validate(audit_reader_output, __doc__))


__all__ = ["audit_reader_output", "validate_audit_current"]
