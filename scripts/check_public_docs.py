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
ENGLISH_SECTIONS = [
    "Why one entrypoint?",
    "One entrypoint, two internal routes",
    "The plain-language quality gate",
    "Specialists keep their own jobs",
    "Good fits and non-fits",
    "Requirements",
    "Install from a source checkout",
    "Use",
    "Evidence and claim boundaries",
    "Repository map",
    "Local validation entrypoints",
    "Migration and retirement",
    "License",
]
CHINESE_SECTIONS = [
    "为什么要统一入口？",
    "一个入口，两条内部路线",
    "“说人话”的三道质量闸门",
    "专业技能继续做自己的专业工作",
    "适合什么，不适合什么",
    "使用条件",
    "从源码副本安装",
    "使用方法",
    "证据与措辞边界",
    "仓库结构",
    "本地验证入口",
    "迁移与退役",
    "许可证",
]
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
    "docs/release-retirement-checklist.md",
    "assets/readme-hero/hero.png",
    "assets/readme-hero/hero_design_note.md",
    "assets/readme-hero/hero_prompt.md",
}
PROHIBITED_PUBLIC_DOCS = {
    "docs/coordination.md",
    "docs/flowguard_adoption_log.md",
    "docs/flowguard_behavior_commitment_ledger.md",
    "docs/flowguard_development_process_flow.md",
    "docs/flowguard_development_process_strategy_selection.md",
    "docs/flowguard_plan_detailing.md",
    "docs/flowguard_primary_path_authority.md",
}


def _headings(text: str) -> list[str]:
    return [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]


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

    english = (root / "README.md").read_text(encoding="utf-8")
    chinese = (root / "README.zh-CN.md").read_text(encoding="utf-8")
    if _headings(english) != ENGLISH_SECTIONS:
        findings.append("english_section_order_mismatch")
    if _headings(chinese) != CHINESE_SECTIONS:
        findings.append("chinese_section_order_mismatch")
    for label, text in (("english", english), ("chinese", chinese)):
        if text.count("<!-- README HERO START -->") != 1 or text.count("<!-- README HERO END -->") != 1:
            findings.append(f"{label}_hero_block_count_mismatch")
        if "assets/readme-hero/hero.png" not in text:
            findings.append(f"{label}_hero_reference_missing")
        if PLACEHOLDER.search(text):
            findings.append(f"{label}_placeholder")
        for required in ("ResearchPacket", "ReaderBrief", "SourceGuard", "LogicGuard", "FlowGuard"):
            if required not in text:
                findings.append(f"{label}_required_concept_missing:{required}")

    for relative in ("README.md", "README.zh-CN.md", "MIGRATION.md", "CONTRIBUTING.md"):
        text = (root / relative).read_text(encoding="utf-8")
        for target in LINK.findall(text):
            clean = target.strip().strip("<>").split("#", 1)[0]
            if not clean or "://" in clean or clean.startswith("mailto:"):
                continue
            if not (root / clean).exists():
                findings.append(f"broken_local_link:{relative}:{clean}")

    hero = root / "assets" / "readme-hero" / "hero.png"
    if hero.stat().st_size < 100_000:
        findings.append("hero_image_is_not_release_quality")
    note = (root / "assets/readme-hero/hero_design_note.md").read_text(encoding="utf-8")
    prompt = (root / "assets/readme-hero/hero_prompt.md").read_text(encoding="utf-8")
    if "determin" not in note.lower() or "exact" not in note.lower():
        findings.append("hero_generation_method_missing")
    if "Logic Writing" not in prompt or "Investigation" not in prompt or "Academic writing" not in prompt:
        findings.append("hero_visual_brief_incomplete")
    return {
        "check": "public-docs",
        "status": "passed" if not findings else "failed",
        "section_pairs": len(ENGLISH_SECTIONS),
        "public_file_count": len(inventory),
        "findings": sorted(set(findings)),
        "claim_boundary": "This check covers local bilingual structure, links, hero provenance, and public-file admission; it does not prove hosted rendering or publication.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return emit(check(args.root), as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
