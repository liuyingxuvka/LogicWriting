"""Build LogicWriting's explicit source-to-obligation surface inventory.

This is an author-side tool.  SkillGuard supplies only the structural source
observation; the exact path-to-obligation decisions live in
``logic_writing_surface_rules.json``.  A newly added, removed, or otherwise
unlisted source path stops generation so the denominator cannot silently grow
or shrink.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping


OBLIGATIONS = (
    "routing",
    "specialist-authority",
    "investigation-evidence",
    "academic-provenance",
    "fiction-native",
    "travel-native",
    "shared-writing",
    "reader-actual-artifact",
    "final-closure",
    "release-integrity",
    "model-depth",
)
RULES_PATH = Path(__file__).with_name("logic_writing_surface_rules.json")
ROUTE_SOURCES = {
    "route:logic-writing:router": "SKILL.md",
    "route:logic-writing:investigation": "references/routes/investigation.md",
    "route:logic-writing:academic-writing": "references/routes/academic-writing.md",
    "route:logic-writing:fiction-writing": "references/routes/fiction-writing.md",
    "route:logic-writing:travel-guide": "references/routes/travel-guide.md",
}
LOCAL_ARTIFACT_PATHS = frozenset({
    "scripts/_common.py", "scripts/build_artifact_map.py",
    "scripts/build_reader_brief.py", "scripts/build_reader_brief_receipt.py",
    "scripts/build_reader_repair.py", "scripts/record_reader_repair.py",
    "scripts/reader_execution.py", "scripts/reader_pipeline.py",
    "scripts/reader_receipts.py", "scripts/receipt_store.py",
    "scripts/receipt_authority.py", "scripts/derive_closure.py",
})
CLAIM_BOUNDARY = (
    "The inventory binds the current LogicWriting skill-root source observation "
    "to explicit target-owned obligations and checks. It proves neither domain "
    "correctness, provider quality, installation currentness, release, nor future prose behavior."
)


def load_skillguard(explicit_root: Path | None = None) -> Any:
    """Load the author dependency without a consumer-side fallback."""

    root = explicit_root or Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills" / "skillguard"
    scripts = root.resolve() / "scripts"
    if not (scripts / "skillguard_v2" / "surface_inventory.py").is_file():
        raise ValueError("author SkillGuard installation missing; supply --skillguard-root")
    sys.path.insert(0, str(scripts))
    from skillguard_v2 import surface_inventory

    return surface_inventory


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def _hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _rules() -> dict[str, tuple[str, ...]]:
    raw = _read(RULES_PATH)
    result: dict[str, tuple[str, ...]] = {}
    for path, ids in raw.items():
        if not isinstance(path, str) or not isinstance(ids, list) or not ids:
            raise ValueError(f"invalid explicit rule: {path!r}")
        normalized = tuple(dict.fromkeys(str(item) for item in ids))
        unknown = set(normalized) - set(OBLIGATIONS)
        if unknown:
            raise ValueError(f"unknown obligation in explicit rule {path}: {sorted(unknown)}")
        result[path] = normalized
    return result


def _category(kind: str) -> str:
    return {"option": "command", "export": "api", "prompt": "template"}.get(kind, kind)


def _schema_check(payload: Mapping[str, Any], name: str, scanner: Any) -> None:
    # Reuse the target's current offline Draft 2020-12 interpreter. This author
    # tool supplies the exact provider schema resource instead of changing the
    # consumer's canonical schema-name registry or requiring a new package.
    module_name = "logic_writing_author_schema_runtime"
    runtime = sys.modules.get(module_name)
    if runtime is None:
        path = Path(__file__).resolve().parents[2] / "skills/logic-writing/scripts/schema_validation.py"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ValueError("target schema runtime unavailable")
        runtime = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = runtime
        spec.loader.exec_module(runtime)
    schema_root = Path(scanner.__file__).resolve().parents[2] / "assets" / "schemas"
    schema = _read(schema_root / name)
    if schema.get("$schema") != runtime.DRAFT_2020_12:
        raise ValueError("provider surface schema dialect is not Draft 2020-12")
    resource = runtime._SchemaResource(name, schema["$id"], schema)
    registry = object.__new__(runtime._LocalSchemaRegistry)
    registry.by_name = {name: resource}
    registry.by_uri = {schema["$id"]: resource}
    registry._check_schema_node(schema, resource, "#", is_root=True)
    errors = runtime._Draft202012Runtime(registry).validate(payload, schema, resource)
    if errors:
        raise ValueError(f"{name} schema invalid: {[(row.path, row.message) for row in errors]}")


def _validate_native(root: Path, scanner: Any, mapping: Mapping[str, Any], inventory: Mapping[str, Any]) -> None:
    _schema_check(mapping, "skillguard_surface_semantic_map_v1.schema.json", scanner)
    _schema_check(inventory, "skillguard_surface_inventory_v1.schema.json", scanner)
    source = _read(root / "skills/logic-writing/.skillguard/contract-source.json")
    native_checks = source["depth_profile"]["native_check_ids"]
    deepening = source["depth_profile"]["model_deepening_check_id"]
    findings = list(scanner.validate_surface_inventory(
        inventory, target_skill_id="logic-writing", native_check_ids=native_checks,
        model_deepening_check_id=deepening,
    ))
    findings.extend(scanner.validate_full_surface_inventory(
        inventory, target_root=root / "skills/logic-writing", command_surface=(),
        route_entries=(), command_handlers=None, native_check_ids=native_checks,
        model_deepening_check_id=deepening,
    ))
    if findings:
        raise ValueError(f"surface_inventory_invalid: {[row.to_dict() for row in findings]}")


def validate_outputs(root: Path, scanner: Any, mapping: Mapping[str, Any], inventory: Mapping[str, Any]) -> None:
    """Check structure AND exact target-authored semantics against current source.

    Re-signing a row cannot license another obligation, owner or surface. The
    current explicit rules and compiled declarations are reconstructed instead
    of accepting a self-consistent caller map as semantic authority.
    """
    _validate_native(root, scanner, mapping, inventory)
    expected_mapping, expected_inventory = build_inventory(root, scanner)
    if mapping != expected_mapping:
        raise ValueError("surface_semantic_map_stale_or_mismatched: regenerate from current explicit author rules")
    if inventory != expected_inventory:
        raise ValueError("surface_inventory_stale_or_mismatched: current source and target bindings differ")


def build_inventory(root: Path, scanner: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    root = root.resolve()
    skill = root / "skills" / "logic-writing"
    control = skill / ".skillguard"
    source = _read(control / "contract-source.json")
    compiled = _read(control / "compiled-contract.json")
    checks = {str(row["check_id"]): row for row in source.get("checks", ())}
    obligations = {str(row["obligation_id"]): row for row in compiled.get("obligations", ())}
    expected_ids = {f"obligation:logic-writing:{suffix}" for suffix in OBLIGATIONS}
    if set(obligations) != expected_ids:
        raise ValueError(f"compiled obligation denominator differs: {sorted(set(obligations) ^ expected_ids)}")
    depth = source.get("depth_profile")
    if not isinstance(depth, Mapping):
        raise ValueError("depth_profile is required")
    native_checks = tuple(str(value) for value in depth.get("native_check_ids", ()))
    deepening = str(depth.get("model_deepening_check_id", ""))
    if not deepening or deepening not in native_checks:
        raise ValueError("model-depth must be a declared native check")
    rules = _rules()
    scan = scanner.discover_full_source_surfaces(skill, command_surface=(), route_entries=(), command_handlers=None)
    if scan.findings:
        raise ValueError(f"unclean source discovery: {[row.to_dict() for row in scan.findings]}")
    observed_paths = set(scan.source_paths)
    ruled_paths = set(rules)
    if observed_paths != ruled_paths:
        raise ValueError(
            "explicit source-rule denominator differs: "
            f"missing_rules={sorted(observed_paths - ruled_paths)} "
            f"orphan_rules={sorted(ruled_paths - observed_paths)}"
        )
    owner_id = str(source["native_route_owner"])
    routes = {row["route_id"]: row for row in compiled["routes"]}
    if set(routes) != set(ROUTE_SOURCES) or set(routes) != set(depth["native_route_ids"]):
        raise ValueError("current native route denominator differs from the five declared target routes")
    if any(row["owner_id"] != owner_id for row in routes.values()):
        raise ValueError("current native route owner differs from target declaration")
    component_rules: dict[str, set[str]] = {}
    for surface in scan.surfaces:
        if surface.review_granularity == "component":
            component_rules.setdefault(surface.review_group_id, set()).update(rules[surface.source_path])
    rows: list[dict[str, Any]] = []
    inverse: dict[str, list[str]] = {obligation_id: [] for obligation_id in sorted(obligations)}
    for surface in sorted(scan.surfaces, key=lambda row: row.surface_id):
        suffixes = sorted(component_rules[surface.review_group_id]) if surface.review_granularity == "component" else sorted(rules[surface.source_path])
        obligation_ids = [f"obligation:logic-writing:{suffix}" for suffix in suffixes]
        required = sorted({
            check_id
            for obligation_id in obligation_ids
            for check_id in obligations[obligation_id].get("required_check_ids", ())
        })
        adequacy = sorted(set(required) | {deepening, "check:logic-writing:contract-calibration"})
        if not set(adequacy) <= set(checks):
            raise ValueError(f"surface {surface.surface_id} references an undeclared check")
        intent = "intent:logic-writing:surface:" + hashlib.sha256("|".join(f"decision:logic-writing:{suffix}" for suffix in suffixes).encode("utf-8")).hexdigest()[:24]
        row = surface.to_dict()
        row.update({
            "disposition": "governed",
            "intent_id": intent,
            "owner_id": owner_id,
            "obligation_ids": obligation_ids,
            "model_obligation_ids": obligation_ids,
            "required_check_ids": required,
            "adequacy_check_ids": adequacy,
            "execution_owner_ids": sorted({str(checks[cid]["execution_owner_id"]) for cid in adequacy}),
            "evidence_subject_ids": sorted({str(checks[cid]["evidence_subject_id"]) for cid in adequacy}),
            "lifecycle_phase": "author-maintenance" if surface.source_path.startswith(".skillguard/") else "consumer-use",
            "consumer_exposure": "author-only" if surface.source_path.startswith(".skillguard/") else "installed-consumer",
            "write_authority": "author-repository" if surface.source_path.startswith(".skillguard/") else (
                "local-artifact-owner" if surface.source_path in LOCAL_ARTIFACT_PATHS or surface.kind in {"effect", "recovery", "installer"}
                else "read-only-input"
            ),
        })
        rows.append(row)
        for obligation_id in obligation_ids:
            inverse[obligation_id].append(surface.surface_id)
    if any(not values for values in inverse.values()):
        raise ValueError(f"obligation has no governed source surface: {[key for key, value in inverse.items() if not value]}")
    model_bindings = [
        {
            "obligation_id": obligation_id,
            "disposition": "governed",
            "surface_ids": sorted(surface_ids),
            "reason": "The explicit author rule binds these current source observations to this target-owned obligation.",
            "proof_ref": ".skillguard/surface-semantic-map.json#decision_rules",
        }
        for obligation_id, surface_ids in sorted(inverse.items())
    ]
    decision_rules = [
        {
            "rule_id": f"decision:logic-writing:{suffix}",
            "model_obligation_ids": [f"obligation:logic-writing:{suffix}"],
            "source_paths": sorted(path for path, ids in rules.items() if suffix in ids),
            "reason": f"Current LogicWriting source paths explicitly assigned to the {suffix} obligation.",
            "proof_ref": ".skillguard/contract-source.json#closure_profiles",
        }
        for suffix in OBLIGATIONS
    ]
    mapping: dict[str, Any] = {
        "schema_version": "skillguard.surface_semantic_map.v1",
        "map_id": "map:logic-writing:surface-semantics",
        "target_skill_id": "logic-writing",
        "source_discovery_fingerprint": scan.discovery_fingerprint,
        "full_surface_ids": [row["surface_id"] for row in rows],
        "current_obligation_ids": sorted(obligations),
        "decision_rules": decision_rules,
        "surface_bindings": [
            {
                "surface_id": row["surface_id"],
                "model_obligation_ids": row["model_obligation_ids"],
                "rule_ids": [value.replace("obligation:", "decision:", 1) for value in row["model_obligation_ids"]],
                "decision": "explicit-author-component-group-closure" if row["review_granularity"] == "component" else "explicit-author-rule",
            }
            for row in rows
        ],
        "obligation_bindings": model_bindings,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    mapping["map_hash"] = _hash(mapping)
    all_check_ids = sorted(native_checks)
    compact_rows = []
    for route_id, route in sorted(routes.items()):
        path = ROUTE_SOURCES[route_id]
        required = sorted({
            check_id for suffix in rules[path]
            for check_id in obligations[f"obligation:logic-writing:{suffix}"]["required_check_ids"]
        } | {cid for cid, check in checks.items() if check["native_route_id"] == route_id})
        adequacy = sorted(set(required) | {deepening, "check:logic-writing:contract-calibration"})
        compact_rows.append({
            "surface_id": route_id, "kind": "route", "name": route_id,
            "disposition": "governed", "intent_id": route_id.replace("route:", "intent:", 1),
            "owner_id": route["owner_id"], "route_id": route_id,
            "function_id": route["function_id"], "required_check_ids": required,
            "adequacy_check_ids": adequacy,
            "evidence_subject_ids": sorted({str(checks[cid]["evidence_subject_id"]) for cid in adequacy}),
            "source_path": path,
            "source_fingerprint": "sha256:" + hashlib.sha256((skill / path).read_bytes()).hexdigest(),
        })
    observed_categories = {_category(row.kind) for row in scan.surfaces}
    inventory: dict[str, Any] = {
        "schema_version": "skillguard.surface_inventory.v1",
        "inventory_id": "inventory:logic-writing:surfaces",
        "target_skill_id": "logic-writing",
        "source_kind": "target-owned-full-source-discovery",
        "source_paths": list(scan.source_paths),
        "observed_surface_ids": [row["surface_id"] for row in compact_rows],
        "owner_ids": sorted({owner_id} | {str(checks[cid]["execution_owner_id"]) for cid in all_check_ids}),
        "rows": compact_rows,
        "current_obligation_ids": sorted(obligations),
        "model_obligations": model_bindings,
        "full_surface_ids": mapping["full_surface_ids"],
        "full_surfaces": rows,
        "surface_category_dispositions": {
            category: {
                "disposition": "governed" if category in observed_categories else "not_applicable_proven",
                "reason": f"The current source observation {'contains' if category in observed_categories else 'does not contain'} {category} surfaces; native package behavior remains outside this skill-root inventory.",
                "proof_ref": ".skillguard/surface-inventory.json#full_discovery_fingerprint",
            }
            for category in scanner.FULL_SURFACE_CATEGORIES
        },
        "full_discovery_fingerprint": scan.discovery_fingerprint,
        "adequacy_check_ids": all_check_ids,
        "model_deepening_check_id": deepening,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    inventory["inventory_hash"] = scanner.surface_inventory_hash(inventory)
    _validate_native(root, scanner, mapping, inventory)
    return mapping, inventory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--member", choices=["logic-writing"], required=True)
    parser.add_argument("--skillguard-root", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    scanner = load_skillguard(args.skillguard_root)
    mapping, inventory = build_inventory(args.root, scanner)
    control = args.root / "skills" / "logic-writing" / ".skillguard"
    for name, payload in (("surface-semantic-map.json", mapping), ("surface-inventory.json", inventory)):
        path = control / name
        if args.write:
            _write(path, payload)
        elif not path.is_file() or _read(path) != payload:
            raise ValueError(f"stale or missing {name}; regenerate from the explicit author rules")
    print(json.dumps({"status": "written" if args.write else "current", "surface_count": len(inventory["full_surfaces"]), "source_path_count": len(inventory["source_paths"]), "inventory_hash": inventory["inventory_hash"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
