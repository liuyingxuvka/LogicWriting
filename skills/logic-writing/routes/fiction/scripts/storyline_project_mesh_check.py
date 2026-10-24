#!/usr/bin/env python3
"""Validate one StorylineDesign project as a native-owner identity/graph mesh."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

from fiction_plan import PlanContext, member


SCHEMA = "storyline-design.project_mesh.v1"
REPORT_SCHEMA = "storyline-design.project_mesh_check.report.v1"
NATIVE_OWNERS = {
    "novel_ledger": "novel_ledger_check.py",
    "chapter_interfaces": "chapter_interface_check.py",
    "promise_payoff": "promise_payoff_check.py",
    "voice_style": "voice_style_continuity_check.py",
}
REPOSITORY_AWARE_NATIVE_OWNERS = {
    "longform_closure_check.py",
}


class Reporter:
    def __init__(self) -> None:
        self.issues: list[dict[str, str]] = []
        self.native_reports: dict[str, dict[str, Any]] = {}

    def error(self, code: str, path: str, message: str) -> None:
        self.issues.append({"severity": "error", "code": code, "path": path, "message": message})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def contained(base: Path, relative: str, reporter: Reporter, field: str) -> Path | None:
    if not isinstance(relative, str) or not relative.strip():
        reporter.error("invalid_surface_ref", field, "Surface reference must be a non-empty relative path.")
        return None
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        reporter.error("surface_escape", field, "Surface reference escapes the project manifest directory.")
        return None
    if not candidate.is_file():
        reporter.error("surface_missing", field, f"Referenced surface does not exist: {relative}")
        return None
    return candidate


def load_json(path: Path, reporter: Reporter, field: str) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        reporter.error("surface_read_error", field, str(exc))
        return None


def run_native_owner(
    kind: str,
    path: Path,
    scripts_root: Path,
    reporter: Reporter,
    repository_root: Path | None = None,
) -> None:
    owner = NATIVE_OWNERS.get(kind)
    if owner is None:
        reporter.error("unknown_native_owner", f"surfaces.{kind}", f"No native owner is registered for {kind!r}.")
        return
    owner_path = scripts_root / owner
    if not owner_path.is_file():
        reporter.error("native_owner_missing", f"surfaces.{kind}", f"Native owner script is missing: {owner}")
        return
    argv = [sys.executable, str(owner_path), str(path), "--json"]
    if repository_root is not None and owner in REPOSITORY_AWARE_NATIVE_OWNERS:
        argv.extend(["--repo-root", str(repository_root)])
    completed = subprocess.run(
        argv,
        cwd=str(path.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    try:
        native_report = json.loads(completed.stdout)
    except json.JSONDecodeError:
        native_report = {
            "passed": False,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "exit_code": completed.returncode,
        }
    reporter.native_reports[kind] = native_report
    if completed.returncode != 0 or not native_report.get("passed"):
        reporter.error("native_owner_failed", f"surfaces.{kind}", f"{owner} rejected the referenced surface.")


def rows(payload: Any, *path: str) -> list[dict[str, Any]]:
    current = payload
    for part in path:
        if not isinstance(current, dict):
            return []
        current = current.get(part)
    return [item for item in current if isinstance(item, dict)] if isinstance(current, list) else []


def add_ids(index: dict[str, str], entries: Iterable[dict[str, Any]], namespace: str, reporter: Reporter) -> None:
    for position, row in enumerate(entries):
        row_id = row.get("id")
        if not isinstance(row_id, str) or not row_id:
            continue
        if row_id in index:
            reporter.error("duplicate_mesh_id", f"{namespace}[{position}].id", f"{row_id!r} already belongs to {index[row_id]}.")
        else:
            index[row_id] = namespace


def string_refs(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def require_refs(refs: Iterable[str], index: dict[str, str], external: set[str], reporter: Reporter, path: str) -> None:
    for ref in refs:
        normalized = ref.split(":", 1)[1] if ":" in ref and ref.split(":", 1)[0] in {"story_unit", "promise", "arc", "thread", "continuity", "chapter", "scene"} else ref
        if normalized not in index and normalized not in external:
            reporter.error("dangling_mesh_edge", path, f"Reference {ref!r} does not resolve in the project mesh or explicit external nodes.")


def validate_graph(payloads: dict[str, Any], manifest: dict[str, Any], reporter: Reporter) -> None:
    request = payloads.get("composition_plan")
    if not isinstance(request, dict) or not isinstance(request.get("composition_plan"), dict):
        reporter.error("composition_plan_missing", "surfaces.composition_plan", "The project must name its canonical brief request.")
        return
    planned = request["composition_plan"].get("planned_units")
    if not isinstance(planned, list) or not planned or any(not isinstance(row, dict) or not isinstance(row.get("planned_unit_id"), str) for row in planned):
        reporter.error("composition_plan_invalid", "surfaces.composition_plan", "Expected canonical planned units.")
        return
    context = PlanContext(request)
    for row in planned:
        for ref in [row.get("parent_unit_id"), *row.get("downstream_unit_ids", [])]:
            if ref is not None and ref not in context.units:
                reporter.error("dangling_mesh_edge", "composition_plan", f"Unknown planned unit {ref!r}.")
    ledger = payloads.get("novel_ledger", {})
    ledger = ledger.get("novel_ledger", ledger) if isinstance(ledger, dict) else {}
    interfaces = payloads.get("chapter_interfaces", {})
    promises = payloads.get("promise_payoff", {})
    if not isinstance(ledger, dict) or not isinstance(interfaces, dict):
        return
    index = {identifier: "composition_plan" for identifier in context.units}
    collections = {"arcs": rows(ledger, "arcs"), "threads": rows(ledger, "threads"),
                   "promises": rows(ledger, "promises"), "continuity": rows(ledger, "continuity"),
                   "chapter_interfaces": rows(interfaces, "chapter_interfaces"),
                   "prose_blueprints": rows(interfaces, "prose_blueprints"),
                   "reverse_outlines": rows(interfaces, "reverse_outlines")}
    for name, group in collections.items():
        add_ids(index, group, name, reporter)
    for kind, group in (("novel_ledger", rows(ledger, "story_units")),
                        ("chapter_interfaces", collections["chapter_interfaces"]),
                        ("prose_blueprints", collections["prose_blueprints"]),
                        ("reverse_outlines", collections["reverse_outlines"])):
        for row in group:
            member(context, row.get("planned_unit_id"), kind, kind, reporter)
    ledger_ids = {row.get("id") for row in collections["promises"]}
    if {row.get("id") for row in rows(promises, "promises")} != ledger_ids:
        reporter.error("promise_identity_mismatch", "surfaces.promise_payoff", "Promise ids differ from the domain ledger.")
    external = set(string_refs(manifest.get("external_nodes"))) | {"not_applicable"}
    for name, group in collections.items():
        for row in group:
            refs = []
            if name == "arcs":
                refs = string_refs(row.get("scope")) + string_refs(row.get("turning_points")) + string_refs(row.get("linked_chapters"))
            elif name == "threads":
                refs = sum((string_refs(row.get(key)) for key in ("introduced_by", "active_in", "resolved_by", "deferred_to")), [])
            elif name == "promises":
                refs = string_refs(row.get("introduced_by")) + string_refs(row.get("payoff_rows"))
            elif name == "continuity":
                refs = sum((string_refs(row.get(key)) for key in ("scope", "first_seen", "last_checked", "affected_units")), [])
            elif name == "chapter_interfaces":
                refs = [move[key] for key, field in (("promise_id", "promise_movements"), ("arc_id", "arc_movements"))
                        for move in row.get(field, []) if isinstance(move, dict) and isinstance(move.get(key), str)]
            elif name == "prose_blueprints":
                refs = string_refs(row.get("source_interface_id"))
            require_refs(refs, index, external, reporter, f"{name}.{row.get('id')}")


def validate_manifest(
    payload: Any,
    manifest_path: Path,
    scripts_root: Path | None = None,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    reporter = Reporter()
    if not isinstance(payload, dict):
        reporter.error("invalid_root", "$", "Project mesh manifest must be an object.")
        return build_report(manifest_path, reporter, {}, {})
    if payload.get("schema_version") != SCHEMA:
        reporter.error("invalid_schema_version", "schema_version", f"Expected {SCHEMA}.")
    project_id = payload.get("project_id")
    model_revision = payload.get("model_revision")
    if not isinstance(project_id, str) or not project_id:
        reporter.error("missing_project_id", "project_id", "A non-empty project_id is required.")
    if not isinstance(model_revision, str) or not model_revision:
        reporter.error("missing_model_revision", "model_revision", "A non-empty model_revision is required.")
    surfaces = payload.get("surfaces")
    if not isinstance(surfaces, dict) or not surfaces:
        reporter.error("missing_surfaces", "surfaces", "At least one native surface is required.")
        return build_report(manifest_path, reporter, {}, {})
    scripts = scripts_root or Path(__file__).resolve().parent
    surface_paths: dict[str, Path] = {}
    surface_payloads: dict[str, Any] = {}
    for kind, relative in surfaces.items():
        path = contained(manifest_path.parent, relative, reporter, f"surfaces.{kind}")
        if path is None:
            continue
        surface_paths[kind] = path
        surface_payloads[kind] = load_json(path, reporter, f"surfaces.{kind}")
        if kind == "source_requirements":
            from longform_closure_check import validate_source_requirements_evidence
            report = validate_source_requirements_evidence(surface_payloads[kind], str(path))
            reporter.native_reports[kind] = report
            if not report["passed"]:
                reporter.error("native_owner_failed", f"surfaces.{kind}", "Source requirements contain unresolved evidence pointers.")
        elif kind != "composition_plan":
            run_native_owner(kind, path, scripts, reporter, repository_root)
    for kind, surface in surface_payloads.items():
        if not isinstance(surface, dict):
            continue
        if kind == "composition_plan":
            continue
        surface_project = surface.get("project_id")
        if surface_project is None and isinstance(surface.get("novel_ledger"), dict):
            surface_project = surface["novel_ledger"].get("project_id")
        if surface_project != project_id:
            reporter.error("project_identity_mismatch", f"surfaces.{kind}.project_id", f"Expected {project_id!r}, got {surface_project!r}.")
        surface_revision = surface.get("model_revision")
        if surface_revision is None and isinstance(surface.get("novel_ledger"), dict):
            surface_revision = surface["novel_ledger"].get("model_revision")
        if surface_revision != model_revision:
            reporter.error("model_revision_mismatch", f"surfaces.{kind}.model_revision", f"Expected {model_revision!r}, got {surface_revision!r}.")
    artifact_hashes: dict[str, str] = {}
    validate_graph(surface_payloads, payload, reporter)
    return build_report(manifest_path, reporter, surface_paths, artifact_hashes)


def build_report(manifest_path: Path, reporter: Reporter, surface_paths: dict[str, Path], artifact_hashes: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA,
        "source_path": str(manifest_path),
        "passed": not reporter.issues,
        "summary": {
            "error_count": len(reporter.issues),
            "surface_count": len(surface_paths),
            "native_owner_count": len(reporter.native_reports),
            "artifact_identity_count": len(set(artifact_hashes.values())),
        },
        "surface_sha256": {kind: sha256(path) for kind, path in sorted(surface_paths.items())},
        "native_reports": reporter.native_reports,
        "issues": reporter.issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a StorylineDesign project model mesh.")
    parser.add_argument("input")
    parser.add_argument("--repo-root")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    path = Path(args.input).resolve()
    reporter = Reporter()
    payload = load_json(path, reporter, "$input") if path.is_file() else None
    if payload is None:
        if not path.is_file():
            reporter.error("manifest_missing", "$input", f"Manifest does not exist: {path}")
        report = build_report(path, reporter, {}, {})
    else:
        report = validate_manifest(
            payload,
            path,
            repository_root=Path(args.repo_root).resolve() if args.repo_root else None,
        )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Story project mesh check: {'passed' if report['passed'] else 'failed'}")
        for issue in report["issues"]:
            print(f"- [{issue['severity']}] {issue['code']} at {issue['path']}: {issue['message']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
