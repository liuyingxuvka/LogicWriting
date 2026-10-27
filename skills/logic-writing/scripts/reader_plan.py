"""Reader plan: current reader-chain responsibilities."""
from __future__ import annotations

from _common import ValidationError, unique_ids, require_exact_fingerprint, fill_fingerprint, fill_missing, fingerprint, fingerprint_without, require_mapping, require_schema, utc_now
from artifact_map import validate_artifact_map
from copy import deepcopy
from reader_plan_core import open_material_choices, validate_composition_plan, validate_reader_intent, validate_route_composition
from reader_rules import FINAL_OWNERS, ROUTE_PROFILE_FIELD, ROUTE_SCHEMA
from typing import Any, Iterable, Mapping
from writer_projection import build_writer_input, validate_writer_input


def build_reader_brief(
    *,
    route_decision: Mapping[str, Any],
    content_boundaries: Mapping[str, Any],
    composition_plan: Mapping[str, Any],
    route_composition: Mapping[str, Any],
    brief_id: str,
    research_folder: str | None = None,
    research_status: str | None = None,
) -> dict[str, Any]:
    decision = require_mapping(route_decision, "RouteDecision")
    raw_intent = require_mapping(decision.get("reader_intent"), "ReaderIntent")
    choices = open_material_choices(raw_intent)
    if choices:
        first = choices[0]
        raise ValidationError(
            f"ReaderIntent has an open material choice {first['choice_id']}: "
            f"{first['question']}; ask the user before planning"
        )
    require_schema("route-decision.schema.json", decision, label="RouteDecision")
    require_exact_fingerprint(decision, "decision_fingerprint")
    if decision["status"] != "current" or decision["final_owner"] not in FINAL_OWNERS:
        raise ValidationError("ReaderBrief requires one current final owner")
    intent = validate_reader_intent(decision["reader_intent"])
    if decision["reader_intent_fingerprint"] != intent["intent_fingerprint"]:
        raise ValidationError("RouteDecision copied a different ReaderIntent fingerprint")
    boundaries = require_mapping(content_boundaries, "content boundaries")
    content_ids = unique_ids(boundaries.get("content_units", ()), "content_unit_id", "content unit")
    limitation_ids = unique_ids(boundaries.get("limitations", ()), "limitation_id", "limitation")
    plan = validate_composition_plan(
        composition_plan,
        reader_intent=intent,
        content_unit_ids=content_ids,
        limitation_ids=limitation_ids,
    )
    owner = decision["final_owner"]
    if owner == "travel-guide":
        import sys
        from pathlib import Path
        travel_scripts = Path(__file__).resolve().parents[1] / "routes/travel/scripts"
        if str(travel_scripts) not in sys.path:
            sys.path.insert(0, str(travel_scripts))
        from travel_contract import validate_plan_file, validate_composition_refs
        from _common import load_json
        trip_path = route_composition.get("trip_plan")
        if not isinstance(trip_path, str) or not trip_path:
            raise ValidationError("travel composition requires trip_plan")
        issues = validate_plan_file(trip_path, repository_root=Path(__file__).resolve().parents[3])
        trip = load_json(trip_path)
        issues.extend(validate_composition_refs(trip, route_composition))
        from _common import worldguard_report_identity_problems
        checks = trip.get("world_feasibility", {}).get("checks", []) if isinstance(trip, dict) else []
        for check in checks if isinstance(checks, list) else []:
            report = check.get("worldguard_report") if isinstance(check, dict) else None
            if isinstance(report, str) and report:
                problems = worldguard_report_identity_problems(Path(trip_path).parent / report,
                                                               route_composition.get("world_contract"))
                if problems:
                    issues.append({"code": "travel_composition.world_report.mismatch",
                                   "message": f"{report} does not belong to the composition's world_contract: {'; '.join(problems)}"})
        if issues:
            raise ValidationError("travel composition input is invalid: " + "; ".join(row["code"] + ": " + row["message"] for row in issues))
    route = validate_route_composition(
        route_composition,
        owner=owner,
        reader_intent_fingerprint=intent["intent_fingerprint"],
        composition_plan_fingerprint=plan["plan_fingerprint"],
        composition_plan=plan,
        content_boundaries=boundaries,
    )
    route_envelope = {
        "owner": owner,
        "profile": route[ROUTE_PROFILE_FIELD[owner]],
        "schema_name": ROUTE_SCHEMA[owner],
        "extension_fingerprint": route["extension_fingerprint"],
    }
    writer_input = build_writer_input(
        owner=owner,
        intent=intent,
        plan=plan,
        route=route,
        boundaries=boundaries,
    )
    brief = {
        "schema_version": "2.0",
        "brief_id": brief_id,
        "route_decision_fingerprint": decision["decision_fingerprint"],
        "reader_intent_fingerprint": intent["intent_fingerprint"],
        "final_owner": owner,
        "terminal_deliverable": decision["terminal_deliverable"],
        "reader_intent": intent,
        "content_boundaries": boundaries,
        "composition_plan": plan,
        "route_extension": route_envelope,
        "writer_input": writer_input,
        "writer_input_fingerprint": fingerprint(writer_input),
    }
    if research_folder is not None:
        if not isinstance(research_folder, str) or not research_folder.strip():
            raise ValidationError("research_folder must be a nonempty path")
        brief["research_folder"] = research_folder
    if research_status is not None:
        if not isinstance(research_status, str) or not research_status.strip() or research_folder is None:
            raise ValidationError("research_status needs research_folder")
        brief["research_status"] = research_status
    brief["brief_fingerprint"] = fingerprint(brief)
    validate_writer_input(writer_input, composition_plan=plan)
    require_schema("reader-brief.schema.json", brief, label="ReaderBrief")
    return brief


def validate_revision_provenance(
    value: Any, *, target_artifact_fingerprint: str, artifact_mode: str | None = None,
    artifact_map: Mapping[str, Any] | None = None, reader_intent_fingerprint: str | None = None,
    final_owner: str | None = None, recorded_at: str | None = None,
) -> dict[str, Any]:
    """Own revision mode, real source-byte identity and source/target unit checks."""
    if value is None:
        if artifact_mode == "revise_existing":
            raise ValidationError("revise_existing requires revision_provenance with source_artifact_path")
        provenance = {
            "schema_version": "2.0", "provenance_id": "provenance:not-applicable",
            "final_owner": final_owner, "artifact_mode": "create_new",
            "reader_intent_fingerprint": reader_intent_fingerprint,
            "source_artifact_fingerprint": None, "target_artifact_fingerprint": target_artifact_fingerprint,
            "applicability": "not_applicable", "unit_treatments": [],
            "recorded_at": recorded_at or utc_now(),
        }
    else:
        provenance = deepcopy(require_mapping(value, "revision provenance"))
    mode = provenance.get("artifact_mode")
    if artifact_mode is not None and mode != artifact_mode:
        raise ValidationError(f"revision provenance says {mode} but ReaderIntent says {artifact_mode}")
    fill_missing(provenance, "reader_intent_fingerprint", reader_intent_fingerprint)
    fill_missing(provenance, "final_owner", final_owner)
    fill_missing(provenance, "target_artifact_fingerprint", target_artifact_fingerprint)
    if provenance["target_artifact_fingerprint"] != target_artifact_fingerprint:
        raise ValidationError("revision provenance is stale for the current artifact")
    if mode == "revise_existing":
        from build_source_unit_manifest import build_source_unit_manifest
        source_path = provenance.get("source_artifact_path")
        if not isinstance(source_path, str) or not source_path:
            raise ValidationError("revise_existing requires source_artifact_path")
        if artifact_map is None:
            raise ValidationError("revise_existing requires the current artifact_map")
        amap = validate_artifact_map(artifact_map)
        manifest = build_source_unit_manifest(manifest_id="manifest:revision",
            source_path=source_path, target_path=amap["artifact_path"])
        actual_source = manifest["source"]["artifact_fingerprint"]
        provided_source = provenance.get("source_artifact_fingerprint")
        if provided_source is not None and provided_source != actual_source:
            raise ValidationError("source_artifact_fingerprint does not match the real source_artifact_path bytes")
        provenance["source_artifact_fingerprint"] = actual_source
        if manifest["target"]["artifact_fingerprint"] != target_artifact_fingerprint:
            raise ValidationError("revision provenance is stale for the current artifact")
        source_ids = {row["unit_id"] for row in manifest["source"]["units"]}
        target_ids = {row["artifact_unit_id"] for row in amap["units"]}
        treatments = provenance.get("unit_treatments", [])
        if not isinstance(treatments, list) or not treatments:
            raise ValidationError("revise_existing requires source-unit treatments")
        treatments = [require_mapping(row, "source unit treatment") for row in treatments]
        unique_ids(treatments, "source_unit_id", "source unit treatment")
        for row in treatments:
            if row["source_unit_id"] not in source_ids:
                raise ValidationError(f"unknown source_unit_id: {row['source_unit_id']}")
            for target in row.get("target_unit_ids", []):
                if target not in target_ids:
                    raise ValidationError(f"unknown target_unit_id: {target}")
    fill_fingerprint(provenance, "provenance_fingerprint")
    require_schema("revision-provenance.schema.json", provenance, label="revision provenance")
    require_exact_fingerprint(provenance, "provenance_fingerprint")
    return provenance
