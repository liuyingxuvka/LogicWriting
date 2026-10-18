"""Check source or hosted release identity without conflating the two."""

from __future__ import annotations

import argparse
import json
import os
import re
from urllib.request import Request, urlopen
from pathlib import Path

from _release_common import emit, git_lines


VERSION = "4.0.8"
REPOSITORY = "liuyingxuvka/LogicWriting"


def _source_checks(root: Path, *, require_clean: bool, require_head: bool) -> list[str]:
    findings: list[str] = []
    version_path = root / "VERSION"
    if not version_path.is_file() or version_path.read_text(encoding="utf-8").strip() != VERSION:
        findings.append("version_file_mismatch")
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8") if (root / "pyproject.toml").is_file() else ""
    if not re.search(
        rf'^version\s*=\s*"{re.escape(VERSION)}"\s*$', pyproject, re.MULTILINE
    ):
        findings.append("pyproject_version_mismatch")
    for name in ("README.md", "README.zh-CN.md"):
        text = (root / name).read_text(encoding="utf-8") if (root / name).is_file() else ""
        if f"source-{VERSION}" not in text or "logic--writing" not in text:
            findings.append(f"readme_identity_mismatch:{name}")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8") if (root / "CHANGELOG.md").is_file() else ""
    if f"## [{VERSION}]" not in changelog:
        findings.append("changelog_version_missing")
    tracked = git_lines(root, "ls-files")
    for path in tracked:
        lowered = path.lower()
        if lowered.endswith((".bundle", ".patch")) or lowered.startswith(("backups/", "private/", "run-artifacts/")):
            findings.append(f"non_source_file_tracked:{path}")
    if require_head and not git_lines(root, "rev-parse", "--verify", "HEAD"):
        findings.append("git_head_missing")
    if require_clean:
        status = git_lines(root, "status", "--porcelain")
        if status:
            findings.append("git_worktree_not_clean")
    branch = git_lines(root, "branch", "--show-current")
    if require_head and branch != ["main"]:
        findings.append("default_source_branch_not_main")
    return findings


def _github_json(repository: str, path: str = "") -> dict:
    """Read the same public GitHub authority directly; no local CLI/login needed."""
    request = Request(f"https://api.github.com/repos/{repository}" + (f"/{path}" if path else ""),
                      headers={"Accept": "application/vnd.github+json", "User-Agent": "LogicWriting-release-check"})
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urlopen(request, timeout=30) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError("GitHub response must be an object")
    return value


def _published_checks(root: Path, repository: str) -> tuple[list[str], dict]:
    findings: list[str] = []
    evidence: dict = {}
    head = git_lines(root, "rev-parse", "HEAD")
    tag = git_lines(root, "rev-list", "-n", "1", f"v{VERSION}")
    if not head or tag != head:
        findings.append("release_tag_does_not_point_to_head")
    remote = git_lines(root, "remote", "get-url", "origin")
    if not remote or repository.lower() not in remote[0].lower():
        findings.append("origin_repository_mismatch")
    try:
        repo = _github_json(repository)
        evidence["repository"] = {"nameWithOwner": repo.get("full_name"), "visibility": "PRIVATE" if repo.get("private") else "PUBLIC",
                                  "defaultBranchRef": {"name": repo.get("default_branch")}, "url": repo.get("html_url")}
        if repo.get("full_name") != repository:
            findings.append("github_repository_identity_mismatch")
        if repo.get("private") is not False:
            findings.append("github_repository_not_public")
        if repo.get("default_branch") != "main":
            findings.append("github_default_branch_not_main")
        main = _github_json(repository, "git/ref/heads/main")["object"]["sha"]
        if not head or main != head[0]:
            findings.append("github_main_does_not_match_head")
        obj = _github_json(repository, f"git/ref/tags/v{VERSION}")["object"]
        for _ in range(8):
            if obj.get("type") == "commit":
                break
            if obj.get("type") != "tag":
                raise ValueError("GitHub release tag has an unsupported object type")
            obj = _github_json(repository, f"git/tags/{obj['sha']}")["object"]
        if obj.get("type") != "commit" or not head or obj.get("sha") != head[0]:
            findings.append("github_release_tag_does_not_match_head")
        evidence["release_commit"] = obj.get("sha")
        release = _github_json(repository, f"releases/tags/v{VERSION}")
        evidence["release"] = {"tagName": release.get("tag_name"), "isDraft": release.get("draft"),
                               "isPrerelease": release.get("prerelease"), "url": release.get("html_url"),
                               "targetCommitish": release.get("target_commitish")}
        if release.get("tag_name") != f"v{VERSION}" or release.get("draft") is not False or release.get("prerelease") is not False:
            findings.append("github_release_identity_mismatch")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        findings.append("github_published_evidence_unavailable")
        evidence["error"] = f"{type(exc).__name__}: {exc}"
    return findings, evidence


def check(root: Path, *, mode: str, repository: str, require_clean: bool, require_head: bool) -> dict:
    root = root.resolve()
    findings = _source_checks(root, require_clean=require_clean, require_head=require_head)
    evidence: dict = {}
    if mode == "published":
        remote_findings, evidence = _published_checks(root, repository)
        findings.extend(remote_findings)
    return {
        "check": "release-surface",
        "mode": mode,
        "status": "passed" if not findings else "failed",
        "version": VERSION,
        "repository": repository,
        "evidence": evidence,
        "findings": sorted(set(findings)),
        "claim_boundary": "Source mode proves local version and public-tree consistency only. Published mode additionally checks the named GitHub repository, tag, and release.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("source", "published"), default="source")
    parser.add_argument("--repository", default=REPOSITORY)
    parser.add_argument("--require-clean", action="store_true")
    parser.add_argument("--require-head", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return emit(
        check(
            args.root,
            mode=args.mode,
            repository=args.repository,
            require_clean=args.require_clean,
            require_head=args.require_head,
        ),
        as_json=args.json,
    )


if __name__ == "__main__":
    raise SystemExit(main())
