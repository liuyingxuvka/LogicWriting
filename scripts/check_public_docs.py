"""Check the bilingual, reader-facing public documentation contract."""

from __future__ import annotations

import argparse
import fnmatch
import re
from pathlib import Path

import yaml

from _release_common import RELEASE_CONTRACT_RELATIVE, emit, git_lines


LINK = re.compile(r"!?\[[^]]*\]\(([^)]+)\)")
PLACEHOLDER = re.compile(r"\b(?:TODO|TBD|FIXME|FINAL SHA|FINAL TAG)\b", re.IGNORECASE)
REQUIRED_PUBLIC_FILES = {
    "README.md",
    "README.zh-CN.md",
    "MIGRATION.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "VERSION",
    "docs/architecture.md",
    "docs/responsibility-map.md",
    "assets/readme-hero/hero.png",
    "assets/readme-hero/hero_design_note.md",
    "assets/readme-hero/hero_prompt.md",
}
PROHIBITED_PUBLIC_DOCS = {
    "SLIM_LOG.md",
    "XR_LOG.md",
    "docs/coordination.md",
    "docs/flowguard_adoption_log.md",
    "docs/flowguard_behavior_commitment_ledger.md",
    "docs/flowguard_development_process_flow.md",
    "docs/flowguard_development_process_strategy_selection.md",
    "docs/flowguard_plan_detailing.md",
    "docs/flowguard_primary_path_authority.md",
}


def _public_inventory(root: Path) -> set[str]:
    admitted = git_lines(root, "ls-files", "--cached", "--others", "--exclude-standard")
    if admitted:
        return {item.replace("\\", "/") for item in admitted}
    inventory = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }
    contract_path = root / RELEASE_CONTRACT_RELATIVE
    if not contract_path.is_file():
        return inventory
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8")) or {}
    patterns = tuple(
        str(item).replace("\\", "/")
        for item in (contract.get("freshness") or {}).get("exclude", [])
    )
    return {
        relative
        for relative in inventory
        if not any(fnmatch.fnmatchcase(relative, pattern) for pattern in patterns)
    }


def check(root: Path) -> dict:
    root = root.resolve()
    findings: list[str] = []
    inventory = _public_inventory(root)
    missing = sorted(path for path in REQUIRED_PUBLIC_FILES if not (root / path).is_file())
    findings.extend(f"missing_public_file:{path}" for path in missing)
    findings.extend(
        f"internal_record_is_public:{path}" for path in sorted(PROHIBITED_PUBLIC_DOCS & inventory)
    )
    if missing:
        return {"check": "public-docs", "status": "failed", "findings": findings}

    for label, relative in (("english", "README.md"), ("chinese", "README.zh-CN.md")):
        text = (root / relative).read_text(encoding="utf-8")
        if PLACEHOLDER.search(text):
            findings.append(f"{label}_placeholder")

    for relative in ("README.md", "README.zh-CN.md", "MIGRATION.md", "CONTRIBUTING.md"):
        text = (root / relative).read_text(encoding="utf-8")
        for target in LINK.findall(text):
            clean = target.strip().strip("<>").split("#", 1)[0]
            if not clean or "://" in clean or clean.startswith("mailto:"):
                continue
            if not (root / clean).exists():
                findings.append(f"broken_local_link:{relative}:{clean}")

    return {
        "check": "public-docs",
        "status": "passed" if not findings else "failed",
        "public_file_count": len(inventory),
        "findings": sorted(set(findings)),
        "claim_boundary": "This check covers required public files, placeholders, local links, and public-file admission; it does not prove hosted rendering or publication.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return emit(check(args.root), as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
