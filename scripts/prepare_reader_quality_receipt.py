"""Prepare one complete current v2 reader chain for independent judgment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def prepare(root: Path, receipt_root: Path, output: Path) -> dict:
    root = root.resolve()
    output = output.resolve()
    scripts = root / "skills" / "logic-writing" / "scripts"
    for path in (root, scripts):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from tests.v2_support import complete_chain

    work = output.parent / "representative-artifact"
    work.mkdir(parents=True, exist_ok=True)
    chain = complete_chain(work, "investigation")
    envelope = {
        "judgment": chain["judgment"],
        "artifact_map": chain["artifact_map"],
        "reader_brief": chain["reader_brief"],
        "shared_writing": chain["shared_writing"],
        "deterministic_audit": chain["deterministic_audit"],
        "route_review": chain["route_review"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "status": "passed",
        "artifact": str(chain["artifact_path"].relative_to(output.parent)),
        "judgment_request": output.name,
        "deterministic_status": "current_pass",
        "claim_boundary": "Preparation freezes one representative current v2 artifact chain; judgment remains a separate validation step.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--receipt-root", type=Path, default=Path("run-artifacts/reader-receipts"))
    parser.add_argument("--output", type=Path, default=Path("run-artifacts/reader-quality-judgment.json"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = prepare(args.root, args.receipt_root, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {"status": "failed", "error": str(exc)}
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) if args.json else f"reader-quality preparation: {report['status']}")
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
