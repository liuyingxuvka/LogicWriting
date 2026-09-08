"""Check portable route resources and linked example正文 in a consumer stage."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlparse


MARKDOWN_LINK = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")
ROUTES = ("fiction-writing", "travel-guide")


def _posix(value: str) -> str:
    return value.replace("\\", "/")


def _safe_path(root: Path, relative: str, *, base: Path | None = None) -> Path | None:
    value = _posix(relative).split("#", 1)[0].strip()
    if not value or value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", value):
        return None
    candidate = ((base or root) / Path(*PurePosixPath(value).parts)).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _resolve_declared(root: Path, value: str) -> Path | None:
    return _safe_path(root, value)


def _markdown_targets(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return []
    targets: list[str] = []
    for raw in MARKDOWN_LINK.findall(text):
        target = raw.strip().strip('<>')
        parsed = urlparse(target)
        if parsed.scheme or parsed.netloc or target.startswith("#"):
            continue
        targets.append(unquote(parsed.path))
    return targets


def _check_markdown_tree(
    root: Path,
    entrypoint: Path,
    findings: list[dict[str, str]],
    *,
    optional_targets: set[str] | None = None,
    depth: str | None = None,
) -> list[str]:
    seen: set[Path] = set()
    queue = [entrypoint]
    while queue:
        current = queue.pop()
        if current in seen or not current.suffix.lower() in {".md", ".markdown"}:
            continue
        seen.add(current)
        for target in _markdown_targets(current):
            resolved = _safe_path(root, target, base=current.parent)
            if resolved is None:
                findings.append({"code": "unsafe_markdown_reference", "source": current.as_posix(), "target": target})
            elif depth != "longform" and _posix(str(resolved.relative_to(root))) in (optional_targets or set()):
                continue
            elif not resolved.is_file():
                findings.append({"code": "missing_markdown_reference", "source": current.as_posix(), "target": resolved.as_posix()})
            else:
                queue.append(resolved)
    return [path.as_posix() for path in sorted(seen)]


def check_consumer_resource_closure(
    root: Path,
    *,
    manifest_path: Path | None = None,
    route: str | None = None,
    depth: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = manifest_path or root / "skills/logic-writing/references/routes/required-resources.json"
    findings: list[dict[str, str]] = []
    if not manifest_path.is_file():
        return {"check": "consumer-resource-closure", "status": "failed", "routes": [], "findings": [{"code": "manifest_missing", "path": manifest_path.as_posix()}]}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"check": "consumer-resource-closure", "status": "failed", "routes": [], "findings": [{"code": "manifest_invalid", "path": manifest_path.as_posix(), "detail": str(exc)}]}
    routes = manifest.get("routes")
    if not isinstance(routes, dict):
        return {"check": "consumer-resource-closure", "status": "failed", "routes": [], "findings": [{"code": "routes_missing", "path": manifest_path.as_posix()}]}
    selected = [route] if route else list(ROUTES)
    route_results: list[dict[str, Any]] = []
    for name in selected:
        config = routes.get(name)
        if not isinstance(config, dict):
            findings.append({"code": "route_missing", "route": name})
            continue
        entry_value = config.get("entrypoint")
        entry = _resolve_declared(root, entry_value) if isinstance(entry_value, str) else None
        if entry is None or not entry.is_file():
            findings.append({"code": "entrypoint_missing", "route": name, "path": str(entry_value)})
            continue
        route_findings_before = len(findings)
        optional_targets = {_posix(value) for value in config.get("longform_resources", []) if isinstance(value, str)}
        resolved_refs = _check_markdown_tree(root, entry, findings, optional_targets=optional_targets, depth=depth)
        declared_paths = list(config.get("required_resources", []))
        if depth in (None, "longform"):
            declared_paths += list(config.get("longform_resources", []))
        existing_resources: list[str] = []
        for value in declared_paths:
            resource = _resolve_declared(root, value) if isinstance(value, str) else None
            if resource is None or not resource.is_file():
                findings.append({"code": "required_resource_missing", "route": name, "path": str(value)})
            else:
                existing_resources.append(resource.as_posix())
        for value in config.get("fixture_roots", []):
            fixture_root = _resolve_declared(root, value) if isinstance(value, str) else None
            if fixture_root is None or not fixture_root.is_dir():
                findings.append({"code": "fixture_root_missing", "route": name, "path": str(value)})
        associations: list[dict[str, Any]] = []
        for association in config.get("json_associations", []):
            if not isinstance(association, dict):
                findings.append({"code": "association_invalid", "route": name})
                continue
            json_value, text_value = association.get("json_path"), association.get("text_path")
            json_path = _resolve_declared(root, json_value) if isinstance(json_value, str) else None
            text_path = _resolve_declared(root, text_value) if isinstance(text_value, str) else None
            test_only = bool(association.get("test_only"))
            if json_path is None or not json_path.is_file():
                code = "test_only_json_missing" if test_only else "json_association_missing"
                findings.append({"code": code, "route": name, "path": str(json_value)})
            if text_path is None or not text_path.is_file():
                code = "test_only_text_missing" if test_only else "linked_prose_missing"
                findings.append({"code": code, "route": name, "path": str(text_value), "json_path": str(json_value)})
            associations.append({"json_path": str(json_value), "text_path": str(text_value), "test_only": test_only, "present": bool(json_path and json_path.is_file() and text_path and text_path.is_file())})
        route_results.append({"route": name, "entrypoint": entry.as_posix(), "resolved_markdown": resolved_refs, "required_resources": existing_resources, "json_associations": associations, "passed": len(findings) == route_findings_before})
    return {"check": "consumer-resource-closure", "manifest": manifest_path.as_posix(), "routes": route_results, "findings": findings, "status": "passed" if not findings else "failed", "claim_boundary": "Pass proves only the selected staged consumer resources and declared local links are closed; it does not prove route semantics or writing quality."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--route", choices=ROUTES)
    parser.add_argument("--depth", choices=("compact", "short", "longform"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = check_consumer_resource_closure(args.root, manifest_path=args.manifest, route=args.route, depth=args.depth)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
