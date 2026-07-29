#!/usr/bin/env python3
"""Propagate current v2 reader-chain staleness along explicit dependencies."""

from __future__ import annotations

from typing import Any

from _common import ValidationError, cli_validate, fingerprint, require_mapping, validation_result


def propagate_staleness(value: Any, *, receipt_root=None) -> dict[str, Any]:
    del receipt_root
    request = require_mapping(value, "staleness request")
    allowed = {"schema_version", "current_inputs", "observed_inputs", "records"}
    unknown = sorted(set(request) - allowed)
    if unknown:
        raise ValidationError(f"staleness request has unknown current fields: {unknown}")
    if request.get("schema_version") != "2.0":
        raise ValidationError("staleness request schema_version must be 2.0")
    current = require_mapping(request.get("current_inputs"), "current_inputs")
    observed = require_mapping(request.get("observed_inputs"), "observed_inputs")
    if set(current) != set(observed):
        raise ValidationError("observed_inputs must exactly cover current_inputs")
    changed = {
        key for key in current
        if current[key] != observed[key]
    }
    records = request.get("records")
    if not isinstance(records, list):
        raise ValidationError("records must be an array")
    ids = [row.get("record_id") for row in records if isinstance(row, dict)]
    if len(ids) != len(records) or not all(ids) or len(ids) != len(set(ids)):
        raise ValidationError("record ids must be non-empty and unique")
    known = set(ids)
    status_by_id: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    pending = list(records)
    while pending:
        progressed = False
        for row in list(pending):
            consumes = row.get("consumes", [])
            depends_on = row.get("depends_on", [])
            if not isinstance(consumes, list) or not isinstance(depends_on, list):
                raise ValidationError("record consumes and depends_on must be arrays")
            if not set(consumes) <= set(current):
                raise ValidationError(f"record {row['record_id']} consumes an unknown input")
            if not set(depends_on) <= known:
                raise ValidationError(f"record {row['record_id']} has an unknown dependency")
            if any(parent not in status_by_id for parent in depends_on):
                continue
            stale_reasons = [
                *(f"input_changed:{key}" for key in consumes if key in changed),
                *(f"dependency_stale:{parent}" for parent in depends_on if status_by_id[parent] == "stale"),
            ]
            status = "stale" if stale_reasons else "current"
            status_by_id[row["record_id"]] = status
            rows.append({
                "record_id": row["record_id"],
                "status": status,
                "stale_because": stale_reasons,
            })
            pending.remove(row)
            progressed = True
        if not progressed:
            raise ValidationError("record dependency graph contains a cycle")
    result = {
        "schema_version": "2.0",
        "changed_input_ids": sorted(changed),
        "records": rows,
    }
    result["propagation_fingerprint"] = fingerprint(result)
    return validation_result(
        status="current_pass",
        staleness=result,
        stale_record_ids=[row["record_id"] for row in rows if row["status"] == "stale"],
    )


if __name__ == "__main__":
    raise SystemExit(cli_validate(propagate_staleness, __doc__))


__all__ = ["propagate_staleness"]
