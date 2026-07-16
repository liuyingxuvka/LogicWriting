"""Validate route-neutral reader-state and model-to-artifact writing contracts."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from _common import (
    ValidationError,
    cli_validate,
    fingerprint_without,
    require_mapping,
    require_schema,
    validation_result,
)


GENERIC_HANDOFF = re.compile(
    r"^(?:sets? up (?:the )?next (?:section|chapter|part|day)|"
    r"leads? to (?:the )?next (?:section|chapter|part|day)|"
    r"moves? to (?:the )?next (?:section|chapter|part|day)|"
    r"continues? (?:to|with)|next section|下文|引出下文|继续)$",
    re.IGNORECASE,
)
EXPLANATION_PRESSURE = re.compile(
    r"\b(?:this (?:section|paragraph|chapter|day) (?:shows|demonstrates|aims|will)|"
    r"the reader (?:should|will) (?:feel|understand)|this scene establishes)\b|"
    r"(?:本节|本段|本章|这一天)(?:旨在|将会|表明)|读者(?:应该|将会)(?:感到|理解)",
    re.IGNORECASE,
)
NO_CHANGED_EFFECT = re.compile(r"^(?:none|same|unchanged|无|相同|不变)$", re.IGNORECASE)


def _bytes_fingerprint(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def validate_shared_writing(value):
    contract = require_mapping(value, "shared writing contract")
    require_schema(
        "shared-writing-contract.schema.json", contract, label="shared writing contract"
    )
    if contract["contract_fingerprint"] != fingerprint_without(
        contract, "contract_fingerprint"
    ):
        raise ValidationError("contract_fingerprint does not bind the exact contract")
    path = Path(contract["artifact_path"]).expanduser().resolve()
    if not path.is_file():
        raise ValidationError("artifact_path does not identify a current file")

    findings: list[dict[str, str]] = []
    actual = _bytes_fingerprint(path)
    if actual != contract["artifact_fingerprint"]:
        findings.append({"code": "stale_artifact", "unit_id": "artifact"})
    if contract["route_extension"]["owner"] != contract["final_owner"]:
        findings.append({"code": "foreign_route_extension", "unit_id": "artifact"})

    text = path.read_text(encoding="utf-8")
    prior = None
    bound_rows: dict[str, str] = {}
    for unit in contract["units"]:
        unit_id = unit["unit_id"]
        if unit["important"] and not unit["model_row_ids"]:
            findings.append({"code": "unbound_prose", "unit_id": unit_id})
        if unit["artifact_span"] not in text:
            findings.append({"code": "unrealized_model_row", "unit_id": unit_id})
        if GENERIC_HANDOFF.search(unit["downstream_consumer"].strip()):
            findings.append({"code": "generic_handoff", "unit_id": unit_id})
        if EXPLANATION_PRESSURE.search(unit["artifact_span"]):
            findings.append({"code": "explanation_pressure", "unit_id": unit_id})
        if prior and prior["contribution"].casefold() == unit["contribution"].casefold():
            if NO_CHANGED_EFFECT.search(unit["variation_effect"].strip()):
                findings.append({"code": "variation_without_effect", "unit_id": unit_id})
        for row_id in unit["model_row_ids"]:
            prior_unit = bound_rows.setdefault(row_id, unit_id)
            if prior_unit != unit_id and NO_CHANGED_EFFECT.search(unit["variation_effect"].strip()):
                findings.append({"code": "unsupported_duplicate_binding", "unit_id": unit_id})
        prior = unit

    hard = {
        "stale_artifact", "foreign_route_extension", "unbound_prose",
        "unrealized_model_row", "generic_handoff", "explanation_pressure",
        "unsupported_duplicate_binding",
    }
    status = "current_pass" if not findings else (
        "failed" if any(row["code"] in hard for row in findings) else "partial"
    )
    return validation_result(
        status=status,
        artifact_fingerprint=actual,
        final_owner=contract["final_owner"],
        findings=findings,
    )


if __name__ == "__main__":
    raise SystemExit(cli_validate(validate_shared_writing, __doc__))


__all__ = ["validate_shared_writing"]
