#!/usr/bin/env python3
"""Verify repository-contained, content-addressed evidence references."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


CONTENT_REFERENCE_RE = re.compile(r"^file:(?P<path>[^;\r\n]+);sha256:(?P<sha256>[0-9a-fA-F]{64})$")
SHA256_VALUE_RE = re.compile(r"^sha256:(?P<sha256>[0-9a-fA-F]{64})$")


class EvidenceIdentityError(ValueError):
    """A stable, machine-readable evidence identity failure."""

    def __init__(self, code: str, path: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
        self.message = message

    def as_issue(self) -> dict[str, str]:
        return {"severity": "error", "code": self.code, "path": self.path, "message": self.message}


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def repository_root_for(source_path: str | Path, repository_root: str | Path | None = None) -> Path:
    """Resolve the one repository root used as the evidence containment boundary."""

    if repository_root is not None:
        root = Path(repository_root).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise EvidenceIdentityError("invalid_repository_root", "repository_root", f"Repository root is not a directory: {root}")
        return root

    source = Path(source_path).expanduser().resolve(strict=False)
    start = source if source.is_dir() else source.parent
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate.resolve(strict=True)
    raise EvidenceIdentityError(
        "repository_root_not_found",
        "repository_root",
        "Cannot establish repository-root containment; pass an explicit repository root.",
    )


def parse_content_reference(reference: Any) -> tuple[str, str]:
    if not isinstance(reference, str):
        raise EvidenceIdentityError(
            "invalid_content_reference",
            "evidence_ref",
            "Evidence reference must be a string in file:<path>;sha256:<64 hex> form.",
        )
    match = CONTENT_REFERENCE_RE.fullmatch(reference.strip())
    if match is None:
        raise EvidenceIdentityError(
            "invalid_content_reference",
            "evidence_ref",
            "Evidence reference must exactly match file:<path>;sha256:<64 hex>.",
        )
    return match.group("path"), match.group("sha256").lower()


def parse_sha256_value(value: Any, *, path: str = "artifact_sha256") -> str:
    if not isinstance(value, str):
        raise EvidenceIdentityError("invalid_sha256_value", path, "SHA-256 value must be sha256:<64 hex>.")
    match = SHA256_VALUE_RE.fullmatch(value.strip())
    if match is None:
        raise EvidenceIdentityError("invalid_sha256_value", path, "SHA-256 value must exactly match sha256:<64 hex>.")
    return match.group("sha256").lower()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise EvidenceIdentityError("content_read_error", "evidence_ref", f"Cannot read evidence file {path}: {exc}") from exc
    return digest.hexdigest()


def verify_content_reference(
    reference: Any,
    source_path: str | Path,
    repository_root: str | Path | None = None,
) -> dict[str, str]:
    """Open an evidence file, enforce containment, and verify its declared digest."""

    declared_path, declared_sha256 = parse_content_reference(reference)
    root = repository_root_for(source_path, repository_root)
    source = Path(source_path).expanduser().resolve(strict=False)
    base = source if source.is_dir() else source.parent
    raw_path = Path(declared_path).expanduser()
    candidate = raw_path if raw_path.is_absolute() else base / raw_path
    unresolved = candidate.resolve(strict=False)
    if not _is_within(unresolved, root):
        raise EvidenceIdentityError(
            "content_reference_outside_root",
            "evidence_ref",
            f"Evidence path escapes repository root: {declared_path}",
        )
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise EvidenceIdentityError(
            "content_file_missing",
            "evidence_ref",
            f"Referenced evidence file does not exist: {declared_path}",
        ) from exc
    except OSError as exc:
        raise EvidenceIdentityError(
            "content_read_error",
            "evidence_ref",
            f"Cannot resolve evidence file {declared_path}: {exc}",
        ) from exc
    if not _is_within(resolved, root):
        raise EvidenceIdentityError(
            "content_reference_outside_root",
            "evidence_ref",
            f"Resolved evidence path escapes repository root: {declared_path}",
        )
    if not resolved.is_file():
        raise EvidenceIdentityError(
            "content_file_not_regular",
            "evidence_ref",
            f"Referenced evidence path is not a regular file: {declared_path}",
        )
    actual_sha256 = sha256_file(resolved)
    if actual_sha256 != declared_sha256:
        raise EvidenceIdentityError(
            "content_hash_mismatch",
            "evidence_ref",
            f"Declared SHA-256 does not match current bytes for {declared_path}.",
        )
    return {
        "reference": str(reference).strip(),
        "repository_path": resolved.relative_to(root).as_posix(),
        "sha256": actual_sha256,
    }


def require_matching_sha256(value: Any, actual_sha256: str, *, path: str = "artifact_sha256") -> str:
    declared = parse_sha256_value(value, path=path)
    if declared != actual_sha256:
        raise EvidenceIdentityError(
            "artifact_sha256_mismatch",
            path,
            "Declared artifact_sha256 does not match the recomputed manuscript identity.",
        )
    return declared
