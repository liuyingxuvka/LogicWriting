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


SCHEMA = "storyline-design.project_mesh.v1"
REPORT_SCHEMA = "storyline-design.project_mesh_check.report.v1"
NATIVE_OWNERS = {
    "novel_ledger": "novel_ledger_check.py",
    "chapter_interfaces": "chapter_interface_check.py",
    "promise_payoff": "promise_payoff_check.py",
    "model_prose_binding": "model_prose_binding_check.py",
    "voice_style": "voice_style_continuity_check.py",
    "semantic_review": "semantic_review_check.py",
    "longform_closure": "longform_closure_check.py",
}
REPOSITORY_AWARE_NATIVE_OWNERS = {
    "longform_closure_check.py",
    "model_prose_binding_check.py",
    "semantic_review_check.py",
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
    ledger = payloads.get("novel_ledger")
    if isinstance(ledger, dict) and isinstance(ledger.get("novel_ledger"), dict):
        ledger = ledger["novel_ledger"]
    if not isinstance(ledger, dict):
        return
    interfaces = payloads.get("chapter_interfaces") if isinstance(payloads.get("chapter_interfaces"), dict) else {}
    promises = payloads.get("promise_payoff") if isinstance(payloads.get("promise_payoff"), dict) else {}
    binding = payloads.get("model_prose_binding") if isinstance(payloads.get("model_prose_binding"), dict) else {}
    closure = payloads.get("longform_closure") if isinstance(payloads.get("longform_closure"), dict) else {}

    index: dict[str, str] = {}
    hierarchy_rows: list[dict[str, Any]] = []
    hierarchy = ledger.get("hierarchy") if isinstance(ledger.get("hierarchy"), dict) else {}
    for kind in ("books", "volumes", "chapters", "scenes"):
        group = rows(hierarchy, kind)
        hierarchy_rows.extend(group)
        add_ids(index, group, f"hierarchy.{kind}", reporter)
    collections = {
        "story_units": rows(ledger, "story_units"),
        "arcs": rows(ledger, "arcs"),
        "threads": rows(ledger, "threads"),
        "promises": rows(ledger, "promises"),
        "continuity": rows(ledger, "continuity"),
        "chapter_interfaces": rows(interfaces, "chapter_interfaces"),
        "prose_blueprints": rows(interfaces, "prose_blueprints"),
        "reverse_outlines": rows(interfaces, "reverse_outlines"),
        "binding_rows": rows(binding, "binding_rows"),
    }
    for name, group in collections.items():
        add_ids(index, group, name, reporter)
    payoff_rows = rows(promises, "promises")
    ledger_promise_ids = {row.get("id") for row in collections["promises"] if isinstance(row.get("id"), str)}
    payoff_ids = {row.get("id") for row in payoff_rows if isinstance(row.get("id"), str)}
    if payoff_ids != ledger_promise_ids:
        reporter.error("promise_identity_mismatch", "surfaces.promise_payoff", "Promise payoff ids must exactly match the novel-ledger promise ids.")
    closure_id = closure.get("closure_id")
    if isinstance(closure_id, str) and closure_id:
        index[closure_id] = "longform_closure"
    external = set(string_refs(manifest.get("external_nodes")))
    scope = ledger.get("longform_scope") if isinstance(ledger.get("longform_scope"), dict) else {}
    for field in ("series_id", "book_id"):
        if isinstance(scope.get(field), str):
            external.add(scope[field])
    for row in hierarchy_rows:
        require_refs([row.get("parent_id")] if isinstance(row.get("parent_id"), str) else [], index, external, reporter, f"hierarchy.{row.get('id')}.parent_id")
        require_refs(string_refs(row.get("depends_on")), index, external, reporter, f"hierarchy.{row.get('id')}.depends_on")
    for row in collections["story_units"]:
        require_refs(string_refs(row.get("parent_id")), index, external, reporter, f"story_units.{row.get('id')}.parent_id")
        require_refs(string_refs(row.get("downstream_use")), index, external, reporter, f"story_units.{row.get('id')}.downstream_use")
    for row in collections["arcs"]:
        require_refs(string_refs(row.get("scope")) + string_refs(row.get("turning_points")) + string_refs(row.get("linked_chapters")), index, external, reporter, f"arcs.{row.get('id')}")
    for row in collections["threads"]:
        require_refs(string_refs(row.get("introduced_by")) + string_refs(row.get("active_in")) + string_refs(row.get("resolved_by")) + string_refs(row.get("deferred_to")), index, external | {"not_applicable"}, reporter, f"threads.{row.get('id')}")
    for row in collections["promises"]:
        require_refs(string_refs(row.get("introduced_by")) + string_refs(row.get("payoff_rows")), index, external, reporter, f"promises.{row.get('id')}")
    for row in collections["continuity"]:
        require_refs(string_refs(row.get("scope")) + string_refs(row.get("first_seen")) + string_refs(row.get("last_checked")) + string_refs(row.get("affected_units")), index, external, reporter, f"continuity.{row.get('id')}")
    for row in collections["chapter_interfaces"]:
        movement_refs = [item.get("promise_id") for item in row.get("promise_movements", []) if isinstance(item, dict) and isinstance(item.get("promise_id"), str)]
        movement_refs += [item.get("arc_id") for item in row.get("arc_movements", []) if isinstance(item, dict) and isinstance(item.get("arc_id"), str)]
        require_refs(string_refs(row.get("chapter_id")) + string_refs(row.get("previous_chapter_id")) + string_refs(row.get("next_chapter_id")) + movement_refs, index, external, reporter, f"chapter_interfaces.{row.get('id')}")
    for row in collections["prose_blueprints"]:
        require_refs(string_refs(row.get("chapter_id")) + string_refs(row.get("source_interface_id")) + string_refs(row.get("scene_order")), index, external, reporter, f"prose_blueprints.{row.get('id')}")
    for row in collections["reverse_outlines"]:
        require_refs(string_refs(row.get("chapter_id")), index, external, reporter, f"reverse_outlines.{row.get('id')}")
    for row in collections["binding_rows"]:
        prose_ref = row.get("prose_ref")
        chapter_ref = prose_ref.split("#", 1)[0] if isinstance(prose_ref, str) else ""
        require_refs(string_refs(chapter_ref) + string_refs(row.get("model_refs")) + string_refs(row.get("downstream_use")), index, external, reporter, f"binding_rows.{row.get('id')}")


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
        run_native_owner(kind, path, scripts, reporter, repository_root)
    for kind, surface in surface_payloads.items():
        if not isinstance(surface, dict):
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
    for kind, surface in surface_payloads.items():
        if not isinstance(surface, dict):
            continue
        value = surface.get("artifact_sha256") or surface.get("manuscript_sha256")
        if isinstance(value, str) and value:
            artifact_hashes[kind] = value.removeprefix("sha256:")
    if len(set(artifact_hashes.values())) > 1:
        reporter.error("artifact_identity_mismatch", "surfaces", "Artifact-bound surfaces do not share one manuscript SHA-256.")
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
