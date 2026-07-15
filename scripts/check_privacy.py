"""Fail when public source files expose private material or machine paths."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from _release_common import RELEASE_CONTRACT_RELATIVE, git_lines


TEXT_SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".toml", ".txt"}
EXCLUDED_PARTS = {".git", "__pycache__", ".pytest_cache", "run-artifacts", "run_artifacts", "evidence"}
PATTERNS = {
    "windows_home": re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+", re.IGNORECASE),
    "unix_home": re.compile(r"/(?:Users|home)/[^/\s]+/"),
    "openai_key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "github_token": re.compile(r"gh[opusr]_[A-Za-z0-9]{20,}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}

# Private case labels are represented only by normalized n-gram digests.  This
# lets the public scanner reject an accidental reintroduction without making
# the scanner itself a new disclosure surface.
SENSITIVE_NGRAM_HASHES = {
    3: {
        "92b28a8dc7f26329a5acecd766a298388b04819aabe18c4837a030f27f3e33e2",
    }
}
WORD_TOKEN = re.compile(r"[A-Za-z0-9]+")


def _fallback_source_paths(root: Path) -> list[Path]:
    paths = [path for path in root.rglob("*") if path.is_file()]
    contract_path = root / RELEASE_CONTRACT_RELATIVE
    if not contract_path.is_file():
        return paths
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8")) or {}
    patterns = tuple(
        str(item).replace("\\", "/")
        for item in (contract.get("freshness") or {}).get("exclude", [])
    )
    return [
        path
        for path in paths
        if not any(
            fnmatch.fnmatchcase(path.relative_to(root).as_posix(), pattern)
            for pattern in patterns
        )
    ]


def _contains_sensitive_ngram(text: str) -> bool:
    tokens = [item.casefold() for item in WORD_TOKEN.findall(text)]
    for size, denied_digests in SENSITIVE_NGRAM_HASHES.items():
        for start in range(0, max(0, len(tokens) - size + 1)):
            normalized = " ".join(tokens[start : start + size])
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            if digest in denied_digests:
                return True
    return False


def scan(root: Path):
    findings = []
    root = root.resolve()
    admitted = git_lines(root, "ls-files", "--cached", "--others", "--exclude-standard")
    paths = (
        [root / Path(*item.replace("\\", "/").split("/")) for item in admitted]
        if admitted
        else _fallback_source_paths(root)
    )
    for path in paths:
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern_id, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append({"path": str(relative).replace("\\", "/"), "pattern": pattern_id})
        if _contains_sensitive_ngram(text):
            findings.append(
                {
                    "path": str(relative).replace("\\", "/"),
                    "pattern": "private_case_marker",
                }
            )
    return {"status": "passed" if not findings else "failed", "findings": findings, "scanned_root": "."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = scan(args.root.resolve())
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else f"privacy check: {report['status']}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
