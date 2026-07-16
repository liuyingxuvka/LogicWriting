#!/usr/bin/env python3
"""Exercise content-exact installation parity and frozen projection behavior."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from installed_parity_check import build_report, load_projection


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="storyline-parity-") as temp:
        root = Path(temp)
        source = root / "source"
        target = root / "target"
        write(source / "SKILL.md", "current\n")
        write(source / "scripts" / "check.py", "print('current')\n")
        write(target / "SKILL.md", "current\n")
        write(target / "scripts" / "check.py", "print('current')\n")
        if not build_report(source, target)["passed"]:
            failures.append("equal content did not pass")

        write(target / "SKILL.md", "stale\n")
        changed = build_report(source, target)
        if changed["passed"] or changed["changed"] != ["SKILL.md"]:
            failures.append("same filename with changed bytes was not isolated")
        write(target / "SKILL.md", "current\n")

        (target / "scripts" / "check.py").unlink()
        missing = build_report(source, target)
        if missing["passed"] or missing["missing"] != ["scripts/check.py"]:
            failures.append("missing projected file was not rejected")
        write(target / "scripts" / "check.py", "print('current')\n")

        write(target / "runtime-report.json", "{}\n")
        extra = build_report(source, target)
        if extra["passed"] or extra["extra"] != ["runtime-report.json"]:
            failures.append("undeclared extra file was not rejected without a projection")

        projection_path = root / "projection.json"
        projection_path.write_text(json.dumps({"files": ["SKILL.md", "scripts/check.py"]}), encoding="utf-8")
        projection = load_projection(projection_path)
        projected = build_report(source, target, projection)
        if not projected["passed"]:
            failures.append("repository-only output incorrectly staled frozen projection")

        invalid_projection = root / "invalid-projection.json"
        invalid_projection.write_text(json.dumps({"files": ["../escape"]}), encoding="utf-8")
        try:
            load_projection(invalid_projection)
        except ValueError:
            pass
        else:
            failures.append("escaping projection path was accepted")

    report = {
        "schema_version": "storyline-design.installed_parity_regression.report.v1",
        "passed": not failures,
        "cases": 6,
        "failures": failures,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
