#!/usr/bin/env python3
"""Compare the frozen StorylineDesign installation projection by content."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


IGNORED_PREFIXES: tuple[str, ...] = ()
IGNORED_PARTS = {"__pycache__"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root: Path) -> dict[str, str]:
    items: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(root)
        if any(part in IGNORED_PARTS for part in relative_path.parts):
            continue
        relative = str(relative_path).replace("\\", "/")
        if any(relative.startswith(prefix) for prefix in IGNORED_PREFIXES):
            continue
        items[relative] = sha256(path)
    return dict(sorted(items.items()))


def load_projection(path: Path | None) -> list[str] | None:
    if path is None:
        return None
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, list) or not files or not all(isinstance(item, str) and item for item in files):
        raise ValueError("Projection must contain a non-empty string list at 'files'.")
    normalized = [item.replace("\\", "/") for item in files]
    if len(normalized) != len(set(normalized)):
        raise ValueError("Projection contains duplicate relative paths.")
    if any(item.startswith("/") or ".." in Path(item).parts for item in normalized):
        raise ValueError("Projection paths must be contained relative paths.")
    return sorted(normalized)


def select_projection(items: dict[str, str], projection: list[str] | None) -> dict[str, str]:
    if projection is None:
        return items
    return {relative: items[relative] for relative in projection if relative in items}


def build_report(source: Path, target: Path, projection: list[str] | None = None) -> dict[str, Any]:
    if not source.exists():
        return {
            "schema_version": "storyline-design.installed_parity_check.report.v2",
            "passed": False,
            "source": str(source),
            "target": str(target),
            "missing": [],
            "extra": [],
            "changed": [],
            "error": "source_missing",
        }
    if not target.exists():
        return {
            "schema_version": "storyline-design.installed_parity_check.report.v2",
            "passed": False,
            "source": str(source),
            "target": str(target),
            "missing": list(select_projection(inventory(source), projection)),
            "extra": [],
            "changed": [],
            "error": "target_missing",
        }
    left_all = inventory(source)
    right_all = inventory(target)
    if projection is not None:
        undeclared = sorted(set(projection) - set(left_all))
        if undeclared:
            return {
                "schema_version": "storyline-design.installed_parity_check.report.v2",
                "passed": False,
                "source": str(source),
                "target": str(target),
                "missing": undeclared,
                "extra": [],
                "changed": [],
                "error": "projection_source_missing",
            }
    left = select_projection(left_all, projection)
    right = select_projection(right_all, projection)
    missing = sorted(set(left) - set(right))
    extra = sorted(set(right) - set(left)) if projection is None else []
    changed = sorted(relative for relative in set(left) & set(right) if left[relative] != right[relative])
    return {
        "schema_version": "storyline-design.installed_parity_check.report.v2",
        "passed": bool(left) and not missing and not extra and not changed,
        "source": str(source),
        "target": str(target),
        "source_count": len(left),
        "target_count": len(right),
        "missing": missing,
        "extra": extra,
        "changed": changed,
        "source_sha256": left,
        "target_sha256": {relative: right[relative] for relative in left if relative in right},
        "ignored_prefixes": list(IGNORED_PREFIXES),
        "ignored_parts": sorted(IGNORED_PARTS),
        "error": "",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check installed skill inventory parity.")
    parser.add_argument("source")
    parser.add_argument("target")
    parser.add_argument("--projection", help="Frozen projection JSON containing a 'files' list.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        projection = load_projection(Path(args.projection).expanduser() if args.projection else None)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        report = {
            "schema_version": "storyline-design.installed_parity_check.report.v2",
            "passed": False,
            "source": args.source,
            "target": args.target,
            "missing": [],
            "extra": [],
            "changed": [],
            "error": f"projection_error: {exc}",
        }
    else:
        report = build_report(Path(args.source).expanduser(), Path(args.target).expanduser(), projection)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Installed parity check: {'passed' if report['passed'] else 'failed'}")
        print(f"Missing: {len(report['missing'])}")
        print(f"Extra: {len(report['extra'])}")
        print(f"Changed: {len(report['changed'])}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
