#!/usr/bin/env python3
"""Check that StorylineDesign universal Guard lifecycle hard gates remain documented."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_TERMS: dict[str, list[str]] = {
    "references/routes/fiction-writing.md": [
        "Every substantive StorylineDesign run uses the same guarded story lifecycle",
        "Artifact size changes evidence depth",
        "FlowGuard process-route evidence",
        "TraceGuard, WorldGuard, LogicGuard, and SourceGuard are passed, partial, blocked, stale, or `not_applicable_with_reason`",
        "novel_ledger",
        "Before claiming final long-form prose closure",
        "return to the earliest failed model surface",
    ],
    "routes/fiction/references/story-artifact-lifecycle.md": [
        "Every story task uses the same Guarded Story Lifecycle",
        "Artifact size changes the amount of evidence",
        "FlowGuard owns stage order",
        "`not_applicable_with_reason`",
        "The final claim strength is limited by the weakest important current surface",
    ],
    "routes/fiction/references/guard-depth-policy.md": [
        "Depth scales with artifact size",
        "It does not remove Guard consideration",
        "Compact",
        "Short Story",
        "Final Manuscript",
    ],
    "routes/fiction/references/story-development-flowgraph.md": [
        "flowguard_process",
        "child Guard handoffs are skipped",
        "old evidence is reused",
        "installed_skill_drift",
        "StorylineDesign closure consumes the flowgraph",
    ],
    "routes/fiction/references/traceguard-storyline-contract.md": [
        "story_world_chronology",
        "protagonist_investigation_order",
        "reader_revelation_order",
        "Do not collapse these tracks into chapter summaries",
        "`not_applicable_with_reason`",
    ],
    "routes/fiction/references/logicguard-theme-contract.md": [
        "theme, ending interpretation",
        "structurally supported",
        "Compact Theme Surface",
        "unsafe overclaim wording",
        "not_applicable_with_reason",
    ],
    "routes/fiction/references/sourceguard-canon-contract.md": [
        "user-provided material",
        "source role",
        "can-support",
        "cannot-support",
        "not_applicable_with_reason",
    ],
    "routes/fiction/references/longform-lifecycle.md": [
        "deep tier of the universal guarded story lifecycle",
        "root index for the layered model mesh",
        "object location and condition",
        "character knowledge",
        "Reverse outlines must be event-and-state evidence",
        "substituted by prose/report text",
    ],
    "routes/fiction/references/novel-ledger.md": [
        "Layer Ownership Map",
        "`continuity` rows",
        "character_state",
        "object",
        "timeline",
        "world_rule",
        "clue_state",
    ],
    "routes/fiction/references/chapter-interface-prose-blueprint.md": [
        "observed_events",
        "observed_reader_state_after",
        "observed_promise_movements",
        "observed_arc_movements",
        "shallow evidence",
    ],
    "routes/fiction/references/longform-closure.md": [
        "flowguard_process",
        "traceguard_storyline",
        "worldguard_story_claims",
        "logicguard_theme_support",
        "sourceguard_canon_support",
        "not_applicable_with_reason",
        "Native validator ownership",
        "local structured",
        "Broad markdown reviews",
        "reverse outline cannot pass as a novel ledger",
        "missing object, character_state, timeline, world_rule, or clue_state rows",
    ],
}


def default_skill_root() -> Path:
    repo_skill = Path.cwd() / "skills" / "logic-writing" / "SKILL.md"
    if repo_skill.exists():
        return repo_skill.parent
    return Path(__file__).resolve().parents[1]


def contains_term(text: str, term: str) -> bool:
    lowered = text.lower()
    lowered_one_line = " ".join(lowered.split())
    term_lowered = term.lower()
    term_one_line = " ".join(term_lowered.split())
    return term_lowered in lowered or term_one_line in lowered_one_line


def build_report(skill_root: Path) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    checked_files = 0
    for relative, terms in REQUIRED_TERMS.items():
        path = skill_root / relative
        if not path.exists():
            issues.append(
                {
                    "severity": "error",
                    "code": "missing_file",
                    "path": relative,
                    "message": "Required documentation surface is missing.",
                }
            )
            continue
        checked_files += 1
        text = path.read_text(encoding="utf-8")
        for term in terms:
            if not contains_term(text, term):
                issues.append(
                    {
                        "severity": "error",
                        "code": "missing_required_term",
                        "path": relative,
                        "message": f"Missing required contract text: {term!r}.",
                    }
                )
    return {
        "schema_version": "storyline-design.doc_contract_check.report.v1",
        "skill_root": str(skill_root),
        "passed": not issues,
        "summary": {
            "checked_file_count": checked_files,
            "required_file_count": len(REQUIRED_TERMS),
            "error_count": len(issues),
            "issue_count": len(issues),
        },
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate StorylineDesign long-form documentation hard gates.")
    parser.add_argument("--skill-root", default="", help="Path to skills/storyline-design. Defaults to source or installed skill root.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    skill_root = Path(args.skill_root) if args.skill_root else default_skill_root()
    report = build_report(skill_root)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Doc contract check: {'passed' if report['passed'] else 'failed'}")
        for issue in report["issues"]:
            print(f"- [{issue['severity']}] {issue['code']} at {issue['path']}: {issue['message']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
