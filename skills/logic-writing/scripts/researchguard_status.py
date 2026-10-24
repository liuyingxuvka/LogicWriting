"""Read one saved ResearchGuard verdict and import its source-owned anchors.

This module never invokes ResearchGuard, performs retrieval or licenses stronger
wording. Source files and reports remain native ResearchGuard data.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from _common import ValidationError, require_mapping


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
    """Problem codes when a saved status report is not the report of this research folder.

    Compares only identity fields the native report writes: question, hypothesis ids and
    texts in index order, model routes and paths, and the source model's anchor ids.
    """
    if research_folder is None:
        return ["research_report_unbound:research_folder"]
    try:
        index, model = read_research_folder(research_folder)
    except ValidationError:
        return ["research_report_unbound:research_folder"]
    if not isinstance(document, Mapping):
        document = {}
    problems = []
    if document.get("question") != index.get("question"):
        problems.append("research_report_mismatch:question")

    def hypothesis_rows(rows):
        if not isinstance(rows, list):
            return None
        return [(row.get("id"), row.get("text")) if isinstance(row, Mapping) else None for row in rows]
    if hypothesis_rows(document.get("hypotheses")) != hypothesis_rows(index.get("hypotheses", [])):
        problems.append("research_report_mismatch:hypotheses")
    reported = document.get("models")
    reported_paths = ({route: row.get("path") if isinstance(row, Mapping) else None for route, row in reported.items()}
                      if isinstance(reported, Mapping) else None)
    declared = {route: path for route, path in index.get("models", {}).items() if route != "experiment_observations"}
    if reported_paths != declared:
        problems.append("research_report_mismatch:models")
    evidence = document.get("evidence")
    reported_anchors = ({row.get("anchor") for row in evidence if isinstance(row, Mapping)}
                        if isinstance(evidence, list) else None)
    source_anchors = {row.get("anchor_id") for row in model.get("anchors", []) if isinstance(row, Mapping)}
    if reported_anchors != source_anchors:
        problems.append("research_report_mismatch:anchors")
    return problems


def fill_anchors_from_research(request: dict[str, Any]) -> dict[str, Any]:
    """Import missing anchors atomically; handwritten ownership conflicts fail."""
    if "sourceguard_model" in request:
        raise ValidationError("`sourceguard_model` is retired; use research_folder (a ResearchGuard research folder)")
    if "research_folder" not in request:
        return request
    _index, model = read_research_folder(request["research_folder"])
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
        if anchor_id in existing:
            written = existing[anchor_id]
            if written.get("source_id") != row.get("source_id") or written.get("locator") != row.get("locator"):
                raise ValidationError(f"anchor_conflict:{anchor_id}")
            continue
        additions.append({"anchor_id": anchor_id, "source_id": row.get("source_id"),
                          "locator": row.get("locator"), "relation": "support",
                          "observed_summary": row.get("normalized_summary") or str(row.get("text") or "")[:200],
                          "boundary": sources.get(row.get("source_id")) or "Use only what the quoted passage says."})
    # Commit only after every source row and ownership conflict has been checked.
    if "content_boundaries" not in request:
        request["content_boundaries"] = boundaries
    if "evidence_anchors" not in boundaries:
        boundaries["evidence_anchors"] = anchors
    anchors.extend(additions)
    return request
