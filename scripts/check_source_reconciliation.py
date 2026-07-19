from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "logic-writing.source-reconciliation.v1"
ALLOWED_DISPOSITIONS = {
    "extend_existing",
    "keep_route_specific",
    "move_to_shared_kernel",
    "keep_shared_kernel",
    "extend_shared_kernel",
    "keep_fiction_route",
    "keep_fiction_and_share_common_findings",
    "move_common_base_to_shared_kernel",
    "move_identity_to_shared_keep_semantics_in_fiction",
    "move_envelope_to_shared_keep_guard_meaning_native",
    "move_envelope_to_shared_keep_rubric_route_specific",
    "keep_fiction_route_and_reattach_parent",
    "retire_no_alias",
    "retire_replace_with_logic_writing_authority",
    "keep_travel_route",
    "keep_travel_route_and_share_recheck_pattern",
    "keep_travel_and_share_common_pattern",
    "keep_travel_semantics_use_shared_projection",
    "replace_with_shared_reader_projection",
}
REQUIRED_SOURCE_IDS = {
    "logic-writing-public-v1.0.2",
    "storyline-public-v0.4.0",
    "storyline-installed-premerge",
    "storyline-executable-closure-candidate",
    "travel-public-v0.2.0",
    "travel-installed-premerge",
}
REQUIRED_CAPABILITIES = {
    "one-final-owner-routing",
    "research-packet",
    "reader-brief",
    "receipt-authority-and-freshness",
    "actual-artifact-audit",
    "story-contribution",
    "turning-points-and-scene-contracts",
    "promise-payoff",
    "novel-ledger-and-chapter-interface",
    "voice-style-and-register",
    "reader-state-and-variation",
    "real-manuscript-identity",
    "guard-receipt-handoff",
    "semantic-review",
    "story-project-model-mesh",
    "storyline-skill-entrypoint",
    "storyline-skillguard-authority",
    "traveler-profile",
    "source-time-weather-alert-modes",
    "experience-candidates-and-feasibility",
    "route-mesh-lodging-and-fit",
    "negative-evidence-and-reachable-fallback",
    "traveler-native-guide-and-reverse-review",
    "travel-to-storyline-call",
    "travel-skill-entrypoint",
    "travel-skillguard-authority",
}


def finding(code: str, message: str, path: str = "") -> dict[str, str]:
    return {"code": code, "message": message, "path": path}


def validate(root: Path) -> dict[str, Any]:
    path = root / "docs" / "source-reconciliation.json"
    findings: list[dict[str, str]] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"schema_version": SCHEMA, "ok": False, "findings": [finding("record_unreadable", str(exc), str(path))]}

    if payload.get("schema_version") != SCHEMA:
        findings.append(finding("schema_invalid", f"Expected {SCHEMA}.", str(path)))
    if payload.get("target_version") != "2.1.2":
        findings.append(finding("target_version_invalid", "Target version must be 2.1.2.", str(path)))

    sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
    source_ids = [row.get("source_id") for row in sources if isinstance(row, dict)]
    if len(source_ids) != len(set(source_ids)):
        findings.append(finding("duplicate_source_id", "Source ids must be unique.", str(path)))
    missing_sources = sorted(REQUIRED_SOURCE_IDS - set(source_ids))
    if missing_sources:
        findings.append(finding("source_missing", ", ".join(missing_sources), str(path)))
    for row in sources:
        if not isinstance(row, dict):
            findings.append(finding("source_row_invalid", "Every source row must be an object.", str(path)))
            continue
        if not row.get("authority"):
            findings.append(finding("source_authority_missing", str(row.get("source_id", "")), str(path)))
        hash_value = row.get("tree_sha256")
        if hash_value is not None and (not isinstance(hash_value, str) or len(hash_value) != 64):
            findings.append(finding("source_hash_invalid", str(row.get("source_id", "")), str(path)))

    imports = payload.get("imports") if isinstance(payload.get("imports"), list) else []
    if {row.get("route") for row in imports if isinstance(row, dict)} != {"fiction-writing", "travel-guide"}:
        findings.append(finding("import_route_inventory_invalid", "Exactly fiction-writing and travel-guide imports are required.", str(path)))
    for row in imports:
        if not isinstance(row, dict):
            continue
        target = root / str(row.get("target_root", ""))
        if not target.is_dir():
            findings.append(finding("import_target_missing", str(target), str(path)))
            continue
        for forbidden in row.get("forbidden_active_surfaces", []):
            forbidden_path = target / str(forbidden)
            if forbidden_path.exists():
                findings.append(finding("forbidden_active_surface", str(forbidden_path.relative_to(root)), str(path)))
        unknown_sources = sorted(set(row.get("source_ids", [])) - set(source_ids))
        if unknown_sources:
            findings.append(finding("import_source_unknown", ", ".join(unknown_sources), str(path)))

    dispositions = payload.get("capability_dispositions") if isinstance(payload.get("capability_dispositions"), list) else []
    capabilities = [row.get("capability") for row in dispositions if isinstance(row, dict)]
    if len(capabilities) != len(set(capabilities)):
        findings.append(finding("duplicate_capability", "Capability dispositions must be unique.", str(path)))
    missing_capabilities = sorted(REQUIRED_CAPABILITIES - set(capabilities))
    if missing_capabilities:
        findings.append(finding("capability_missing", ", ".join(missing_capabilities), str(path)))
    for row in dispositions:
        if not isinstance(row, dict):
            findings.append(finding("capability_row_invalid", "Every capability row must be an object.", str(path)))
            continue
        if row.get("source") not in source_ids:
            findings.append(finding("capability_source_unknown", str(row.get("capability", "")), str(path)))
        if row.get("disposition") not in ALLOWED_DISPOSITIONS:
            findings.append(finding("capability_disposition_invalid", str(row.get("capability", "")), str(path)))

    return {
        "schema_version": SCHEMA,
        "ok": not findings,
        "source_count": len(source_ids),
        "import_count": len(imports),
        "capability_count": len(capabilities),
        "findings": findings,
        "claim_boundary": payload.get("claim_boundary", ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Logic Writing source reconciliation.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = validate(Path(args.root).resolve())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("pass" if report["ok"] else "fail")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
