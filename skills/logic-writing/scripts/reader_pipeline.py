"""Current Logic Writing reader-composition kernel.

This module owns only route-neutral identity, composition coverage, mechanical
artifact mapping, deterministic checks, independent-review binding, and typed
repair. Route semantics remain in the four selected route validators.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from _common import (
    ValidationError,
    fingerprint,
    fingerprint_text,
    fingerprint_without,
    require_mapping,
    require_schema,
)


FINAL_OWNERS = ("investigation", "academic-writing", "fiction-writing", "travel-guide")
ROUTE_SCHEMA = {
    "investigation": "investigation-composition.schema.json",
    "academic-writing": "academic-composition.schema.json",
    "fiction-writing": "fiction-composition.schema.json",
    "travel-guide": "travel-composition.schema.json",
}
ROUTE_PROFILE_FIELD = {
    "investigation": "profile",
    "academic-writing": "profile",
    "fiction-writing": "output_room",
    "travel-guide": "guide_kind",
}
LIST_LINE = re.compile(
    r"^\s*(?:[-*+•◦▪‣]\s+|\d+[.)、]\s*|[一二三四五六七八九十]+、\s*|"
    r"[（(][一二三四五六七八九十\d]+[）)]\s*|\*\*[^*]{1,30}\*\*[：:])"
)
PLACEHOLDER = re.compile(
    r"\b(?:TODO|TBD|FIXME|INSERT\s+(?:TEXT|CITATION|EVIDENCE)|LOREM IPSUM)\b|"
    r"\[(?:TODO|TBD|INSERT)[^\]]*\]",
    re.IGNORECASE,
)
WORKFLOW_LEAK = re.compile(
    r"\b(?:SourceGuard|LogicGuard|TraceGuard|FlowGuard|current_pass|"
    r"reader_intent_fingerprint|composition_plan_fingerprint|repair_request)\b|"
    r"(?:本段|本节|本章)(?:旨在|将会|负责)|(?:以下段落|下一节)(?:将会|负责)",
    re.IGNORECASE,
)
SENTENCE_END = re.compile(r"[.!?。！？](?:[\"'”’)\]]*)$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_exact_fingerprint(value: Mapping[str, Any], field: str) -> None:
    if value.get(field) != fingerprint_without(dict(value), field):
        raise ValidationError(f"{field} does not bind the exact current object")


def _ids(rows: Iterable[Mapping[str, Any]], field: str, label: str) -> tuple[str, ...]:
    values = tuple(str(row.get(field, "")) for row in rows)
    if not all(values) or len(values) != len(set(values)):
        raise ValidationError(f"{label} ids must be non-empty and unique")
    return values


def validate_reader_intent(value: Any) -> dict[str, Any]:
    intent = require_mapping(value, "ReaderIntent")
    require_schema("reader-intent.schema.json", intent, label="ReaderIntent")
    _require_exact_fingerprint(intent, "intent_fingerprint")
    extent = intent["extent"]
    if not extent["minimum"] <= extent["target"] <= extent["maximum"]:
        raise ValidationError("ReaderIntent extent must satisfy minimum <= target <= maximum")
    rows = intent["structure"]["requested_outline"]
    outline_ids = set(_ids(rows, "outline_id", "outline"))
    for row in rows:
        parent = row["parent_outline_id"]
        if parent is not None and parent not in outline_ids:
            raise ValidationError(f"outline row {row['outline_id']} has an unknown parent")
    parent_of = {row["outline_id"]: row["parent_outline_id"] for row in rows}
    for outline_id in outline_ids:
        seen: set[str] = set()
        current: str | None = outline_id
        while current is not None:
            if current in seen:
                raise ValidationError("ReaderIntent outline contains a parent cycle")
            seen.add(current)
            current = parent_of.get(current)
    return intent


def validate_writing_request(value: Any) -> dict[str, Any]:
    request = require_mapping(value, "WritingRequest")
    require_schema("writing-request.schema.json", request, label="WritingRequest")
    validate_reader_intent(request["reader_intent"])
    if request["reader_intent"]["intent_fingerprint"] == request["request_fingerprint"]:
        raise ValidationError("request_fingerprint must bind the whole request, not alias ReaderIntent")
    _require_exact_fingerprint(request, "request_fingerprint")
    deliverable = dict(request["terminal_deliverable"])
    if deliverable["fingerprint"] != fingerprint_without(deliverable, "fingerprint"):
        raise ValidationError("terminal_deliverable fingerprint is not current")
    return request


def validate_composition_plan(
    value: Any,
    *,
    reader_intent: Mapping[str, Any],
    content_unit_ids: Iterable[str],
    limitation_ids: Iterable[str],
) -> dict[str, Any]:
    plan = require_mapping(value, "CompositionPlan")
    require_schema("composition-plan.schema.json", plan, label="CompositionPlan")
    _require_exact_fingerprint(plan, "plan_fingerprint")
    intent = validate_reader_intent(reader_intent)
    if plan["reader_intent_fingerprint"] != intent["intent_fingerprint"]:
        raise ValidationError("CompositionPlan does not bind the current ReaderIntent")
    material_conflicts = [row for row in plan["unresolved_conflicts"] if row["material"]]
    if material_conflicts:
        raise ValidationError("material ReaderIntent conflicts must be resolved before drafting")

    planned = plan["planned_units"]
    planned_ids = set(_ids(planned, "planned_unit_id", "planned unit"))
    outline_coverage = {
        outline_id
        for unit in planned
        for outline_id in unit["source_outline_ids"]
    }
    required_outline_ids = {
        row["outline_id"]
        for row in intent["structure"]["requested_outline"]
        if row["required"]
    }
    missing_outline = sorted(required_outline_ids - outline_coverage)
    if missing_outline:
        raise ValidationError(f"required ReaderIntent outline rows are not planned: {missing_outline}")

    required_content = set(content_unit_ids)
    disposition_by_id = {row["content_unit_id"]: row for row in plan["content_dispositions"]}
    if set(disposition_by_id) != required_content:
        raise ValidationError("CompositionPlan content dispositions must exactly cover current content units")
    consumed_content = {
        content_id
        for unit in planned
        for content_id in unit["content_unit_ids"]
    }
    for content_id, disposition in disposition_by_id.items():
        if disposition["disposition"] == "consumed":
            if content_id not in consumed_content or not disposition["planned_unit_ids"]:
                raise ValidationError(f"consumed content unit {content_id} lacks a planned unit")
            if any(unit_id not in planned_ids for unit_id in disposition["planned_unit_ids"]):
                raise ValidationError(f"content disposition {content_id} references an unknown planned unit")

    known_limitations = set(limitation_ids)
    placed_limitations = {
        limitation_id
        for unit in planned
        for limitation_id in unit["limitation_ids"]
    }
    if not known_limitations <= placed_limitations:
        raise ValidationError(
            f"limitations lack planned placement: {sorted(known_limitations - placed_limitations)}"
        )
    for unit in planned:
        parent = unit["parent_unit_id"]
        if parent is not None and parent not in planned_ids:
            raise ValidationError(f"planned unit {unit['planned_unit_id']} has an unknown parent")
        if unit["presentation_mode"] in {"list", "table", "appendix"}:
            policy = intent["list_policy"]
            if policy == "prose_default" and unit["planned_unit_id"] not in plan["allowed_list_zones"]:
                raise ValidationError(f"planned list/table unit {unit['planned_unit_id']} is outside an allowed zone")
    return plan


def validate_route_composition(
    value: Any,
    *,
    owner: str,
    reader_intent_fingerprint: str,
    composition_plan_fingerprint: str,
) -> dict[str, Any]:
    if owner not in ROUTE_SCHEMA:
        raise ValidationError(f"unknown final owner: {owner}")
    composition = require_mapping(value, f"{owner} composition")
    require_schema(ROUTE_SCHEMA[owner], composition, label=f"{owner} composition")
    _require_exact_fingerprint(composition, "extension_fingerprint")
    if composition["final_owner"] != owner:
        raise ValidationError("route composition belongs to a sibling final owner")
    if composition["reader_intent_fingerprint"] != reader_intent_fingerprint:
        raise ValidationError("route composition does not bind the current ReaderIntent")
    if composition["composition_plan_fingerprint"] != composition_plan_fingerprint:
        raise ValidationError("route composition does not bind the current CompositionPlan")
    return composition


def build_reader_brief(
    *,
    route_decision: Mapping[str, Any],
    content_boundaries: Mapping[str, Any],
    composition_plan: Mapping[str, Any],
    route_composition: Mapping[str, Any],
    native_dependency_receipt_fingerprints: Iterable[str],
    content_authority_fingerprints: Mapping[str, str],
    brief_id: str,
) -> dict[str, Any]:
    decision = require_mapping(route_decision, "RouteDecision")
    require_schema("route-decision.schema.json", decision, label="RouteDecision")
    _require_exact_fingerprint(decision, "decision_fingerprint")
    if decision["status"] != "current" or decision["final_owner"] not in FINAL_OWNERS:
        raise ValidationError("ReaderBrief requires one current final owner")
    intent = validate_reader_intent(decision["reader_intent"])
    if decision["reader_intent_fingerprint"] != intent["intent_fingerprint"]:
        raise ValidationError("RouteDecision copied a different ReaderIntent fingerprint")
    boundaries = require_mapping(content_boundaries, "content boundaries")
    content_ids = _ids(boundaries.get("content_units", ()), "content_unit_id", "content unit")
    limitation_ids = _ids(boundaries.get("limitations", ()), "limitation_id", "limitation")
    plan = validate_composition_plan(
        composition_plan,
        reader_intent=intent,
        content_unit_ids=content_ids,
        limitation_ids=limitation_ids,
    )
    owner = decision["final_owner"]
    route = validate_route_composition(
        route_composition,
        owner=owner,
        reader_intent_fingerprint=intent["intent_fingerprint"],
        composition_plan_fingerprint=plan["plan_fingerprint"],
    )
    route_envelope = {
        "owner": owner,
        "profile": route[ROUTE_PROFILE_FIELD[owner]],
        "schema_name": ROUTE_SCHEMA[owner],
        "extension_fingerprint": route["extension_fingerprint"],
        "native_receipt_fingerprints": list(native_dependency_receipt_fingerprints),
    }
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
        "native_dependency_receipt_fingerprints": list(native_dependency_receipt_fingerprints),
        "content_authority_fingerprints": dict(content_authority_fingerprints),
    }
    brief["brief_fingerprint"] = fingerprint(brief)
    require_schema("reader-brief.schema.json", brief, label="ReaderBrief")
    return brief


def _classify_block(text: str) -> tuple[str, str, int]:
    stripped = text.strip()
    first = stripped.splitlines()[0] if stripped else ""
    heading = re.match(r"^(#{1,6})\s+(.+)$", first)
    if heading:
        return "heading", "other", len(heading.group(1))
    if first.startswith("```"):
        return "code", "other", 0
    if all(line.lstrip().startswith(">") for line in stripped.splitlines() if line.strip()):
        return "quote", "prose", 0
    lines = [line for line in stripped.splitlines() if line.strip()]
    if lines and all(LIST_LINE.match(line) for line in lines):
        return "list", "functional_list", 0
    if len(lines) >= 2 and all("|" in line for line in lines):
        return "table", "table", 0
    return "paragraph", "prose", 0


def build_artifact_map(
    artifact_path: str | Path,
    *,
    map_id: str,
    language: str,
    artifact_format: str | None = None,
) -> dict[str, Any]:
    path = Path(artifact_path).expanduser().resolve()
    if not path.is_file():
        raise ValidationError("artifact_path does not identify a current file")
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("ArtifactMap currently requires UTF-8 text or Markdown") from exc
    fmt = artifact_format or ("markdown" if path.suffix.lower() in {".md", ".markdown"} else "text")
    if fmt not in {"text", "markdown"}:
        raise ValidationError("ArtifactMap supports only text and markdown")
    artifact_fp = "sha256:" + __import__("hashlib").sha256(data).hexdigest()
    units: list[dict[str, Any]] = [
        {
            "artifact_unit_id": "artifact:document",
            "parent_unit_id": None,
            "unit_kind": "document",
            "zone": "other",
            "order": 1,
            "heading_level": 0,
            "locator": f"char:0-{len(text)}",
            "start": 0,
            "end": len(text),
            "text": text,
            "content_fingerprint": fingerprint_text(text),
        }
    ]
    heading_stack: list[tuple[int, str]] = []
    order = 2
    block_start: int | None = None
    offset = 0
    blocks: list[tuple[int, int, str]] = []
    for line in text.splitlines(keepends=True):
        if line.strip():
            if block_start is None:
                block_start = offset
        elif block_start is not None:
            blocks.append((block_start, offset, text[block_start:offset].rstrip("\r\n")))
            block_start = None
        offset += len(line)
    if block_start is not None:
        blocks.append((block_start, len(text), text[block_start:].rstrip("\r\n")))
    if not blocks and text:
        blocks.append((0, len(text), text))

    for index, (start, raw_end, block_text) in enumerate(blocks, start=1):
        end = start + len(block_text)
        kind, zone, heading_level = _classify_block(block_text)
        if kind == "heading":
            while heading_stack and heading_stack[-1][0] >= heading_level:
                heading_stack.pop()
            parent_id = heading_stack[-1][1] if heading_stack else "artifact:document"
            unit_id = f"artifact:heading:{index:04d}"
            heading_stack.append((heading_level, unit_id))
            lowered = block_text.casefold()
            if re.search(r"\bappendix\b|附录", lowered):
                zone = "operational_appendix"
            elif re.search(r"\bsources?\b|evidence boundary|来源|资料边界", lowered):
                zone = "source_boundary"
            elif re.search(r"\brecheck\b|复核|出发前", lowered):
                zone = "recheck"
        else:
            parent_id = heading_stack[-1][1] if heading_stack else "artifact:document"
            unit_id = f"artifact:{kind}:{index:04d}"
            parent_zone = next(
                (row["zone"] for row in reversed(units) if row["artifact_unit_id"] == parent_id),
                "other",
            )
            if parent_zone in {"operational_appendix", "source_boundary", "recheck"}:
                zone = parent_zone
        units.append(
            {
                "artifact_unit_id": unit_id,
                "parent_unit_id": parent_id,
                "unit_kind": kind,
                "zone": zone,
                "order": order,
                "heading_level": heading_level,
                "locator": f"char:{start}-{end}",
                "start": start,
                "end": end,
                "text": block_text,
                "content_fingerprint": fingerprint_text(block_text),
            }
        )
        order += 1
    artifact_map = {
        "schema_version": "2.0",
        "map_id": map_id,
        "artifact_path": str(path),
        "artifact_format": fmt,
        "artifact_fingerprint": artifact_fp,
        "language": language,
        "units": units,
        "unmapped_ranges": [],
    }
    artifact_map["map_fingerprint"] = fingerprint(artifact_map)
    require_schema("artifact-map.schema.json", artifact_map, label="ArtifactMap")
    validate_artifact_map(artifact_map)
    return artifact_map


def validate_artifact_map(value: Any) -> dict[str, Any]:
    artifact_map = require_mapping(value, "ArtifactMap")
    require_schema("artifact-map.schema.json", artifact_map, label="ArtifactMap")
    _require_exact_fingerprint(artifact_map, "map_fingerprint")
    path = Path(artifact_map["artifact_path"]).expanduser().resolve()
    if not path.is_file():
        raise ValidationError("ArtifactMap artifact is missing")
    data = path.read_bytes()
    actual_fp = "sha256:" + __import__("hashlib").sha256(data).hexdigest()
    if actual_fp != artifact_map["artifact_fingerprint"]:
        raise ValidationError("ArtifactMap is stale for the current bytes")
    text = data.decode("utf-8")
    unit_ids = set(_ids(artifact_map["units"], "artifact_unit_id", "artifact unit"))
    last_end = 0
    for unit in artifact_map["units"]:
        start, end = unit["start"], unit["end"]
        if end < start or end > len(text):
            raise ValidationError(f"ArtifactMap unit {unit['artifact_unit_id']} is out of bounds")
        if unit["text"] != text[start:end]:
            raise ValidationError(f"ArtifactMap unit {unit['artifact_unit_id']} does not match current text")
        if unit["content_fingerprint"] != fingerprint_text(unit["text"]):
            raise ValidationError(f"ArtifactMap unit {unit['artifact_unit_id']} fingerprint is stale")
        parent = unit["parent_unit_id"]
        if parent is not None and parent not in unit_ids:
            raise ValidationError(f"ArtifactMap unit {unit['artifact_unit_id']} has an unknown parent")
        if unit["unit_kind"] != "document":
            if start < last_end:
                raise ValidationError("non-document ArtifactMap units overlap")
            last_end = end
    return artifact_map


def validate_shared_writing(
    value: Any,
    *,
    artifact_map: Mapping[str, Any],
    reader_brief: Mapping[str, Any],
) -> dict[str, Any]:
    contract = require_mapping(value, "SharedWriting")
    require_schema("shared-writing-contract.schema.json", contract, label="SharedWriting")
    _require_exact_fingerprint(contract, "contract_fingerprint")
    amap = validate_artifact_map(artifact_map)
    brief = require_mapping(reader_brief, "ReaderBrief")
    require_schema("reader-brief.schema.json", brief, label="ReaderBrief")
    _require_exact_fingerprint(brief, "brief_fingerprint")
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


def _audit_finding(
    *,
    code: str,
    unit_id: str,
    message: str,
    owner: str,
    boundary: str,
    index: int,
) -> dict[str, Any]:
    return {
        "finding_id": f"audit:{index:04d}",
        "code": code,
        "severity": "blocking" if code in {
            "stale_binding", "locked_structure_missing", "must_preserve_missing",
            "verbatim_missing", "citation_missing", "workflow_leak", "placeholder",
        } else "repair",
        "message": message,
        "affected_unit_ids": [unit_id],
        "repair_owner": owner,
        "preservation_boundary": boundary,
    }


def build_reader_audit(
    *,
    audit_id: str,
    artifact_map: Mapping[str, Any],
    reader_brief: Mapping[str, Any],
    shared_writing: Mapping[str, Any],
    audited_at: str | None = None,
) -> dict[str, Any]:
    amap = validate_artifact_map(artifact_map)
    brief = require_mapping(reader_brief, "ReaderBrief")
    require_schema("reader-brief.schema.json", brief, label="ReaderBrief")
    contract = validate_shared_writing(shared_writing, artifact_map=amap, reader_brief=brief)
    units = amap["units"]
    text = "\n".join(row["text"] for row in units if row["unit_kind"] != "document")
    plan_by_id = {row["planned_unit_id"]: row for row in brief["composition_plan"]["planned_units"]}
    unit_to_plan: dict[str, Mapping[str, Any]] = {}
    for binding in contract["unit_bindings"]:
        for unit_id in binding["artifact_unit_ids"]:
            unit_to_plan[unit_id] = plan_by_id[binding["planned_unit_id"]]
    findings: list[dict[str, Any]] = []

    def add(code: str, unit_id: str, message: str, boundary: str = "preserve current content boundaries") -> None:
        findings.append(_audit_finding(code=code, unit_id=unit_id, message=message, owner=brief["final_owner"], boundary=boundary, index=len(findings) + 1))

    for row in units:
        if row["unit_kind"] == "document":
            continue
        if PLACEHOLDER.search(row["text"]):
            add("placeholder", row["artifact_unit_id"], "draft placeholder remains in the current artifact")
        if WORKFLOW_LEAK.search(row["text"]):
            add("workflow_leak", row["artifact_unit_id"], "internal workflow or paragraph-planning language leaked into reader-facing copy")
        plan = unit_to_plan.get(row["artifact_unit_id"])
        if row["unit_kind"] == "list" and plan and plan["presentation_mode"] == "prose":
            add("disallowed_list_zone", row["artifact_unit_id"], "a prose-required planned unit is realized as a list or labeled card block")

    headings = {re.sub(r"^#{1,6}\s+", "", row["text"]).strip() for row in units if row["unit_kind"] == "heading"}
    for outline in brief["reader_intent"]["structure"]["requested_outline"]:
        if outline["required"] and outline["title_locked"] and outline["label"] not in headings:
            add("locked_structure_missing", "artifact:document", f"locked heading is missing: {outline['label']}")
    for token in brief["content_boundaries"]["must_preserve_tokens"]:
        if token["token"] not in text:
            add("must_preserve_missing", "artifact:document", f"required exact token is missing: {token['token']}")
    for obligation in brief["content_boundaries"]["verbatim_obligations"]:
        if obligation["text"] not in text:
            add("verbatim_missing", "artifact:document", f"required verbatim text is missing: {obligation['verbatim_id']}")
    for citation in brief["content_boundaries"]["citation_duties"]:
        if citation["marker"] not in text:
            add("citation_missing", "artifact:document", f"required citation marker is missing: {citation['marker']}")

    prose_paragraphs = [row for row in units if row["unit_kind"] == "paragraph" and row["zone"] in {"prose", "narrative"}]
    short = [
        row for row in prose_paragraphs
        if len(row["text"].strip()) < 90 and len(SENTENCE_END.findall(row["text"].strip())) <= 1
    ]
    consecutive_short = 0
    for row in prose_paragraphs:
        if row in short:
            consecutive_short += 1
            if consecutive_short >= 3:
                add("microparagraph_sequence", row["artifact_unit_id"], "three or more short prose blocks create pointillist, card-like reading")
                break
        else:
            consecutive_short = 0
    if prose_paragraphs and len(short) / len(prose_paragraphs) > 0.65 and len(prose_paragraphs) >= 4:
        add("fragmentation_ratio", "artifact:document", "the prose-required body is dominated by one-sentence microparagraphs")

    list_units = [row for row in units if row["unit_kind"] == "list"]
    disallowed_lists = [
        row for row in list_units
        if unit_to_plan.get(row["artifact_unit_id"], {}).get("presentation_mode") == "prose"
    ]
    metrics = {
        "heading_count": sum(row["unit_kind"] == "heading" for row in units),
        "paragraph_count": sum(row["unit_kind"] == "paragraph" for row in units),
        "prose_paragraph_count": len(prose_paragraphs),
        "short_prose_paragraph_count": len(short),
        "list_item_count": sum(len(row["text"].splitlines()) for row in list_units),
        "disallowed_list_item_count": sum(len(row["text"].splitlines()) for row in disallowed_lists),
        "placeholder_count": sum(f["code"] == "placeholder" for f in findings),
        "workflow_leak_count": sum(f["code"] == "workflow_leak" for f in findings),
    }
    dimension_codes = {
        "current_bytes": {"stale_binding"},
        "structure_lock": {"locked_structure_missing"},
        "exact_preservation": {"must_preserve_missing", "verbatim_missing"},
        "citation_placement": {"citation_missing"},
        "list_zones": {"disallowed_list_zone"},
        "fragmentation": {"microparagraph_sequence", "fragmentation_ratio"},
        "binding_coverage": {"stale_binding"},
    }
    dimensions = {
        name: ("repair" if any(f["code"] in codes for f in findings) else "passed")
        for name, codes in dimension_codes.items()
    }
    audit = {
        "schema_version": "2.0",
        "audit_id": audit_id,
        "final_owner": brief["final_owner"],
        "route_decision_fingerprint": brief["route_decision_fingerprint"],
        "reader_intent_fingerprint": brief["reader_intent_fingerprint"],
        "reader_brief_fingerprint": brief["brief_fingerprint"],
        "composition_plan_fingerprint": brief["composition_plan"]["plan_fingerprint"],
        "artifact_map_fingerprint": amap["map_fingerprint"],
        "shared_writing_contract_fingerprint": contract["contract_fingerprint"],
        "artifact_fingerprint": amap["artifact_fingerprint"],
        "visible_unit_ids": [row["artifact_unit_id"] for row in units],
        "structure_metrics": metrics,
        "findings": findings,
        "quality_dimensions": dimensions,
        "status": "repair" if findings else "passed",
        "audited_at": audited_at or utc_now(),
    }
    audit["audit_fingerprint"] = fingerprint(audit)
    require_schema("reader-audit.schema.json", audit, label="ReaderAudit")
    return audit


def _verify_span_evidence(evidence: Mapping[str, Any], units: Mapping[str, Mapping[str, Any]]) -> None:
    unit = units.get(evidence["artifact_unit_id"])
    if unit is None:
        raise ValidationError(f"review evidence references unknown unit {evidence['artifact_unit_id']}")
    if evidence["locator"] != unit["locator"]:
        raise ValidationError("review evidence locator is stale")
    if evidence["excerpt"] not in unit["text"]:
        raise ValidationError("review evidence excerpt is absent from the current unit")
    if evidence["excerpt_fingerprint"] != fingerprint_text(evidence["excerpt"]):
        raise ValidationError("review evidence excerpt fingerprint is stale")


def validate_route_artifact_review(
    value: Any,
    *,
    owner: str,
    route_composition: Mapping[str, Any],
    artifact_map: Mapping[str, Any],
    required_dimensions: Iterable[str],
) -> dict[str, Any]:
    review = require_mapping(value, "route artifact review")
    require_schema("route-artifact-review.schema.json", review, label="route artifact review")
    _require_exact_fingerprint(review, "review_fingerprint")
    amap = validate_artifact_map(artifact_map)
    route = validate_route_composition(
        route_composition,
        owner=owner,
        reader_intent_fingerprint=route_composition["reader_intent_fingerprint"],
        composition_plan_fingerprint=route_composition["composition_plan_fingerprint"],
    )
    if review["final_owner"] != owner or review["route_extension_fingerprint"] != route["extension_fingerprint"]:
        raise ValidationError("route review belongs to a sibling or stale route composition")
    if review["artifact_map_fingerprint"] != amap["map_fingerprint"] or review["artifact_fingerprint"] != amap["artifact_fingerprint"]:
        raise ValidationError("route review does not bind the current ArtifactMap")
    units = {row["artifact_unit_id"]: row for row in amap["units"]}
    present_dimensions = {row["dimension_id"] for row in review["dimensions"]}
    missing = set(required_dimensions) - present_dimensions
    if missing:
        raise ValidationError(f"route review omits required dimensions: {sorted(missing)}")
    for row in review["dimensions"]:
        for evidence in row["evidence"]:
            _verify_span_evidence(evidence, units)
    for finding in review["findings"]:
        _verify_span_evidence(finding["evidence"], units)
    derived = "repair" if review["findings"] or any(row["status"] != "passed" for row in review["dimensions"]) else "passed"
    if review["status"] != derived:
        raise ValidationError("route review status is not derived from current dimensions and findings")
    if bool(review["required_repairs"]) != (derived != "passed"):
        raise ValidationError("route review required_repairs do not match its status")
    return review


def validate_reader_judgment(
    value: Any,
    *,
    artifact_map: Mapping[str, Any],
    reader_brief: Mapping[str, Any],
    shared_writing: Mapping[str, Any],
    deterministic_audit: Mapping[str, Any],
    route_review: Mapping[str, Any],
) -> dict[str, Any]:
    judgment = require_mapping(value, "ReaderJudgment")
    require_schema("reader-judgment.schema.json", judgment, label="ReaderJudgment")
    _require_exact_fingerprint(judgment, "judgment_fingerprint")
    amap = validate_artifact_map(artifact_map)
    brief = require_mapping(reader_brief, "ReaderBrief")
    contract = validate_shared_writing(shared_writing, artifact_map=amap, reader_brief=brief)
    audit = require_mapping(deterministic_audit, "ReaderAudit")
    require_schema("reader-audit.schema.json", audit, label="ReaderAudit")
    _require_exact_fingerprint(audit, "audit_fingerprint")
    review = require_mapping(route_review, "route artifact review")
    require_schema("route-artifact-review.schema.json", review, label="route artifact review")
    _require_exact_fingerprint(review, "review_fingerprint")
    if judgment["producer_id"] == judgment["judge_id"]:
        raise ValidationError("routine ReaderJudgment requires an independent judge context")
    expected = {
        "final_owner": brief["final_owner"],
        "reader_intent_fingerprint": brief["reader_intent_fingerprint"],
        "reader_brief_fingerprint": brief["brief_fingerprint"],
        "composition_plan_fingerprint": brief["composition_plan"]["plan_fingerprint"],
        "artifact_map_fingerprint": amap["map_fingerprint"],
        "shared_writing_contract_fingerprint": contract["contract_fingerprint"],
        "deterministic_audit_fingerprint": audit["audit_fingerprint"],
        "route_audit_fingerprint": review["review_fingerprint"],
        "artifact_fingerprint": amap["artifact_fingerprint"],
    }
    for key, expected_value in expected.items():
        if judgment[key] != expected_value:
            raise ValidationError(f"ReaderJudgment {key} is stale or foreign")
    units = {row["artifact_unit_id"]: row for row in amap["units"]}
    for row in judgment["reverse_outline"]:
        _verify_span_evidence(row["evidence"], units)
    for row in (*judgment["defects"], *judgment["strengths"]):
        _verify_span_evidence(row["evidence"], units)
    score_pass = min(judgment["scores"].values()) >= 4
    blocking = any(row["severity"] == "blocking" for row in judgment["defects"])
    derived = (
        "passed"
        if audit["status"] == review["status"] == "passed"
        and score_pass
        and not blocking
        and not judgment["required_repairs"]
        else "repair"
    )
    if judgment["status"] != derived:
        raise ValidationError("ReaderJudgment status is not derived from the current evidence")
    if judgment["status"] == "passed" and any(row["orphaned"] or row["overloaded"] for row in judgment["reverse_outline"]):
        raise ValidationError("ReaderJudgment cannot pass with orphaned or overloaded units")
    return judgment


DEFAULT_FORBIDDEN_SHORTCUTS = (
    "Do not repair coherence by adding transition words alone.",
    "Do not turn prose into more bullet cards.",
    "Do not delete limitations or citation duties.",
    "Do not copy safe meanings as an allowed-wording script.",
    "Do not explain paragraph jobs in reader-facing meta-language.",
)


def build_repair_request(
    *,
    repair_id: str,
    attempt_number: int,
    reader_brief: Mapping[str, Any],
    artifact_map: Mapping[str, Any],
    shared_writing: Mapping[str, Any],
    deterministic_audit: Mapping[str, Any],
    route_review: Mapping[str, Any],
    judgment: Mapping[str, Any],
    defect_lineage: str,
) -> dict[str, Any]:
    brief = require_mapping(reader_brief, "ReaderBrief")
    amap = validate_artifact_map(artifact_map)
    contract = validate_shared_writing(shared_writing, artifact_map=amap, reader_brief=brief)
    validated = validate_reader_judgment(
        judgment,
        artifact_map=amap,
        reader_brief=brief,
        shared_writing=contract,
        deterministic_audit=deterministic_audit,
        route_review=route_review,
    )
    if validated["status"] == "passed":
        raise ValidationError("a passing ReaderJudgment cannot produce a RepairRequest")
    defect_ids = [row["observation_id"] for row in validated["defects"]]
    target_units = list(dict.fromkeys(
        unit_id
        for row in validated["required_repairs"]
        for unit_id in row["target_unit_ids"]
    ))
    required_changes = [row["required_change"] for row in validated["required_repairs"]]
    preserve_ids = [
        row["content_unit_id"]
        for row in brief["content_boundaries"]["content_units"]
        if row["required"]
    ]
    request = {
        "schema_version": "2.0",
        "repair_id": repair_id,
        "attempt_number": attempt_number,
        "final_owner": brief["final_owner"],
        "source_artifact_fingerprint": amap["artifact_fingerprint"],
        "reader_intent_fingerprint": brief["reader_intent_fingerprint"],
        "reader_brief_fingerprint": brief["brief_fingerprint"],
        "composition_plan_fingerprint": brief["composition_plan"]["plan_fingerprint"],
        "artifact_map_fingerprint": amap["map_fingerprint"],
        "shared_writing_contract_fingerprint": contract["contract_fingerprint"],
        "audit_fingerprint": deterministic_audit["audit_fingerprint"],
        "route_audit_fingerprint": route_review["review_fingerprint"],
        "judgment_fingerprint": validated["judgment_fingerprint"],
        "defect_lineage": defect_lineage,
        "defect_set_fingerprint": fingerprint(sorted(defect_ids)),
        "target_unit_ids": target_units,
        "required_changes": required_changes,
        "preserve_content_unit_ids": preserve_ids,
        "must_preserve_tokens": [row["token"] for row in brief["content_boundaries"]["must_preserve_tokens"]],
        "forbidden_shortcuts": list(DEFAULT_FORBIDDEN_SHORTCUTS),
    }
    request["request_fingerprint"] = fingerprint(request)
    require_schema("reader-repair-request.schema.json", request, label="ReaderRepairRequest")
    return request


def record_repair_result(
    *,
    request: Mapping[str, Any],
    output_artifact_map: Mapping[str, Any],
    changed_unit_ids: Iterable[str],
    preserved_content_unit_ids: Iterable[str],
    preservation_violations: Iterable[str],
    remaining_defect_ids: Iterable[str],
) -> dict[str, Any]:
    repair = require_mapping(request, "ReaderRepairRequest")
    require_schema("reader-repair-request.schema.json", repair, label="ReaderRepairRequest")
    _require_exact_fingerprint(repair, "request_fingerprint")
    amap = validate_artifact_map(output_artifact_map)
    remaining_fp = fingerprint(sorted(remaining_defect_ids))
    changed = list(changed_unit_ids)
    violations = list(preservation_violations)
    same_bytes = repair["source_artifact_fingerprint"] == amap["artifact_fingerprint"]
    same_defects = remaining_fp == repair["defect_set_fingerprint"]
    if violations:
        progress = "blocked"
    elif same_bytes or same_defects:
        progress = "no_progress"
    else:
        progress = "progressed"
    result = {
        "schema_version": "2.0",
        "repair_id": repair["repair_id"],
        "request_fingerprint": repair["request_fingerprint"],
        "defect_lineage": repair["defect_lineage"],
        "input_artifact_fingerprint": repair["source_artifact_fingerprint"],
        "output_artifact_fingerprint": amap["artifact_fingerprint"],
        "changed_unit_ids": changed,
        "preservation_check": {
            "status": "failed" if violations else "passed",
            "preserved_content_unit_ids": list(preserved_content_unit_ids),
            "violations": violations,
        },
        "remaining_defect_set_fingerprint": remaining_fp,
        "progress_status": progress,
        "rerun_required": [
            "artifact_map", "shared_writing", "deterministic_audit",
            "route_audit", "reader_judgment",
        ],
    }
    result["result_fingerprint"] = fingerprint(result)
    require_schema("reader-repair-result.schema.json", result, label="ReaderRepairResult")
    return result


def validate_revision_provenance(value: Any, *, target_artifact_fingerprint: str) -> dict[str, Any]:
    provenance = require_mapping(value, "revision provenance")
    require_schema("revision-provenance.schema.json", provenance, label="revision provenance")
    _require_exact_fingerprint(provenance, "provenance_fingerprint")
    if provenance["target_artifact_fingerprint"] != target_artifact_fingerprint:
        raise ValidationError("revision provenance is stale for the current artifact")
    source_ids = _ids(provenance["unit_treatments"], "source_unit_id", "source unit treatment")
    if provenance["artifact_mode"] == "revise_existing" and not source_ids:
        raise ValidationError("revise_existing requires source-unit treatments")
    return provenance


__all__ = [
    "build_artifact_map",
    "build_reader_audit",
    "build_reader_brief",
    "build_repair_request",
    "record_repair_result",
    "validate_artifact_map",
    "validate_composition_plan",
    "validate_reader_intent",
    "validate_reader_judgment",
    "validate_revision_provenance",
    "validate_route_artifact_review",
    "validate_route_composition",
    "validate_shared_writing",
    "validate_writing_request",
]
