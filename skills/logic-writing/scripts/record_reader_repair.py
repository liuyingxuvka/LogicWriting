"""Record one actual ReaderRepairResult and derive progress from bytes and defects."""

from __future__ import annotations

import argparse
import json

from _common import ValidationError, dump_json, load_json, require_mapping, validation_result
from reader_pipeline import record_repair_result


def validate_request(value, *, execution_resolver=None):
    request = require_mapping(value, "ReaderRepair result request")
    result = record_repair_result(
        request=request.get("repair_request"),
        output_artifact_map=request.get("output_artifact_map"),
        changed_unit_ids=request.get("changed_unit_ids", []),
        preserved_content_unit_ids=request.get("preserved_content_unit_ids", []),
        preservation_violations=request.get("preservation_violations", []),
        remaining_defect_ids=request.get("remaining_defect_ids", []),
        current_judgment=request.get("current_judgment"),
        reader_brief=request.get("reader_brief"),
        shared_writing=request.get("shared_writing"),
        deterministic_audit=request.get("deterministic_audit"),
        route_composition=request.get("route_composition"),
        route_review=request.get("route_review"),
        execution_record=request.get("execution_record"),
        execution_resolver=execution_resolver,
        review_obligations=request.get("review_obligations"),
    )
    return validation_result(
        status="current_pass" if result["progress_status"] != "blocked" else "blocked",
        repair_result=result,
        result_fingerprint=result["result_fingerprint"],
        progress_status=result["progress_status"],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    parser.add_argument("--execution-root", help="Local immutable writer/judge capture root")
    args = parser.parse_args()
    try:
        from execution_record_resolver import LocalExecutionRecordResolver
        resolver = LocalExecutionRecordResolver(args.execution_root) if args.execution_root else None
        result = validate_request(load_json(args.input), execution_resolver=resolver)
    except (ValidationError, OSError, json.JSONDecodeError) as exc:
        result = validation_result(status="blocked", errors=(str(exc),))
    dump_json(result, args.output)
    return 0 if result["status"] == "current_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["record_repair_result"]
