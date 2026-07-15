"""Check source or hosted release identity without conflating the two."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from _release_common import emit, git_lines, run


VERSION = "1.0.2"
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
    view = run(
        ["gh", "repo", "view", repository, "--json", "nameWithOwner,visibility,defaultBranchRef,url"],
        cwd=root,
        timeout=120,
    )
    if view.returncode != 0:
        findings.append("github_repository_unavailable")
    else:
        try:
            repo_data = json.loads(view.stdout)
            evidence["repository"] = repo_data
            if repo_data.get("nameWithOwner") != repository:
                findings.append("github_repository_identity_mismatch")
            if repo_data.get("visibility") != "PUBLIC":
                findings.append("github_repository_not_public")
            if (repo_data.get("defaultBranchRef") or {}).get("name") != "main":
                findings.append("github_default_branch_not_main")
        except json.JSONDecodeError:
            findings.append("github_repository_response_invalid")
    release = run(
        ["gh", "release", "view", f"v{VERSION}", "--repo", repository, "--json", "tagName,isDraft,isPrerelease,url,targetCommitish"],
        cwd=root,
        timeout=120,
    )
    if release.returncode != 0:
        findings.append("github_release_unavailable")
    else:
        try:
            release_data = json.loads(release.stdout)
            evidence["release"] = release_data
            if release_data.get("tagName") != f"v{VERSION}" or release_data.get("isDraft") or release_data.get("isPrerelease"):
                findings.append("github_release_identity_mismatch")
        except json.JSONDecodeError:
            findings.append("github_release_response_invalid")
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
