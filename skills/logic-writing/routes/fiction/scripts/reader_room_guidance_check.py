#!/usr/bin/env python3
"""Check reader-room and variation guidance without scanning prose as banned text."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DOC_PATHS = [
    "skills/logic-writing/references/routes/fiction-writing.md",
    "skills/logic-writing/routes/fiction/references/workflow.md",
    "skills/logic-writing/routes/fiction/references/longform-lifecycle.md",
    "skills/logic-writing/routes/fiction/references/prose-native-contract.md",
    "skills/logic-writing/routes/fiction/references/chapter-interface-prose-blueprint.md",
    "skills/logic-writing/routes/fiction/references/story-contribution-contract.md",
    "skills/logic-writing/routes/fiction/references/scene-contract.md",
    "skills/logic-writing/routes/fiction/references/voice-style-continuity.md",
    "skills/logic-writing/routes/fiction/references/longform-closure.md",
    "skills/logic-writing/routes/fiction/references/closure-report.md",
]

REQUIRED_TERMS = [
    "reader-native manuscript review",
    "reader-room contamination",
    "story-world chapter ending",
    "explanation pressure",
    "variation pressure",
    "post-draft contribution review",
    "character voice distinction",
    "model-prose binding",
    "reader-state simulation",
    "resistance/friction",
    "register ownership",
]

FORBIDDEN_MANUSCRIPT_TERMS = [
    "潮窗",
    "陈乔",
    "唐世逸",
    "徐以亭",
    "任明轩",
]

EXAMPLE_PATHS = [
    "skills/logic-writing/routes/fiction/examples/reader_room_failure_cases/reader_room_planning_leak.md",
    "skills/logic-writing/routes/fiction/examples/reader_room_failure_cases/author_forecast_chapter_ending.md",
    "skills/logic-writing/routes/fiction/examples/reader_room_failure_cases/duplicate_chapter_contribution.md",
    "skills/logic-writing/routes/fiction/examples/reader_room_failure_cases/premature_reveal_without_support.md",
    "skills/logic-writing/routes/fiction/examples/reader_room_failure_cases/late_payoff_without_prior_support.md",
    "skills/logic-writing/routes/fiction/examples/reader_room_failure_cases/exposition_pressure_over_scene.md",
    "skills/logic-writing/routes/fiction/examples/reader_room_failure_cases/same_voice_cast.md",
    "skills/logic-writing/routes/fiction/examples/reader_room_failure_cases/location_changes_without_pressure_change.md",
    "skills/logic-writing/routes/fiction/examples/reader_room_failure_cases/repeated_event_function.md",
    "skills/logic-writing/routes/fiction/examples/reader_room_failure_cases/intentional_repetition_with_escalation.md",
]


def read_docs() -> tuple[str, list[dict[str, str]]]:
    parts: list[str] = []
    issues: list[dict[str, str]] = []
    for raw_path in DOC_PATHS:
        path = Path(raw_path)
        if not path.exists():
            issues.append({"code": "missing_doc", "path": raw_path})
            continue
        parts.append(path.read_text(encoding="utf-8").lower())
    return "\n".join(parts), issues


def check_terms() -> list[dict[str, str]]:
    text, issues = read_docs()
    for term in REQUIRED_TERMS:
        if term.lower() not in text:
            issues.append({"code": "missing_term", "path": "docs", "term": term})
    return issues


def check_genre_neutral() -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for raw_path in DOC_PATHS:
        path = Path(raw_path)
        if not path.exists():
            issues.append({"code": "missing_doc", "path": raw_path})
            continue
        text = path.read_text(encoding="utf-8")
        for term in FORBIDDEN_MANUSCRIPT_TERMS:
            if term in text:
                issues.append(
                    {"code": "manuscript_specific_term", "path": raw_path, "term": term}
                )
    return issues


def check_examples() -> list[dict[str, str]]:
    return [
        {"code": "missing_example", "path": raw_path}
        for raw_path in EXAMPLE_PATHS
        if not Path(raw_path).exists()
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        choices=["all", "terms", "genre", "examples"],
        default="all",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    issues: list[dict[str, str]] = []
    if args.check in {"all", "terms"}:
        issues.extend(check_terms())
    if args.check in {"all", "genre"}:
        issues.extend(check_genre_neutral())
    if args.check in {"all", "examples"}:
        issues.extend(check_examples())

    report = {
        "schema_version": "storyline-design.reader_room_guidance_check.report.v1",
        "check": args.check,
        "passed": not issues,
        "issue_count": len(issues),
        "issues": issues,
    }
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(f"Reader-room guidance check: {'passed' if report['passed'] else 'failed'}")
        for issue in issues:
            detail = issue.get("term") or issue.get("path") or issue["code"]
            print(f"- {issue['code']}: {detail}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
