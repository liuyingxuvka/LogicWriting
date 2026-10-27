"""Reader binding: current reader-chain responsibilities."""
from __future__ import annotations

from _common import ValidationError, require_exact_fingerprint, require_mapping, require_schema
from artifact_map import validate_artifact_map
from pathlib import Path
from typing import Any, Mapping


def validate_shared_writing(
    value: Any,
    *,
    artifact_map: Mapping[str, Any],
    reader_brief: Mapping[str, Any],
) -> dict[str, Any]:
    amap = validate_artifact_map(artifact_map)
    return shared_writing_from_current(value, amap=amap, reader_brief=reader_brief)


def _resolve_quote(units, quote):
    matches = [row for row in units.values() if row['unit_kind'] != 'document' and quote in row['text']]
    preview = quote[:60]
    if not matches:
        raise ValidationError(f'quote "{preview}" is not in the current text')
    if len(matches) > 1:
        ids = ', '.join(row['artifact_unit_id'] for row in matches)
        raise ValidationError(f'quote "{preview}" is in several units ({ids}); use a longer quote')
    return matches[0]


def quote_binding_units(binding, units):
    quotes = binding.get('anchor_excerpts')
    if quotes is None:
        return None
    prefix = f"binding {binding.get('binding_id', '?')}: "
    if not isinstance(quotes, list) or not quotes or any(not isinstance(q, str) or len(q) < 12 for q in quotes):
        raise ValidationError(prefix + 'anchor_excerpts requires quotes of at least 12 characters')
    try:
        resolved = {}
        for quote in quotes:
            unit = _resolve_quote(units, quote)
            resolved[unit['artifact_unit_id']] = unit
    except ValidationError as exc:
        raise ValidationError(prefix + str(exc)) from exc
    if 'artifact_unit_ids' in binding:
        ids = binding['artifact_unit_ids']
        if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids) or set(ids) != set(resolved):
            raise ValidationError(prefix + 'anchor_excerpts and artifact_unit_ids disagree')
    return list(resolved.values())


def shared_writing_from_current(value, *, amap, reader_brief):
    contract = require_mapping(value, "SharedWriting")
    require_schema("shared-writing-contract.schema.json", contract, label="SharedWriting")
    require_exact_fingerprint(contract, "contract_fingerprint")
    brief = require_mapping(reader_brief, "ReaderBrief")
    require_schema("reader-brief.schema.json", brief, label="ReaderBrief")
    require_exact_fingerprint(brief, "brief_fingerprint")
    expected = {
        "final_owner": brief["final_owner"],
        "route_decision_fingerprint": brief["route_decision_fingerprint"],
        "reader_intent_fingerprint": brief["reader_intent_fingerprint"],
        "reader_brief_fingerprint": brief["brief_fingerprint"],
        "composition_plan_fingerprint": brief["composition_plan"]["plan_fingerprint"],
        "route_extension_fingerprint": brief["route_extension"]["extension_fingerprint"],
        "artifact_map_fingerprint": amap["map_fingerprint"],
        "artifact_fingerprint": amap["artifact_fingerprint"],
    }
    for key, expected_value in expected.items():
        if contract[key] != expected_value:
            raise ValidationError(f"SharedWriting {key} does not bind the current reader chain")
    if Path(contract["artifact_path"]).expanduser().resolve() != Path(amap["artifact_path"]):
        raise ValidationError("SharedWriting artifact_path does not match ArtifactMap")

    units = {row["artifact_unit_id"]: row for row in amap["units"]}
    plan_units = {row["planned_unit_id"]: row for row in brief["composition_plan"]["planned_units"]}
    content_units = {
        row["content_unit_id"]: row
        for row in brief["content_boundaries"]["content_units"]
    }
    bound_plans: set[str] = set()
    bound_content: set[str] = set()
    for binding in contract["unit_bindings"]:
        quote_binding_units(binding, units)
        planned_id = binding["planned_unit_id"]
        if planned_id not in plan_units:
            raise ValidationError(f"SharedWriting references unknown planned unit {planned_id}")
        bound_plans.add(planned_id)
        for content_id in binding["content_unit_ids"]:
            if content_id not in content_units:
                raise ValidationError(f"SharedWriting references unknown content unit {content_id}")
            bound_content.add(content_id)
        if set(binding["artifact_unit_ids"]) != {
            span["artifact_unit_id"] for span in binding["artifact_spans"]
        }:
            raise ValidationError(f"SharedWriting binding {binding['binding_id']} has inconsistent unit/span ids")
        for span in binding["artifact_spans"]:
            unit = units.get(span["artifact_unit_id"])
            if unit is None:
                raise ValidationError(f"SharedWriting references unknown artifact unit {span['artifact_unit_id']}")
            if span["locator"] != unit["locator"] or span["content_fingerprint"] != unit["content_fingerprint"]:
                raise ValidationError(f"SharedWriting span for {unit['artifact_unit_id']} is stale")
    required_plans = {key for key, row in plan_units.items() if row["required"]}
    if not required_plans <= bound_plans:
        raise ValidationError(f"required planned units are unbound: {sorted(required_plans - bound_plans)}")
    required_content = {key for key, row in content_units.items() if row["required"]}
    explicit_dispositions = {
        row["item_id"]
        for row in contract["coverage_dispositions"]
        if row["item_kind"] == "content_unit" and row["disposition"] in {"omitted", "not_applicable", "blocked"}
    }
    if not required_content <= bound_content | explicit_dispositions:
        raise ValidationError(f"required content units are unbound: {sorted(required_content - bound_content - explicit_dispositions)}")
    return contract
