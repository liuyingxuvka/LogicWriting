"""Install the Logic Writing skill into an agent's skills directory.

    python scripts/install_skill.py --target ~/.claude/skills            # or "$CODEX_HOME/skills"
    python scripts/install_skill.py --target ~/.claude/skills --dry-run
    python scripts/install_skill.py --target ~/.claude/skills --check    # exit 1 if the copy differs

Copies skills/logic-writing/ to <target>/logic-writing/ (replacing an older copy) and
leaves out the fixtures and regression runners that only this repository's tests use.
ResearchGuard and WorldGuard are installed separately.
"""

from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "skills" / "logic-writing"
REPOSITORY_ONLY = (
    "routes/fiction/examples",
    "routes/travel/examples",
    "routes/fiction/scripts/run_longform_regression.py",
    "routes/fiction/scripts/run_native_regression.py",
    "routes/fiction/scripts/run_route_regression.py",
    "routes/fiction/scripts/run_story_model_mesh_regression.py",
    "routes/travel/scripts/validate_failure_cases.py",
    "routes/travel/scripts/validate_positive_cases.py",
)


def skill_files(root: Path, *, installed: bool) -> set[str]:
    files = set()
    for path in root.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(root).as_posix()
        if not installed and any(rel == item or rel.startswith(item + "/") for item in REPOSITORY_ONLY):
            continue
        files.add(rel)
    return files


def differences(src: Path, dst: Path) -> list[str]:
    if not dst.is_dir():
        return [f"missing {dst}"]
    wanted = skill_files(src, installed=False)
    present = skill_files(dst, installed=True)
    out = [f"only in source: {rel}" for rel in sorted(wanted - present)]
    out += [f"only in target: {rel}" for rel in sorted(present - wanted)]
    out += [f"differs: {rel}" for rel in sorted(wanted & present) if not filecmp.cmp(src / rel, dst / rel, shallow=False)]
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, help="skills directory, e.g. ~/.claude/skills")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = os.path.expandvars(args.target)
    if "$" in target:
        parser.error(f"target contains an unset environment variable: {args.target}")
    dst = Path(target).expanduser() / "logic-writing"
    if not (SOURCE / "SKILL.md").is_file():
        print(f"skill source not found: {SOURCE}", file=sys.stderr)
        return 2
    diff = differences(SOURCE, dst)
    if args.check:
        print("\n".join(diff) or "installed skill is current")
        return 1 if diff else 0
    if args.dry_run:
        print(f"would copy {SOURCE} -> {dst}" + (f" ({len(diff)} difference(s))" if diff else " (already current)"))
        return 0
    if dst.exists():
        shutil.rmtree(dst)
    files = sorted(skill_files(SOURCE, installed=False))
    for rel in files:
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE / rel, dst / rel)
    print(f"installed {dst} ({len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
