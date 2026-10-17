"""Compare canonical Logic Writing skill files with the installed directory."""
from __future__ import annotations
import argparse
import importlib.util
import os
from pathlib import Path
from _release_common import canonical_hash, emit


def check(source_skill: Path, codex_home: Path) -> dict:
    source = source_skill.resolve()
    helper = source / "routes/fiction/scripts/installed_parity_check.py"
    findings = []
    report = {}
    try:
        spec = importlib.util.spec_from_file_location("logic_writing_directory_parity", helper)
        if spec is None or spec.loader is None:
            raise ValueError("parity_helper_missing")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        report = module.build_report(source, codex_home.resolve() / "skills/logic-writing")
        for kind in ("missing", "extra", "changed"):
            findings.extend(f"{kind}:{path}" for path in report.get(kind, []))
        if report.get("error"):
            findings.append(report["error"])
    except (OSError, ValueError, ImportError) as exc:
        findings.append(str(exc))
    return {
        "check": "installation-parity", "status": "passed" if report.get("passed") and not findings else "failed",
        "skill_id": "logic-writing", "member_count": report.get("source_count", 0),
        "projection_hash": canonical_hash(report.get("source_sha256", {})), "findings": sorted(set(findings)),
        "claim_boundary": "Exact canonical skill directory inventory and byte parity; no domain task is executed.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-skill", required=True, type=Path)
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return emit(check(args.source_skill, args.codex_home), as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
