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


def research_wording_boundary(document: Mapping[str, Any]) -> tuple[str, str, set[str]] | None:
    """Return the restricted root and only the anchors that directly support that root."""
    root = document.get('verdict', {}).get('root_claim')
    if not isinstance(root, Mapping) or root.get('wording_license') not in ('withhold', 'qualify'):
        return None
    support = set()
    for row in document.get('evidence', []):
        if not isinstance(row, Mapping):
            continue
        directions = row.get('directions')
        if (isinstance(row.get('anchor'), str) and isinstance(directions, list)
                and any(isinstance(direction, Mapping) and direction.get('hypothesis') == root['id']
                        and direction.get('direction') == 'support' for direction in directions)):
            support.add(row['anchor'])
    return root['id'], root['wording_license'], support


def research_report_identity_problems(document: Any, research_folder: Any) -> list[str]:
    """A saved research report counts only while its declared input bytes match."""
    if not isinstance(research_folder, (str, Path)) or not str(research_folder).strip():
        return ["research_report_unbound:research_folder"]
    base = Path(research_folder).expanduser()
    if base.name == "research.yaml":
        base = base.parent
    problems = input_digest_problems(document, base, "research.yaml", "research_report_stale")
    import yaml
    from collections.abc import Mapping

    try:
        index = yaml.safe_load((base / "research.yaml").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return problems
    if not isinstance(index, Mapping) or not isinstance(index.get("models"), Mapping):
        return problems
    digests = document.get("input_digests", []) if isinstance(document, Mapping) else []
    if not isinstance(digests, list):
        digests = []
    declared = {
        row.get("path")
        for row in digests
        if isinstance(row, Mapping) and isinstance(row.get("path"), str)
    }
    required = []
    for name, value in index["models"].items():
        if isinstance(value, str):
            required.append(value)
        elif name == "experiment_observations" and isinstance(value, list):
            required.extend(path for path in value if isinstance(path, str))
    for path in required:
        if path not in declared:
            problems.append("research_report_stale:" + path)
    return list(dict.fromkeys(problems))


def relation_for_root_claim(rows: Any, root_id: str | None) -> str:
    """The anchor relation for the root claim: oppose > limit > support; unknown is context."""
    found = {row.get("direction") for row in rows if isinstance(row, Mapping) and row.get("hypothesis") == root_id} if (
        root_id and isinstance(rows, list)) else set()
    for direction, relation in (("oppose", "counter"), ("limit", "limit"), ("support", "support")):
        if direction in found:
            return relation
    return "context"


def research_directions(report_path: Any, research_folder: Any, *, document=None) -> dict[str, str]:
    """Relations of the saved report's anchors for its root claim; empty without a report."""
    if report_path is None:
        return {}
    if document is None:
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


def validate_anchor_authority(request: Mapping[str, Any], *, document=None) -> list[dict[str, str]]:
    """Check report membership and retain explicitly declared outside-research gaps."""
    if 'research_folder' not in request:
        return []
    status = request.get('research_status')
    if not status:
        raise ValidationError('research_folder needs research_status: run researchguard status <folder> --json --output research-status.json')
    if document is None:
        import json
        try:
            document = json.loads(Path(status).read_text(encoding='utf-8'))
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            raise ValidationError(f'cannot read research_status {status}: {exc}') from exc
    native_ids = set(research_directions(status, request['research_folder'], document=document))
    if not isinstance(document.get('evidence'), list):
        raise ValidationError('ResearchGuard report evidence must be a list')
    boundaries = require_mapping(request.get('content_boundaries', {}), 'content_boundaries')
    anchors = boundaries.get('evidence_anchors', [])
    if not isinstance(anchors, list):
        raise ValidationError('content_boundaries.evidence_anchors must be a list')
    risks = []
    for anchor in anchors:
        anchor = require_mapping(anchor, 'evidence anchor')
        identity = anchor.get('anchor_id')
        reason = anchor.get('outside_research', '')
        reason = reason.strip() if isinstance(reason, str) else ''
        if identity not in native_ids and not reason:
            raise ValidationError(f'anchor_not_in_research:{identity} (the anchor is not in the saved research report; add it to the research folder with researchguard source add-anchor and researchguard sync, then rerun with --refresh-providers, or give outside_research: <reason>)')
        if reason:
            risks.append(dict(defect_id='outside_research:' + identity, reason=reason))
    return risks


def fill_anchors_from_research(request: dict[str, Any]) -> dict[str, Any]:
    """Import missing anchors atomically; handwritten ownership conflicts fail."""
    if "sourceguard_model" in request:
        raise ValidationError("`sourceguard_model` is retired; use research_folder (a ResearchGuard research folder)")
    if "research_folder" not in request:
        if "research_status" in request:
            raise ValidationError("research_status needs research_folder")
        return request
    status = request.get('research_status')
    if not status:
        raise ValidationError('research_folder needs research_status: run researchguard status <folder> --json --output research-status.json')
    import json
    try:
        document=json.loads(Path(status).read_text(encoding='utf-8'))
    except (OSError,UnicodeError,ValueError,TypeError) as exc:
        raise ValidationError(f'cannot read research_status {status}: {exc}') from exc
    directions=research_directions(status,request['research_folder'],document=document)
    evidence=document.get('evidence')
    if not isinstance(evidence,list):
        raise ValidationError('ResearchGuard report evidence must be a list')
    native_anchors=[]
    for row in evidence:
        row=require_mapping(row,'ResearchGuard report evidence')
        if not isinstance(row.get('source'),str) or not row['source']:
            raise ValidationError('ResearchGuard report anchor needs source')
        native_anchors.append({'anchor_id':row.get('anchor'),'source_id':row['source'],
                               'locator':row.get('locator'),'summary':row.get('summary'),
                               'boundary':row.get('boundary')})
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
    validate_anchor_authority(request, document=document)
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
                          "observed_summary": row.get("summary"),
                          "boundary": row.get("boundary") or "Use only what the quoted passage says."})
    # Commit only after every report row and ownership conflict has been checked.
    if "content_boundaries" not in request:
        request["content_boundaries"] = boundaries
    if "evidence_anchors" not in boundaries:
        boundaries["evidence_anchors"] = anchors
    anchors.extend(additions)
    return request
