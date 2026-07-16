#!/usr/bin/env python3
"""Check that long-form final closure guidance names the required evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


DEFAULT_PATHS = [
    "skills/logic-writing/references/routes/fiction-writing.md",
    "skills/logic-writing/routes/fiction/references/longform-lifecycle.md",
    "skills/logic-writing/routes/fiction/references/longform-closure.md",
    "skills/logic-writing/routes/fiction/references/novel-ledger.md",
]
DEFAULT_TERMS = [
    "final artifact",
    "source requirements",
    "artifact-bound",
    "stale",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate final prose closure guidance text."
    )
    parser.add_argument("paths", nargs="*", default=DEFAULT_PATHS)
    parser.add_argument(
        "--term",
        action="append",
        dest="terms",
        default=None,
        help="Required lowercase text fragment. Can be repeated.",
    )
    args = parser.parse_args(argv)

    text_parts: list[str] = []
    missing_paths: list[str] = []
    for raw_path in args.paths:
        path = Path(raw_path)
        if not path.exists():
            missing_paths.append(raw_path)
            continue
        text_parts.append(path.read_text(encoding="utf-8").lower())

    text = "\n".join(text_parts)
    required_terms = args.terms or DEFAULT_TERMS
    missing_terms = [term for term in required_terms if term.lower() not in text]

    if missing_paths or missing_terms:
        if missing_paths:
            print("Missing files:", ", ".join(missing_paths))
        if missing_terms:
            print("Missing terms:", ", ".join(missing_terms))
        return 1

    print("Final closure guidance text check: passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
