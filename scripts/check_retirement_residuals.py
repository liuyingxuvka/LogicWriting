"""Reject active local references to the two retired predecessor skills."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from _release_common import emit


OLD_IDS = ("research-investigation-workflow", "academic-thesis-revision-workflow")
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".toml", ".py", ".txt"}


def _active_files(home: Path):
    prompt = home / "AGENTS.md"
    if prompt.is_file():
        yield prompt, "AGENTS.md"
    router = home / ".skillguard" / "global-router"
    for path in router.glob("*.json") if router.is_dir() else ():
        yield path, f".skillguard/global-router/{path.name}"
    skills = home / "skills"
    if skills.is_dir():
        for path in skills.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            relative = path.relative_to(home).as_posix()
            if any(part in {"__pycache__", ".sg-runtime", "evidence", "runs"} for part in path.relative_to(home).parts):
                continue
            yield path, relative


def check(codex_home: Path) -> dict:
    home = codex_home.resolve()
    findings: list[str] = []
    for old_id in OLD_IDS:
        if (home / "skills" / old_id).exists():
            findings.append(f"retired_skill_directory_exists:{old_id}")
    for path, label in _active_files(home):
        text = path.read_text(encoding="utf-8", errors="replace")
        for old_id in OLD_IDS:
            if old_id in text:
                findings.append(f"active_reference:{label}:{old_id}")
    return {
        "check": "retirement-residuals",
        "status": "passed" if not findings else "failed",
        "findings": sorted(set(findings)),
        "claim_boundary": "This scan covers active local skills, the managed prompt, and global routing records. Historical backups and public migration documentation are deliberately outside its scope.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")),
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return emit(check(args.codex_home), as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
