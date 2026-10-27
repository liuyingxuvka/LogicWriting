"""Read one saved ResearchGuard verdict and import its source-owned anchors.

This module never invokes ResearchGuard, performs retrieval or licenses stronger
wording. Source files and reports remain native ResearchGuard data.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from _common import ValidationError, require_mapping, input_digest_problems


SEARCH_STATES = {"continue_search", "stop_sufficient", "blocked_unresolved_critical", "not_run"}
LICENSES = {"assert", "qualify", "withhold"}
VERDICT_FIELDS = {"search", "root_claim", "live_hypotheses", "contested", "errors"}


def assess_research_verdict(document: Any, alternatives=()) -> dict[str, Any]:
    """Assess a saved native result; disagreements remain non-blocking risks."""
    unreadable = {"status": "unreadable", "passed": False,
                  "reason": "ResearchGuard report has no valid five-key verdict", "residual_risk": []}
    if not isinstance(document, Mapping) or not isinstance(document.get("verdict"), Mapping):
        return unreadable
    verdict = document["verdict"]
    if set(verdict) != VERDICT_FIELDS:
        return unreadable
    errors, live, root = verdict["errors"], verdict["live_hypotheses"], verdict["root_claim"]
    if (isinstance(errors, bool) or not isinstance(errors, int) or errors < 0
            or not isinstance(verdict["search"], str) or verdict["search"] not in SEARCH_STATES or not isinstance(verdict["contested"], bool)
            or not isinstance(live, list) or any(not isinstance(item, str) or not item for item in live)
            or len(set(live)) != len(live)):
        return unreadable
    if root is not None and (not isinstance(root, Mapping) or set(root) != {"id", "wording_license", "reason"}
            or not isinstance(root["id"], str) or not root["id"]
            or not isinstance(root["wording_license"], str) or root["wording_license"] not in LICENSES or not isinstance(root["reason"], str)):
        return unreadable
    if not isinstance(alternatives, (list, tuple)):
        raise ValidationError("content alternatives must be a list")
    rows = list(alternatives)
    hypotheses = document.get("hypotheses", [])
    if not isinstance(hypotheses, list) or any(not isinstance(row, Mapping) or not isinstance(row.get("id"), str) for row in hypotheses):
        return unreadable
    alternative_ids = {row.get("alternative_id") for row in rows if isinstance(row, Mapping)}
    root_id = root["id"] if root else None
    # A source-only question with one live primary hypothesis does not imply an
    # unavailable assert license. Multiple hypotheses or a declared alternative do.
    competitors = bool(set(live) - {root_id}) if root else len(live) > 1 or bool(set(live) & alternative_ids)
    reasons, risks = [], []
    if errors:
        reasons.append(f"research errors {errors}")
    if verdict["search"] != "stop_sufficient":
        reasons.append(f"search {verdict['search']}")
    if competitors and (root is None or root["wording_license"] != "assert"):
        reasons.append(f"root claim {root_id} {root['wording_license']}: {root['reason']}" if root else "root claim unavailable with live alternatives")
    declared = {row.get("id") for row in hypotheses}
    declared.update(live)
    if root_id:
        declared.add(root_id)
    for row in rows:
        if isinstance(row, Mapping) and row.get("alternative_id") in declared:
            if (row.get("status") == "live") != (row["alternative_id"] in live):
                reasons.append(f"alternative_status_conflict:{row['alternative_id']}")
    if verdict["contested"]:
        risks.append({"defect_id": "research:contested", "reason": "ResearchGuard routes disagree; preserve that disagreement as a residual research risk."})
    if root is None:
        risks.append({"defect_id": "research:root_claim_not_run", "reason": "No native root-claim wording license was produced; search sufficiency does not license assert wording."})
    elif root["wording_license"] != "assert":
        risks.append({"defect_id": "research:wording_boundary", "reason": f"Root claim {root_id} remains {root['wording_license']}: {root['reason']}"})
    if reasons:
        return {"status": "failed", "passed": False, "reason": "; ".join(reasons), "residual_risk": risks}
    reason = "search stop_sufficient; no research errors"
    reason += f"; root claim {root_id} {root['wording_license']}: {root['reason']}" if root else "; source-only result, no assert license"
    return {"status": "passed", "passed": True, "reason": reason, "residual_risk": risks}


def read_research_folder(location: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read the research index and its SourceGuard model; never runs ResearchGuard."""
    if not isinstance(location, (str, Path)) or not str(location).strip():
        raise ValidationError("research_folder must name a ResearchGuard research folder or research.yaml")
    try:
        import yaml
    except ImportError as exc:
        raise ValidationError("reading a ResearchGuard research folder needs PyYAML (it comes with ResearchGuard)") from exc
    index_path = Path(location).expanduser()
    if index_path.is_dir():
        index_path /= "research.yaml"
    try:
        index = require_mapping(yaml.safe_load(index_path.read_text(encoding="utf-8")), "ResearchGuard research index")
        if index.get("schema") != "researchguard.research.v1":
            raise ValidationError("research_folder needs a researchguard.research.v1 index")
        models = require_mapping(index.get("models"), "research models")
        source_path = models.get("source")
        if not isinstance(source_path, str) or not source_path:
            raise ValidationError("research_folder must name models.source")
        model = require_mapping(yaml.safe_load((index_path.parent / source_path).read_text(encoding="utf-8")), "SourceGuard model")
    except (OSError, yaml.YAMLError) as exc:
        raise ValidationError(f"cannot read research_folder {location}: {exc}") from exc
    return index, model


def research_report_identity_problems(document: Any, research_folder: Any) -> list[str]:
    """A saved research report counts only while its declared input bytes match."""
    if not isinstance(research_folder, (str, Path)) or not str(research_folder).strip():
        return ['research_report_unbound:research_folder']
    base = Path(research_folder).expanduser()
    if base.name == 'research.yaml':
        base = base.parent
    return input_digest_problems(document, base, 'research.yaml', 'research_report_stale')


def relation_for_root_claim(rows: Any, root_id: str | None) -> str:
    """The anchor relation for the root claim: oppose > limit > support; unknown is context."""
    found = {row.get("direction") for row in rows if isinstance(row, Mapping) and row.get("hypothesis") == root_id} if (
        root_id and isinstance(rows, list)) else set()
    for direction, relation in (("oppose", "counter"), ("limit", "limit"), ("support", "support")):
        if direction in found:
            return relation
    return "context"


def research_directions(report_path: Any, research_folder: Any) -> dict[str, str]:
    """Relations of the saved report's anchors for its root claim; empty without a report."""
    if report_path is None:
        return {}
    import json
    try:
        document = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise ValidationError(f"cannot read research_status {report_path}: {exc}") from exc
    problems = research_report_identity_problems(document, research_folder)
    if problems:
        raise ValidationError("; ".join(problems))
    verdict = document.get("verdict")
    root = verdict.get("root_claim") if isinstance(verdict, Mapping) else None
    root_id = root.get("id") if isinstance(root, Mapping) else None
    return {row["anchor"]: relation_for_root_claim(row.get("directions"), root_id)
            for row in document.get("evidence", []) if isinstance(row, Mapping) and isinstance(row.get("anchor"), str)}


def fill_anchors_from_research(request: dict[str, Any]) -> dict[str, Any]:
    """Import missing anchors atomically; handwritten ownership conflicts fail."""
    if "sourceguard_model" in request:
        raise ValidationError("`sourceguard_model` is retired; use research_folder (a ResearchGuard research folder)")
    if "research_folder" not in request:
        if "research_status" in request:
            raise ValidationError("research_status needs research_folder")
        return request
    _index, model = read_research_folder(request["research_folder"])
    directions = research_directions(request.get("research_status"), request["research_folder"])
    source_rows, native_anchors = model.get("sources", []), model.get("anchors", [])
    if not isinstance(source_rows, list) or not isinstance(native_anchors, list):
        raise ValidationError("SourceGuard sources and anchors must be lists")
    sources = {row["source_id"]: row.get("cannot_support_structural_use") for row in source_rows if isinstance(row, Mapping) and row.get("source_id")}
    boundaries = require_mapping(request.get("content_boundaries", {}), "content_boundaries")
    anchors = boundaries.get("evidence_anchors", [])
    if not isinstance(anchors, list):
        raise ValidationError("content_boundaries.evidence_anchors must be a list")
    existing = {}
    for row in anchors:
        row = require_mapping(row, "evidence anchor")
        anchor_id = row.get("anchor_id")
        if anchor_id in existing:
            raise ValidationError(f"duplicate anchor_id:{anchor_id}")
        existing[anchor_id] = row
    additions, seen = [], set()
    for row in native_anchors:
        row = require_mapping(row, "SourceGuard anchor")
        anchor_id = row.get("anchor_id")
        if not isinstance(anchor_id, str) or not anchor_id:
            raise ValidationError("SourceGuard anchor needs anchor_id")
        if anchor_id in seen:
            raise ValidationError(f"duplicate source anchor_id:{anchor_id}")
        seen.add(anchor_id)
        relation = directions.get(anchor_id, "context")
        if anchor_id in existing:
            written = existing[anchor_id]
            if written.get("source_id") != row.get("source_id") or written.get("locator") != row.get("locator"):
                raise ValidationError(f"anchor_conflict:{anchor_id}")
            if {written.get("relation"), relation} == {"support", "counter"}:
                raise ValidationError(f"anchor_relation_conflict:{anchor_id}")
            continue
        additions.append({"anchor_id": anchor_id, "source_id": row.get("source_id"),
                          "locator": row.get("locator"), "relation": relation,
                          "observed_summary": row.get("normalized_summary") or str(row.get("text") or "")[:200],
                          "boundary": sources.get(row.get("source_id")) or "Use only what the quoted passage says."})
    # Commit only after every source row and ownership conflict has been checked.
    if "content_boundaries" not in request:
        request["content_boundaries"] = boundaries
    if "evidence_anchors" not in boundaries:
        boundaries["evidence_anchors"] = anchors
    anchors.extend(additions)
    return request
