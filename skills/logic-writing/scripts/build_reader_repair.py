"""Build a typed ReaderRepairRequest from one current non-pass reader chain."""

from __future__ import annotations

from _common import cli_validate, require_mapping, validation_result
from reader_pipeline import build_repair_request


def validate_request(value):
    request = require_mapping(value, "ReaderRepair build request")
    repair = build_repair_request(
        repair_id=request.get("repair_id"),
        attempt_number=request.get("attempt_number"),
        reader_brief=request.get("reader_brief"),
        artifact_map=request.get("artifact_map"),
        shared_writing=request.get("shared_writing"),
        deterministic_audit=request.get("deterministic_audit"),
        route_review=request.get("route_review"),
        judgment=request.get("judgment"),
        defect_lineage=request.get("defect_lineage"),
    )
    return validation_result(
        status="current_pass",
        repair_request=repair,
        request_fingerprint=repair["request_fingerprint"],
    )


if __name__ == "__main__":
    raise SystemExit(cli_validate(validate_request, __doc__))


__all__ = ["build_repair_request"]
