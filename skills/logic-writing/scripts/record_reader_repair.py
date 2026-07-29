"""Record one actual ReaderRepairResult and derive progress from bytes and defects."""

from __future__ import annotations

from _common import cli_validate, require_mapping, validation_result
from reader_pipeline import record_repair_result


def validate_request(value):
    request = require_mapping(value, "ReaderRepair result request")
    result = record_repair_result(
        request=request.get("repair_request"),
        output_artifact_map=request.get("output_artifact_map"),
        changed_unit_ids=request.get("changed_unit_ids", []),
        preserved_content_unit_ids=request.get("preserved_content_unit_ids", []),
        preservation_violations=request.get("preservation_violations", []),
        remaining_defect_ids=request.get("remaining_defect_ids", []),
    )
    return validation_result(
        status="current_pass" if result["progress_status"] != "blocked" else "blocked",
        repair_result=result,
        result_fingerprint=result["result_fingerprint"],
        progress_status=result["progress_status"],
    )


if __name__ == "__main__":
    raise SystemExit(cli_validate(validate_request, __doc__))


__all__ = ["record_repair_result"]
