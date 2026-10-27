"""Reader checks: current reader-chain responsibilities."""
from __future__ import annotations

from world_refs import world_ref_unquoted

from _common import ValidationError, require_exact_fingerprint, fingerprint, fingerprint_text, require_mapping, require_schema, utc_now
from artifact_map import validate_artifact_map
import re
from reader_binding import shared_writing_from_current
from reader_plan_core import validate_route_composition
from reader_rules import PLACEHOLDER, SENTENCE_MARK, WORKFLOW_LEAK, BODY_UNIT_KINDS, CJK, LATIN
from text_extent import measure_text
from typing import Any, Iterable, Mapping


def _measure_extent(text: str, unit: str, metric_id: str | None = None) -> int:
    """Measure reader-facing extent using the declared intent unit."""
    return measure_text(text, unit, metric_id=metric_id)


def _language_mismatch(text: str, language: str) -> bool:
    """Return true only for an obvious whole-document language mismatch."""
    compact = re.sub(r"\s+", "", text)
    cjk = len(CJK.findall(compact))
    latin = len(LATIN.findall(compact))
    normalized = language.casefold()
    if normalized.startswith(("zh", "ja", "ko")):
        return latin >= 30 and cjk == 0
    if normalized.startswith(("en", "de", "fr", "es", "it", "pt")):
        return cjk >= 30 and latin == 0
    return False


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
    contract = shared_writing_from_current(shared_writing, amap=amap, reader_brief=brief)
    return build_reader_audit_from_current(audit_id=audit_id, amap=amap, brief=brief,
                                           contract=contract, audited_at=audited_at)


def build_reader_audit_from_current(*, audit_id, amap, brief, contract, audited_at=None):
    units = amap["units"]
    visible_units = [row for row in units if row["unit_kind"] != "document"]
    text = "\n".join(row["text"] for row in visible_units)
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
        if row["unit_kind"] in {"paragraph", "list", "table", "quote", "scene", "code"} and plan is None:
            add("unbound_body_unit", row["artifact_unit_id"], "an actual body unit is not covered by a binding or explicit disposition")
        if row["unit_kind"] == "list" and plan and plan["presentation_mode"] == "prose":
            add("disallowed_list_zone", row["artifact_unit_id"], "a prose-required planned unit is realized as a list or labeled card block")

    # Sibling planned units must appear in the text in plan order (only bound units take part).
    position = {row["artifact_unit_id"]: index for index, row in enumerate(units)}
    first_position: dict[str, int] = {}
    for binding in contract["unit_bindings"]:
        places = [position[unit_id] for unit_id in binding["artifact_unit_ids"] if unit_id in position]
        if places:
            planned_id = binding["planned_unit_id"]
            first_position[planned_id] = min(places + ([first_position[planned_id]] if planned_id in first_position else []))
    siblings: dict[Any, list[Mapping[str, Any]]] = {}
    for planned in brief["composition_plan"]["planned_units"]:
        if planned["planned_unit_id"] in first_position:
            siblings.setdefault(planned.get("parent_unit_id"), []).append(planned)
    for children in siblings.values():
        previous = None
        for planned in sorted(children, key=lambda row: row.get("order", 0)):
            here = first_position[planned["planned_unit_id"]]
            if previous is not None and here < first_position[previous["planned_unit_id"]]:
                add("plan_order_mismatch", units[here]["artifact_unit_id"],
                    f"planned unit {planned['planned_unit_id']} comes after {previous['planned_unit_id']} in the plan "
                    "but before it in the text")
                break
            previous = planned

    for overclaim in brief['content_boundaries']['prohibited_overclaims']:
        for pattern in overclaim.get('forbidden_patterns', []):
            try:
                matcher = re.compile(pattern, re.IGNORECASE)
            except re.error as exc:
                raise ValidationError(f"overclaim {overclaim['overclaim_id']}: invalid forbidden pattern: {exc}") from exc
            for row in visible_units:
                if row['unit_kind'] in BODY_UNIT_KINDS and matcher.search(row['text']):
                    add('overclaim_pattern', row['artifact_unit_id'], f"forbidden pattern matched overclaim {overclaim['overclaim_id']}")

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
    content_to_artifacts: dict[str, set[str]] = {}
    for binding in contract["unit_bindings"]:
        for content_id in binding["content_unit_ids"]:
            content_to_artifacts.setdefault(str(content_id), set()).update(
                str(unit_id) for unit_id in binding["artifact_unit_ids"]
            )
    units_by_id = {row["artifact_unit_id"]: row for row in visible_units}
    for citation in brief["content_boundaries"]["citation_duties"]:
        marker = citation["marker"]
        if marker not in text:
            add("citation_missing", "artifact:document", f"required citation marker is missing: {marker}")
            continue
        target_ids = {
            unit_id for content_id in citation["content_unit_ids"]
            for unit_id in content_to_artifacts.get(str(content_id), set())
        }
        target_units = [units_by_id[unit_id] for unit_id in target_ids if unit_id in units_by_id]
        placement = citation["placement"]
        placement_ok = False
        if placement in {"footnote", "endnote"}:
            # Markdown/text artifacts have no universal footnote AST.  The
            # marker still has to occur in a real mapped unit; a marker that
            # only appears in a discarded source boundary cannot pass.
            placement_ok = any(marker in row["text"] for row in target_units) or marker in text
        elif placement in {"same_unit", "same_paragraph", "same_sentence"}:
            for row in target_units:
                if marker not in row["text"]:
                    continue
                if placement != "same_sentence":
                    placement_ok = True
                    break
                marker_pos = row["text"].find(marker)
                for match in re.finditer(r"[^.!?。！？]*[.!?。！？]", row["text"]):
                    if match.start() <= marker_pos < match.end():
                        placement_ok = True
                        break
                if placement_ok:
                    break
        if not placement_ok:
            add("citation_placement", "artifact:document", f"citation marker is outside its required {placement}: {citation['citation_id']}")

    prose_paragraphs = [row for row in visible_units if row["unit_kind"] == "paragraph" and row["zone"] in {"prose", "narrative"}]
    short = [
        row for row in prose_paragraphs
        if len(row["text"].strip()) < 90 and len(SENTENCE_MARK.findall(row["text"].strip())) <= 1
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
    fragmentation_applicable = brief["final_owner"] != "fiction-writing" or brief.get("route_extension", {}).get("profile") not in {"reader_native", "story"}
    if fragmentation_applicable and prose_paragraphs and len(short) / len(prose_paragraphs) > 0.65 and len(prose_paragraphs) >= 4:
        add("fragmentation_ratio", "artifact:document", "the prose-required body is dominated by one-sentence microparagraphs")

    list_units = [row for row in units if row["unit_kind"] == "list"]
    disallowed_lists = [
        row for row in list_units
        if unit_to_plan.get(row["artifact_unit_id"], {}).get("presentation_mode") == "prose"
    ]
    metrics = {
        "heading_count": sum(row["unit_kind"] == "heading" for row in visible_units),
        "paragraph_count": sum(row["unit_kind"] == "paragraph" for row in visible_units),
        "prose_paragraph_count": len(prose_paragraphs),
        "short_prose_paragraph_count": len(short),
        "list_item_count": sum(len(row["text"].splitlines()) for row in list_units),
        "disallowed_list_item_count": sum(len(row["text"].splitlines()) for row in disallowed_lists),
        "placeholder_count": sum(f["code"] == "placeholder" for f in findings),
        "workflow_leak_count": sum(f["code"] == "workflow_leak" for f in findings),
        "body_character_count": sum(len(row["text"].strip()) for row in prose_paragraphs),
    }
    minimum = brief["reader_intent"]["extent"]["minimum"]
    maximum = brief["reader_intent"]["extent"]["maximum"]
    extent_unit = brief["reader_intent"]["extent"]["unit"]
    body_text = "\n".join(
        row["text"] for row in visible_units
        if row["unit_kind"] in BODY_UNIT_KINDS and row["zone"] not in {"source_boundary"}
    )
    body_count = _measure_extent(
        body_text,
        extent_unit,
        brief["reader_intent"]["extent"].get("extent_metric_id"),
    )
    metrics["extent_unit"] = extent_unit
    metrics["extent_count"] = body_count
    if body_count < minimum:
        add("extent_below_minimum", "artifact:document", f"actual body extent {body_count} {extent_unit} is below ReaderIntent minimum {minimum}")
    if body_count > maximum:
        add("extent_above_maximum", "artifact:document", f"actual body extent {body_count} {extent_unit} exceeds ReaderIntent maximum {maximum}")
    if _language_mismatch(body_text, brief["reader_intent"]["language"]):
        add("wrong_language", "artifact:document", "the current artifact is predominantly in a different language from ReaderIntent")
    dimension_codes = {
        "current_bytes": {"stale_binding"},
        "structure_lock": {"locked_structure_missing"},
        "exact_preservation": {"must_preserve_missing", "verbatim_missing"},
        "citation_placement": {"citation_missing", "citation_placement"},
        "list_zones": {"disallowed_list_zone"},
        "fragmentation": {"microparagraph_sequence", "fragmentation_ratio"},
        "language_fit": {"wrong_language"},
        "binding_declared": {"unbound_body_unit"},
        "claim_boundaries": {"overclaim_pattern"},
        "plan_order": {"plan_order_mismatch"},
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


def validate_reader_audit_current(
    audit: Mapping[str, Any],
    *,
    artifact_map: Mapping[str, Any],
    reader_brief: Mapping[str, Any],
    shared_writing: Mapping[str, Any],
    rules_version: str = "reader-audit-rules.v2",
) -> dict[str, Any]:
    """Recompute every substantive audit result from current bytes and inputs."""
    candidate = require_mapping(audit, "ReaderAudit")
    require_schema("reader-audit.schema.json", candidate, label="ReaderAudit")
    require_exact_fingerprint(candidate, "audit_fingerprint")
    current = build_reader_audit(
        audit_id=candidate["audit_id"], artifact_map=artifact_map,
        reader_brief=reader_brief, shared_writing=shared_writing,
        audited_at=candidate.get("audited_at"),
    )
    return compare_reader_audit(candidate, current, rules_version=rules_version)


def compare_reader_audit(candidate, current, *, rules_version="reader-audit-rules.v2"):
    candidate = require_mapping(candidate, "ReaderAudit")
    require_schema("reader-audit.schema.json", candidate, label="ReaderAudit")
    require_exact_fingerprint(candidate, "audit_fingerprint")
    ignored = {"audit_id", "audited_at", "audit_fingerprint"}
    left = {key: value for key, value in candidate.items() if key not in ignored}
    right = {key: value for key, value in current.items() if key not in ignored}
    if left != right:
        raise ValidationError(f"ReaderAudit is stale or caller-authored for current {rules_version}")
    return candidate


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
    required_dimensions: Iterable[str] = (),
    review_obligations: Mapping[str, Any] | None = None,
    reader_brief=None,
    shared_writing=None,
) -> dict[str, Any]:
    amap = validate_artifact_map(artifact_map)
    route = validate_route_composition(
        route_composition,
        owner=owner,
        reader_intent_fingerprint=route_composition["reader_intent_fingerprint"],
        composition_plan_fingerprint=route_composition["composition_plan_fingerprint"],
    )
    shared = None
    if reader_brief is not None:
        require_schema('reader-brief.schema.json', reader_brief, label='ReaderBrief')
        if (reader_brief['final_owner'] != owner or
            reader_brief['route_extension']['extension_fingerprint'] != route['extension_fingerprint']):
            raise ValidationError('boundary review ReaderBrief belongs to a sibling or stale route')
        shared = shared_writing_from_current(shared_writing, amap=amap, reader_brief=reader_brief)
    return route_review_from_current(value, owner=owner, route=route, amap=amap,
                                      required_dimensions=required_dimensions, review_obligations=review_obligations,
                                      brief=reader_brief, shared=shared)


def _review_boundary_checks(review, *, brief, shared, amap):
    """Validate the reviewer's quoted boundary declarations against current bindings."""
    units = {row['artifact_unit_id']: row for row in amap['units']}
    body = [row['artifact_unit_id'] for row in sorted(amap['units'], key=lambda row: (row['start'], row['end']))
            if row['unit_kind'] in BODY_UNIT_KINDS]
    dispositions = {row['limitation_id']: row for row in brief['composition_plan'].get('limitation_dispositions', [])
                    if row['disposition'] in {'body', 'note'}}
    limitations = {row['limitation_id']: row for row in brief['content_boundaries']['limitations']}
    overclaims = {row['overclaim_id']: row for row in brief['content_boundaries']['prohibited_overclaims']}
    missing = []
    for kind, key, expected in [('limitation_checks', 'limitation_id', dispositions),
                                ('overclaim_checks', 'overclaim_id', overclaims)]:
        rows = review.get(kind, [])
        ids = [row[key] for row in rows]
        if len(ids) != len(set(ids)):
            raise ValidationError(f'{kind} contains duplicate ids')
        unknown = set(ids) - set(expected)
        if unknown:
            raise ValidationError(f'{kind} names unknown or inapplicable ids: {sorted(unknown)}')
        missing.extend(sorted(set(expected) - set(ids)))
        for row in rows:
            row_id = row[key]
            if row['status'] == 'present' and not row['evidence']:
                raise ValidationError(f'{row_id}: present requires quoted evidence')
            if kind == 'overclaim_checks' and row['status'] == 'absent' and row['evidence']:
                raise ValidationError(f'{row_id}: absent must not carry evidence')
            allowed = set(body)
            if kind == 'limitation_checks':
                targets = set(dispositions[row_id]['destination_unit_ids'])
                allowed = {unit for binding in shared['unit_bindings'] if binding['planned_unit_id'] in targets
                           for unit in binding['artifact_unit_ids']} & set(body)
                if limitations[row_id]['required_placement'] == 'adjacent_unit':
                    allowed |= {body[j] for i, unit in enumerate(body) if unit in allowed
                                for j in (i-1, i+1) if 0 <= j < len(body)}
            for evidence in row['evidence']:
                _verify_span_evidence(evidence, units)
                if evidence['artifact_unit_id'] not in allowed:
                    raise ValidationError(f'{row_id}: excerpt must be in its bound planned unit or permitted adjacent body unit')
    if missing:
        raise ValidationError(f'route review omits required boundary checks: {missing}')


def route_review_from_current(value, *, owner, route, amap, required_dimensions=(), review_obligations=None, brief=None, shared=None):
    review = require_mapping(value, "route artifact review")
    require_schema("route-artifact-review.schema.json", review, label="route artifact review")
    require_exact_fingerprint(review, "review_fingerprint")
    if review["final_owner"] != owner or review["route_extension_fingerprint"] != route["extension_fingerprint"]:
        raise ValidationError("route review belongs to a sibling or stale route composition")
    if review["artifact_map_fingerprint"] != amap["map_fingerprint"] or review["artifact_fingerprint"] != amap["artifact_fingerprint"]:
        raise ValidationError("route review does not bind the current ArtifactMap")
    if review_obligations is not None:
        from review_obligations import validate_review_obligation_manifest
        manifest = validate_review_obligation_manifest(review_obligations, owner=owner)
        manifest_fp = manifest["manifest_fingerprint"]
        if review.get("review_obligation_manifest_fingerprint") != manifest_fp:
            raise ValidationError("route review does not bind the current review obligation manifest")
        required_dimensions = tuple(
            row["dimension_id"] for row in manifest["obligations"]
            if row.get("applicability", "required") == "required"
        )
    if owner == "fiction-writing" and route.get("longform_project"):
        required_dimensions = tuple(dict.fromkeys((*required_dimensions, "explanation_pressure", "variation", "register_ownership")))
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
    if brief is not None:
        if shared is None:
            raise ValidationError('boundary review requires SharedWriting with ReaderBrief')
        _review_boundary_checks(review, brief=brief, shared=shared, amap=amap)
        world_ref_unquoted(brief["composition_plan"], review, shared, lambda span: _verify_span_evidence(span, units))
    elif review.get("world_ref_checks"):
        raise ValidationError("world_ref_checks requires the current ReaderBrief and SharedWriting")
    boundary_repair = (any(row['status'] == 'missing' for row in review.get('limitation_checks', [])) or
                       any(row['status'] == 'present' for row in review.get('overclaim_checks', [])))
    derived = "repair" if boundary_repair or review["findings"] or any(row["status"] != "passed" for row in review["dimensions"]) else "passed"
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
    review_obligations: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    amap = validate_artifact_map(artifact_map)
    brief = require_mapping(reader_brief, "ReaderBrief")
    contract = shared_writing_from_current(shared_writing, amap=amap, reader_brief=brief)
    candidate = require_mapping(deterministic_audit, "ReaderAudit")
    require_schema("reader-audit.schema.json", candidate, label="ReaderAudit")
    require_exact_fingerprint(candidate, "audit_fingerprint")
    current = build_reader_audit_from_current(audit_id=candidate["audit_id"], amap=amap, brief=brief,
                                              contract=contract, audited_at=candidate.get("audited_at"))
    audit = compare_reader_audit(candidate, current)
    return reader_judgment_from_current(value, amap=amap, brief=brief, contract=contract, audit=audit,
                                         route_review=route_review,
                                         review_obligations=review_obligations)


def reader_judgment_from_current(value, *, amap, brief, contract, audit, route_review,
                                   review_obligations=None):
    judgment = require_mapping(value, "ReaderJudgment")
    require_schema("reader-judgment.schema.json", judgment, label="ReaderJudgment")
    require_exact_fingerprint(judgment, "judgment_fingerprint")
    review = require_mapping(route_review, "route artifact review")
    require_schema("route-artifact-review.schema.json", review, label="route artifact review")
    require_exact_fingerprint(review, "review_fingerprint")
    if judgment["judge_kind"] == "independent_context" and judgment["producer_id"] == judgment["judge_id"]:
        raise ValidationError("routine ReaderJudgment requires an independent judge context")
    if review_obligations is not None:
        from review_obligations import validate_review_obligation_manifest
        manifest = validate_review_obligation_manifest(review_obligations)
        if judgment.get("review_obligation_manifest_fingerprint") != manifest["manifest_fingerprint"]:
            raise ValidationError("ReaderJudgment does not bind the current review obligation manifest")
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
    actual_body_ids = {row["artifact_unit_id"] for row in amap["units"] if row["unit_kind"] in {"paragraph", "list", "table", "quote", "scene"}}
    outlined_ids = {row["artifact_unit_id"] for row in judgment["reverse_outline"]}
    if actual_body_ids - outlined_ids:
        raise ValidationError(f"ReaderJudgment reverse outline omits actual units: {sorted(actual_body_ids - outlined_ids)}")
    repair_ids = {ref for row in judgment["required_repairs"] for ref in row["defect_ids"]}
    unrequested = {row["observation_id"] for row in judgment["defects"]} - repair_ids
    if unrequested:
        raise ValidationError(f"ReaderJudgment defects lack repair requests: {sorted(unrequested)}")
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
