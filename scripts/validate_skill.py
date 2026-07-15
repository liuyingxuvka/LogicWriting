"""Portable static validation for the installable Logic Writing skill."""

from __future__ import annotations

import argparse
import json
import py_compile
import re
import sys
from pathlib import Path


PLACEHOLDERS = re.compile(r"\b(?:TODO|TBD|FIXME|VERIFIED INSTALL COMMAND|FINAL SHA|FINAL TAG)\b", re.IGNORECASE)
LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")


def _frontmatter(text: str):
    if not text.startswith("---\n"):
        return {}, "missing YAML frontmatter"
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, "unterminated YAML frontmatter"
    fields = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields, ""


def validate_skill(root: Path):
    errors: list[str] = []
    warnings: list[str] = []
    root = root.resolve()
    skill_md = root / "SKILL.md"
    if not skill_md.is_file():
        return {"status": "failed", "errors": ["SKILL.md is missing"], "warnings": []}
    text = skill_md.read_text(encoding="utf-8")
    fields, frontmatter_error = _frontmatter(text)
    if frontmatter_error:
        errors.append(frontmatter_error)
    if fields.get("name") != "logic-writing":
        errors.append("frontmatter name must be logic-writing")
    description = fields.get("description", "")
    if len(description) < 80 or "academic" not in description.lower() or "investigation" not in description.lower():
        errors.append("frontmatter description must explain both activation routes")
    if len(text.splitlines()) > 500:
        errors.append("SKILL.md exceeds 500 lines")
    if PLACEHOLDERS.search(text):
        errors.append("SKILL.md contains a placeholder")
    if (root / "README.md").exists() or (root / "CHANGELOG.md").exists():
        errors.append("repository docs must not be copied into the installed skill")

    for target in LINK.findall(text):
        if "://" in target or target.startswith("#"):
            continue
        clean = target.split("#", 1)[0]
        resolved = (root / clean).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            errors.append(f"reference escapes skill root: {target}")
            continue
        if not resolved.exists():
            errors.append(f"missing referenced resource: {target}")

    yaml_path = root / "agents" / "openai.yaml"
    if not yaml_path.is_file():
        errors.append("agents/openai.yaml is missing")
    else:
        yaml_text = yaml_path.read_text(encoding="utf-8")
        for required in ('display_name: "Logic Writing"', "short_description:", "$logic-writing"):
            if required not in yaml_text:
                errors.append(f"agents/openai.yaml missing {required}")
        if PLACEHOLDERS.search(yaml_text):
            errors.append("agents/openai.yaml contains a placeholder")

    compiled = 0
    for script in sorted((root / "scripts").glob("*.py")):
        try:
            py_compile.compile(str(script), doraise=True)
            compiled += 1
        except py_compile.PyCompileError as exc:
            errors.append(f"{script.name}: {exc.msg}")
    if compiled < 10:
        warnings.append("unexpectedly small script inventory")

    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".yaml", ".yml", ".json", ".py"}:
            content = path.read_text(encoding="utf-8")
            if PLACEHOLDERS.search(content):
                errors.append(f"placeholder in {path.relative_to(root)}")
    return {
        "status": "passed" if not errors else "failed",
        "skill_root": str(root),
        "script_count": compiled,
        "reference_count": len(tuple((root / "references").rglob("*.md"))),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = validate_skill(args.skill_root)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else f"skill static validation: {report['status']}\n" + "\n".join(report["errors"]))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
