"""Execute or audit the frozen OpenSpec validation plan under one foreground owner."""

from __future__ import annotations

import argparse
import fnmatch
import glob
import hashlib
import importlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from _release_common import RELEASE_CONTRACT_RELATIVE


VERIFIER_VERSION = "logic-writing-frozen-validation.v3"
DEFAULT_CONTRACT = RELEASE_CONTRACT_RELATIVE
DEFAULT_RECEIPTS = Path("run-artifacts/validation-receipts")
IGNORED_PARTS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "evidence",
    "validation-receipts",
    ".skillguard/runs",
}


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(value))
    os.replace(temporary, path)


def _resolve_executable(name: str) -> str:
    value = shutil.which(name)
    if value is None and os.name == "nt":
        value = shutil.which(name + ".cmd") or shutil.which(name + ".exe")
    if value is None:
        raise FileNotFoundError(f"executable_not_found:{name}")
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: str | bytes | None) -> str:
    """Normalize partial subprocess output for a durable terminal receipt."""

    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _load_contract(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("checks"), list):
        raise ValueError("verification_contract_invalid")
    return value


def _inventory_revision(contract: Mapping[str, Any]) -> str:
    payload = {
        "checks": contract["checks"],
        "contract_version": contract.get("contract_version"),
        "change": contract.get("change"),
        "test_mesh": contract.get("test_mesh"),
    }
    compact = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(compact).hexdigest()


def _validate_plan(contract: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    checks = [dict(item) for item in contract["checks"]]
    ids = [str(item.get("id", "")) for item in checks]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("check_ids_missing_or_duplicate")
    index = {str(item["id"]): item for item in checks}
    commands = [item for item in checks if item.get("kind") == "command"]
    execution_ids = [str(item.get("execution_id", "")) for item in commands]
    if not all(execution_ids) or len(execution_ids) != len(set(execution_ids)):
        raise ValueError("command_execution_ids_missing_or_duplicate")
    consumers: dict[str, str] = {}
    for item in checks:
        check_id = str(item["id"])
        if item.get("kind") == "receipt":
            owner = str(item.get("execution_owner", ""))
            if owner not in index or index[owner].get("kind") != "command":
                raise ValueError(f"receipt_consumer_owner_invalid:{check_id}")
            consumers[check_id] = owner
        elif item.get("kind") != "command":
            raise ValueError(f"unsupported_check_kind:{check_id}")
        for dependency in item.get("depends_on_receipts", []):
            if dependency not in index:
                raise ValueError(f"unknown_dependency:{check_id}:{dependency}")

    visiting: set[str] = set()
    visited: set[str] = set()
    ordered: list[dict[str, Any]] = []

    def visit(check_id: str) -> None:
        if check_id in visited:
            return
        if check_id in visiting:
            raise ValueError(f"dependency_cycle:{check_id}")
        visiting.add(check_id)
        item = index[check_id]
        for dependency in item.get("depends_on_receipts", []):
            visit(consumers.get(str(dependency), str(dependency)))
        visiting.remove(check_id)
        visited.add(check_id)
        if item.get("kind") == "command":
            ordered.append(item)

    for item in commands:
        visit(str(item["id"]))
    return ordered, consumers


def _is_ignored(relative: Path, *, explicit: bool) -> bool:
    parts = relative.as_posix().split("/")
    if relative.name == "verification-report.json":
        return True
    if parts[:2] == [".flowguard", "history"]:
        return True
    if parts[:3] == [".flowguard", "structure", "reverse-surfaces"]:
        return True
    if parts[:2] == ["kb", "history"]:
        return True
    if relative.parts and (
        relative.parts[0].startswith(".storyline-")
        or relative.parts[0].startswith(".probe-")
    ):
        return True
    if any(
        part
        in {
            ".git",
            "__pycache__",
            ".pytest_cache",
            "evidence",
            "validation-receipts",
            "work",
            "scratch",
            "backups",
            "private",
            "run-artifacts",
            "run_artifacts",
            "verification-receipts",
        }
        for part in parts
    ):
        return True
    if relative.as_posix() in {
        "docs/coordination.md",
        "docs/flowguard_adoption_log.md",
        ".flowguard/adoption_log.jsonl",
    }:
        return True
    return relative.as_posix().startswith("skills/logic-writing/.skillguard/runs/")


def _selector_files(root: Path, selector: str) -> list[Path]:
    normalized = selector.replace("\\", "/")
    wildcard = any(character in normalized for character in "*?[")
    files: list[Path] = []

    def matches_pattern(relative: Path) -> bool:
        """Match path segments without letting ``**`` traverse ignored trees."""

        path_parts = relative.as_posix().split("/")
        pattern_parts = normalized.split("/")

        def visit(path_index: int, pattern_index: int) -> bool:
            if pattern_index == len(pattern_parts):
                return path_index == len(path_parts)
            token = pattern_parts[pattern_index]
            if token == "**":
                return visit(path_index, pattern_index + 1) or (
                    path_index < len(path_parts)
                    and visit(path_index + 1, pattern_index)
                )
            return (
                path_index < len(path_parts)
                and fnmatch.fnmatchcase(path_parts[path_index], token)
                and visit(path_index + 1, pattern_index + 1)
            )

        return visit(0, 0)

    def admit(path: Path) -> None:
        """Admit one file while pruning known runtime trees before resolve.

        The release contract intentionally watches broad source globs, while
        `_is_ignored` excludes evidence and other runtime output.  Resolving
        every historical evidence file first made a cold source snapshot very
        expensive on Windows.  A lexical check is safe as an early prune; the
        resolved path is still checked afterwards so a symlink cannot escape
        the repository or smuggle an ignored target back into the manifest.
        """

        try:
            lexical = path.relative_to(root)
        except ValueError:
            return
        if _is_ignored(lexical, explicit=not wildcard):
            return
        try:
            resolved = path.resolve()
            relative = resolved.relative_to(root)
        except (OSError, RuntimeError, ValueError):
            return
        if _is_ignored(relative, explicit=not wildcard) or not resolved.is_file():
            return
        files.append(resolved)

    if not wildcard:
        matches = [Path(item) for item in glob.glob(str(root / normalized), recursive=False)]
        for match in matches:
            if match.is_dir():
                for directory, dirnames, filenames in os.walk(
                    match, topdown=True, followlinks=False
                ):
                    directory_path = Path(directory)
                    dirnames[:] = [
                        name
                        for name in dirnames
                        if not _is_ignored(
                            directory_path.joinpath(name).relative_to(root),
                            explicit=True,
                        )
                    ]
                    for filename in filenames:
                        admit(directory_path / filename)
            elif match.is_file():
                admit(match)
    else:
        # Derive a static traversal root before the first wildcard segment.
        # This avoids the recursive ``glob.glob`` walk over ignored history and
        # run-artifact trees on archive-backed Windows workspaces.
        pattern_parts = normalized.split("/")
        static_count = 0
        for part in pattern_parts:
            if any(character in part for character in "*?["):
                break
            static_count += 1
        traversal = root.joinpath(*pattern_parts[:static_count])
        if traversal.is_file():
            if matches_pattern(traversal.relative_to(root)):
                admit(traversal)
        elif traversal.is_dir():
            for directory, dirnames, filenames in os.walk(
                traversal, topdown=True, followlinks=False
            ):
                directory_path = Path(directory)
                dirnames[:] = [
                    name
                    for name in dirnames
                    if not _is_ignored(
                        directory_path.joinpath(name).relative_to(root),
                        explicit=False,
                    )
                ]
                for filename in filenames:
                    candidate = directory_path / filename
                    if matches_pattern(candidate.relative_to(root)):
                        admit(candidate)
    if not files:
        raise ValueError(f"input_selector_has_no_files:{selector}")
    return sorted(set(files))


def _manifest(
    root: Path,
    selectors: Iterable[str],
    *,
    known_hashes: Mapping[str, str] | None = None,
    selector_cache: dict[str, list[Path]] | None = None,
) -> dict[str, str]:
    """Build one admitted input manifest.

    A frozen validation first hashes the complete public source snapshot.  The
    per-owner input manifests are subsets of that same snapshot, so reading
    each file again only adds I/O and can make a Windows run appear hung.  A
    caller may provide the already-frozen map; paths outside it are hashed once
    and added to the local cache.  The content identity is unchanged because
    cached values come from the frozen snapshot itself.
    """
    files: dict[str, Path] = {}
    for selector in selectors:
        selector_text = str(selector)
        if selector_cache is not None and selector_text in selector_cache:
            admitted_paths = selector_cache[selector_text]
        else:
            admitted_paths = _selector_files(root, selector_text)
            if selector_cache is not None:
                selector_cache[selector_text] = admitted_paths
        for path in admitted_paths:
            files[path.relative_to(root).as_posix()] = path
    manifest: dict[str, str] = {}
    pending: dict[str, Path] = {}
    for relative, path in sorted(files.items()):
        if known_hashes is not None and relative in known_hashes:
            manifest[relative] = str(known_hashes[relative])
        else:
            pending[relative] = path

    # Archive-backed Windows workspaces have high per-file latency.  Hash a
    # bounded batch concurrently, then merge in lexical order so the manifest
    # and its fingerprint remain deterministic.  Small manifests stay serial
    # to avoid thread overhead in focused unit tests.
    if len(pending) <= 4:
        computed = {relative: _file_hash(path) for relative, path in pending.items()}
    else:
        workers = min(8, len(pending))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="frozen-hash") as pool:
            futures = {
                relative: pool.submit(_file_hash, path)
                for relative, path in pending.items()
            }
            computed = {relative: futures[relative].result() for relative in sorted(futures)}
    manifest.update(computed)
    if known_hashes is not None and isinstance(known_hashes, dict):
        known_hashes.update(computed)
    return manifest


def _global_snapshot(root: Path, contract: Mapping[str, Any]) -> tuple[str, dict[str, str]]:
    selectors = [str(item) for item in (contract.get("freshness") or {}).get("watch", [])]
    selectors.append(DEFAULT_CONTRACT.as_posix())
    manifest = _manifest(root, selectors)
    return _hash(manifest), manifest


def _tree_identity(root: Path, admitted_roots: Iterable[Path]) -> dict[str, Any]:
    files: dict[str, str] = {}
    for admitted in admitted_roots:
        if not admitted.exists():
            continue
        candidates = [admitted] if admitted.is_file() else [path for path in admitted.rglob("*") if path.is_file()]
        for path in candidates:
            relative = path.relative_to(root)
            if any(part in {"__pycache__", ".pytest_cache", "evidence", "runs"} for part in relative.parts):
                continue
            if path.suffix.lower() in {".pyc", ".pyo"}:
                continue
            files[relative.as_posix()] = _file_hash(path)
    return {"file_count": len(files), "manifest_hash": _hash(files)}


def _toolchain_observation(check: Mapping[str, Any]) -> dict[str, Any]:
    declared = str(check.get("toolchain_identity", ""))
    resolved_executable = _resolve_executable(str(check.get("command", "")))
    executable = Path(resolved_executable)
    try:
        executable_hash = _file_hash(executable) if executable.is_file() else "unavailable"
    except OSError:
        # Microsoft Store app-execution aliases are runnable but are not always
        # readable as ordinary files.  Bind their command path and version
        # probe instead of treating a Windows alias as a validation failure.
        executable_hash = "unavailable"
    try:
        completed = subprocess.run(
            [resolved_executable, "--version"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=30,
            check=False,
        )
        version_probe = {
            "exit_code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        version_probe = {"error_type": type(exc).__name__}
    observation: dict[str, Any] = {
        "declared_identity": declared,
        "executable_name": executable.name,
        "executable_path_hash": _hash({"path": os.path.normcase(os.path.abspath(resolved_executable))}),
        "executable_hash": executable_hash,
        "executable_version_probe_hash": _hash(version_probe),
    }
    lowered = declared.casefold()
    if "pytest" in lowered:
        pytest = importlib.import_module("pytest")
        pytest_path = Path(pytest.__file__).resolve()
        observation["pytest"] = {
            "version": str(getattr(pytest, "__version__", "unknown")),
            "entry_hash": _file_hash(pytest_path),
        }
    if "flowguard" in lowered:
        flowguard = importlib.import_module("flowguard")
        package_root = Path(flowguard.__file__).resolve().parent
        observation["flowguard"] = {
            "schema_version": str(getattr(flowguard, "SCHEMA_VERSION", "unknown")),
            **_tree_identity(package_root, (package_root,)),
        }
    if "skillguard" in lowered:
        codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).resolve()
        skillguard_root = codex_home / "skills" / "skillguard"
        observation["skillguard"] = _tree_identity(
            skillguard_root,
            tuple(skillguard_root / name for name in ("SKILL.md", "scripts", "references", "assets")),
        )
    if "openspec" in lowered:
        try:
            completed = subprocess.run(
                [str(executable), "--version"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
                check=False,
            )
            observation["openspec_version_output_hash"] = _hash(
                {"exit_code": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}
            )
        except (OSError, subprocess.TimeoutExpired):
            observation["openspec_version_output_hash"] = "unavailable"
    observation["observation_hash"] = _hash(observation)
    return observation


def _check_manifest(
    root: Path,
    check: Mapping[str, Any],
    *,
    known_hashes: Mapping[str, str] | None = None,
    selector_cache: dict[str, list[Path]] | None = None,
) -> dict[str, str]:
    selectors = [str(item) for item in check.get("input_selectors", [])]
    if not selectors:
        raise ValueError(f"check_input_selectors_missing:{check.get('id')}")
    return _manifest(
        root,
        selectors,
        known_hashes=known_hashes,
        selector_cache=selector_cache,
    )


def _receipt_hash(receipt: Mapping[str, Any]) -> str:
    return _hash({key: value for key, value in receipt.items() if key != "receipt_hash"})


def _load_current_success(
    path: Path,
    execution_fingerprint: str,
    *,
    receipts: Path | None = None,
    check_id: str | None = None,
) -> dict[str, Any] | None:
    """Load one reusable success receipt only after reopening its evidence.

    A success file is an index entry, not proof by itself.  In particular, a
    copied receipt must not be able to point at a result outside its attempt
    directory (or at a result whose bytes no longer match the recorded
    fingerprint).  The old loader checked only the receipt's own hash, which
    allowed a self-consistent but foreign result path to be reused by a later
    frozen run.

    Invalid or stale cached evidence is treated as a cache miss.  The current
    execution then gets a new private attempt and records the failure or
    success under the current maintenance unit.
    """

    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None

    owner_id = check_id or str(value.get("check_id") or "")
    if (
        not owner_id
        or value.get("status") != "passed"
        or value.get("terminal_status") != "passed"
        or value.get("exit_code") != 0
        or value.get("timed_out") is True
        or value.get("cleanup_confirmed") is not True
        or value.get("check_id") != owner_id
        or value.get("execution_fingerprint") != execution_fingerprint
        or value.get("receipt_hash") != _receipt_hash(value)
    ):
        return None

    receipt_root = (receipts or path.parents[2]).resolve()
    try:
        # A success receipt must live in this check's success namespace and
        # its attempt must be below the same private receipt root.
        path.resolve().relative_to((receipt_root / "success" / owner_id).resolve())
        attempt_root, run_root = _owner_context_paths(value, receipt_root, check_id=owner_id)
        attempt_root.relative_to((receipt_root / "attempts" / owner_id).resolve())
        result_path = _safe_evidence_path(
            receipt_root,
            value.get("result_path"),
            field=f"result_path:{owner_id}",
        )
        result_path.relative_to(attempt_root)
        result = _read_json(result_path)
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return None
    if not isinstance(result, Mapping):
        return None
    if (
        result.get("status") != "passed"
        or result.get("check_id") != owner_id
        or result.get("execution_fingerprint") != execution_fingerprint
        or result.get("exit_code") != 0
        or result.get("timed_out") is True
        or result.get("cleanup_confirmed") is not True
        or result.get("result_fingerprint") != value.get("result_fingerprint")
        or result.get("result_fingerprint")
        != _hash({key: item for key, item in result.items() if key != "result_fingerprint"})
    ):
        return None
    # Keep the local binding explicit even though ``_owner_context_paths``
    # already checked that the run directory is below the attempt directory.
    if not run_root.is_dir():
        return None
    return value


def _powershell_process_ids(root_pid: int) -> list[int] | None:
    try:
        powershell = _resolve_executable("powershell")
        script = (
            f"$all=Get-CimInstance Win32_Process; $ids=@({root_pid}); $scan=@({root_pid}); "
            "while($scan.Count -gt 0){$next=@(); foreach($id in $scan){"
            "$children=@($all|Where-Object {$_.ParentProcessId -eq $id}|ForEach-Object {$_.ProcessId});"
            "$ids += $children; $next += $children}; $scan=$next}; $ids|Sort-Object -Unique|ConvertTo-Json -Compress"
        )
        completed = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=20,
            check=False,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            return None
        value = json.loads(completed.stdout)
        return [int(item) for item in (value if isinstance(value, list) else [value])]
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired):
        return None


def _terminate_and_confirm(process: subprocess.Popen[str]) -> tuple[bool, list[int]]:
    if os.name == "nt":
        ids = _powershell_process_ids(process.pid)
        try:
            subprocess.run(
                [_resolve_executable("taskkill"), "/PID", str(process.pid), "/T", "/F"],
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False, ids or [process.pid]
        try:
            process.wait(timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            return False, ids or [process.pid]
        if ids is None:
            return False, [process.pid]
        remaining = []
        for pid in ids:
            try:
                probe = subprocess.run(
                    [_resolve_executable("tasklist"), "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                return False, ids
            if probe.returncode == 0 and not probe.stdout.lstrip().startswith("INFO:") and f'"{pid}"' in probe.stdout:
                remaining.append(pid)
        return not remaining, remaining
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass
    try:
        os.killpg(process.pid, 0)
        return False, [process.pid]
    except ProcessLookupError:
        return True, []


def _execute(
    command: list[str],
    *,
    cwd: Path,
    timeout: int,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    resolved = [_resolve_executable(command[0]), *command[1:]]
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    started = time.monotonic()
    process = subprocess.Popen(
        resolved,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=flags,
        start_new_session=os.name != "nt",
        env=dict(env) if env is not None else None,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return {
            "exit_code": int(process.returncode),
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": False,
            "cleanup_confirmed": True,
            "remaining_process_ids": [],
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
    except subprocess.TimeoutExpired as timeout_exc:
        stdout = _text(timeout_exc.stdout)
        stderr = _text(timeout_exc.stderr)
        cleanup_error: str | None = None
        try:
            confirmed, remaining = _terminate_and_confirm(process)
        except Exception as exc:  # pragma: no cover - defensive receipt path
            confirmed = False
            remaining = [int(getattr(process, "pid", 0) or 0)]
            cleanup_error = f"{type(exc).__name__}: {exc}"
        pipe_drain_timeout = False
        try:
            tail_stdout, tail_stderr = process.communicate(timeout=10)
            stdout += _text(tail_stdout)
            stderr += _text(tail_stderr)
        except subprocess.TimeoutExpired as drain_exc:
            stdout += _text(drain_exc.stdout)
            stderr += _text(drain_exc.stderr)
            pipe_drain_timeout = True
            confirmed = False
        except Exception as exc:  # pragma: no cover - defensive receipt path
            cleanup_error = cleanup_error or f"pipe_drain:{type(exc).__name__}: {exc}"
            confirmed = False
        result = {
            "exit_code": None,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": True,
            "cleanup_confirmed": confirmed,
            "remaining_process_ids": remaining,
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
        if cleanup_error is not None:
            result["cleanup_error"] = cleanup_error
        if pipe_drain_timeout:
            result["pipe_drain_timeout"] = True
        return result


def _read_json(path: Path) -> Any:
    """Read one JSON evidence file without creating or normalising it."""

    return json.loads(path.read_text(encoding="utf-8"))


def _safe_evidence_path(root: Path, relative: Any, *, field: str) -> Path:
    """Resolve a receipt-owned relative path and reject escapes/symlinks."""

    if not isinstance(relative, (str, Path)) or not str(relative).strip():
        raise ValueError(f"{field}_missing")
    candidate_relative = Path(relative)
    if candidate_relative.is_absolute():
        raise ValueError(f"{field}_must_be_relative")
    base = root.resolve()
    candidate = (base / candidate_relative).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"{field}_escaped_receipt_root") from exc
    current = base
    for part in candidate_relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{field}_contains_symlink")
    return candidate


def _owner_context_paths(receipt: Mapping[str, Any], receipts: Path, *, check_id: str) -> tuple[Path, Path]:
    """Return the attempt and run roots recorded by one execution owner."""

    context = receipt.get("owner_context")
    if not isinstance(context, Mapping):
        raise ValueError(f"owner_context_missing:{check_id}")
    attempt_root = _safe_evidence_path(receipts, context.get("attempt_root"), field=f"owner_context.attempt_root:{check_id}")
    run_root = _safe_evidence_path(receipts, context.get("run_root"), field=f"owner_context.run_root:{check_id}")
    try:
        run_root.relative_to(attempt_root)
    except ValueError as exc:
        raise ValueError(f"owner_context.run_root_outside_attempt:{check_id}") from exc
    if not attempt_root.is_dir() or not run_root.is_dir():
        raise ValueError(f"owner_context_directory_missing:{check_id}")
    if context.get("owner_id") != check_id:
        raise ValueError(f"owner_context.owner_id_mismatch:{check_id}")
    return attempt_root, run_root


def _dependency_owner_run_root(
    dependency: str,
    *,
    index: Mapping[str, Mapping[str, Any]],
    consumers: Mapping[str, str],
    receipts: Path,
) -> Path:
    owner_id = consumers.get(str(dependency), str(dependency))
    receipt = index.get(owner_id)
    if not isinstance(receipt, Mapping):
        raise ValueError(f"dependency_owner_missing:{dependency}")
    if (
        receipt.get("status") != "passed"
        or receipt.get("terminal_status") != "passed"
        or receipt.get("exit_code") != 0
        or receipt.get("timed_out") is True
        or receipt.get("cleanup_confirmed") is not True
        or receipt.get("check_id") != owner_id
        or receipt.get("receipt_hash") != _receipt_hash(receipt)
    ):
        raise ValueError(f"dependency_owner_not_passed:{dependency}")
    attempt_root, run_root = _owner_context_paths(receipt, receipts, check_id=owner_id)
    result_path = _safe_evidence_path(
        receipts,
        receipt.get("result_path"),
        field=f"dependency.result_path:{dependency}",
    )
    try:
        result_path.relative_to(attempt_root)
    except ValueError as exc:
        raise ValueError(f"dependency_result_outside_attempt:{dependency}") from exc
    if not result_path.is_file():
        raise ValueError(f"dependency_result_missing:{dependency}")
    result = _read_json(result_path)
    if (
        not isinstance(result, Mapping)
        or result.get("status") != "passed"
        or result.get("check_id") != owner_id
        or result.get("execution_fingerprint") != receipt.get("execution_fingerprint")
        or result.get("result_fingerprint") != receipt.get("result_fingerprint")
        or result.get("result_fingerprint")
        != _hash({key: value for key, value in result.items() if key != "result_fingerprint"})
    ):
        raise ValueError(f"dependency_result_identity_mismatch:{dependency}")
    return run_root


def _materialize_owner_argument(
    value: Any,
    *,
    attempt_root: Path,
    run_root: Path,
    receipts: Path,
    index: Mapping[str, Mapping[str, Any]],
    consumers: Mapping[str, str],
) -> str:
    """Expand only the release runner's explicit owner-context placeholders."""

    text = str(value)
    replacements = {
        "{owner_attempt_root}": str(attempt_root),
        "{owner_run_root}": str(run_root),
        "{receipt_root}": str(receipts),
    }
    for token, replacement in replacements.items():
        text = text.replace(token, replacement)

    dependency_token = re.compile(r"\{dependency:([^{}:]+(?:\.[^{}:]+)*):run_root\}")

    def replace_dependency(match: re.Match[str]) -> str:
        dependency = match.group(1)
        return str(
            _dependency_owner_run_root(
                dependency,
                index=index,
                consumers=consumers,
                receipts=receipts,
            )
        )

    text = dependency_token.sub(replace_dependency, text)
    if "{" in text or "}" in text:
        raise ValueError(f"unresolved_owner_context_argument:{text}")
    return text


def _owner_environment(
    *,
    check_id: str,
    attempt_root: Path,
    run_root: Path,
    receipts: Path,
    dependencies: Iterable[str],
    index: Mapping[str, Mapping[str, Any]],
    consumers: Mapping[str, str],
) -> dict[str, str]:
    """Build a private child environment for one validation owner."""

    environment = {str(key): str(value) for key, value in os.environ.items()}
    environment.update(
        {
            # Existing owner CLIs consume this variable as their output root.
            "LW_VALIDATION_ATTEMPT_ROOT": str(run_root),
            "LW_VALIDATION_OWNER_ATTEMPT_ROOT": str(attempt_root),
            "LW_VALIDATION_OWNER_RUN_ROOT": str(run_root),
            "LW_VALIDATION_OWNER_ID": check_id,
            "LW_VALIDATION_RECEIPT_ROOT": str(receipts),
        }
    )
    for dependency in dependencies:
        owner_id = consumers.get(str(dependency), str(dependency))
        dependency_root = _dependency_owner_run_root(
            str(dependency), index=index, consumers=consumers, receipts=receipts
        )
        key = "LW_VALIDATION_DEPENDENCY_" + re.sub(r"[^A-Za-z0-9]", "_", owner_id).upper() + "_ROOT"
        environment[key] = str(dependency_root)
        if owner_id == "check.reader.execution-quality-producer":
            environment["LW_VALIDATION_DEPENDENCY_INDEX"] = str(dependency_root / "dependency-index.json")
    return environment


def _audit_existing_validation(
    root: Path,
    receipts: Path,
    *,
    contract: Mapping[str, Any],
    ordered: list[dict[str, Any]],
    consumers: Mapping[str, str],
    revision: str,
    snapshot_id: str,
    snapshot_manifest: Mapping[str, str],
    require_clean_git: bool,
) -> dict[str, Any]:
    """Audit one already-written frozen result without starting or writing anything.

    This branch deliberately performs no executable lookup, version probe, lock
    acquisition, directory creation, or semantic child execution.  It verifies
    the current source snapshot and every persisted owner/consumer artifact
    against the existing parent index only.
    """

    base = {
        "schema_version": "logic_writing_validation_index.v1",
        "audit_only": True,
        "executed_check_ids": [],
        "reused_check_ids": [],
        "claim_boundary": "Read-only audit of one existing frozen-validation parent index; no owner was started and no evidence was rewritten.",
    }
    if require_clean_git:
        return {
            **base,
            "status": "failed",
            "error": "audit_only_cannot_verify_git_clean_without_starting_a_git_probe",
        }
    if not receipts.is_dir():
        return {**base, "status": "failed", "error": "validation_receipt_root_missing"}
    index_path = receipts / "index.json"
    if not index_path.is_file():
        return {**base, "status": "failed", "error": "validation_parent_index_missing"}
    try:
        parent = _read_json(index_path)
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {**base, "status": "failed", "error": f"validation_parent_index_unreadable:{exc}"}
    if not isinstance(parent, Mapping):
        return {**base, "status": "failed", "error": "validation_parent_index_not_object"}
    if parent.get("index_hash") != _hash({key: value for key, value in parent.items() if key != "index_hash"}):
        return {**base, "status": "failed", "error": "validation_parent_index_hash_mismatch"}
    if parent.get("status") != "passed":
        return {**base, "status": "failed", "error": "validation_parent_index_not_passed"}
    if parent.get("verifier_version") != VERIFIER_VERSION:
        return {**base, "status": "failed", "error": "validation_parent_index_verifier_stale"}
    if parent.get("inventory_revision") != revision:
        return {**base, "status": "failed", "error": "validation_parent_index_inventory_stale"}
    if parent.get("frozen_snapshot_id") != snapshot_id:
        return {**base, "status": "failed", "error": "validation_parent_index_source_snapshot_stale"}
    if parent.get("frozen_snapshot_file_count") != len(snapshot_manifest):
        return {**base, "status": "failed", "error": "validation_parent_index_source_file_count_stale"}
    if parent.get("execution_owner_count") != len(ordered) or parent.get("receipt_consumer_count") != len(consumers):
        return {**base, "status": "failed", "error": "validation_parent_index_plan_counts_mismatch"}

    indexed = parent.get("receipts")
    if not isinstance(indexed, Mapping) or set(indexed) != {str(item["id"]) for item in ordered}:
        return {**base, "status": "failed", "error": "validation_parent_index_owner_set_mismatch"}
    indexed_consumers = parent.get("consumer_owners")
    if indexed_consumers != dict(consumers):
        return {**base, "status": "failed", "error": "validation_parent_index_consumer_set_mismatch"}

    validated: dict[str, Mapping[str, Any]] = {}
    known_hashes: dict[str, str] = dict(snapshot_manifest)
    selector_cache: dict[str, list[Path]] = {}
    try:
        for check in ordered:
            check_id = str(check["id"])
            receipt = indexed[check_id]
            if not isinstance(receipt, Mapping):
                raise ValueError(f"owner_receipt_not_object:{check_id}")
            if receipt.get("status") != "passed" or receipt.get("terminal_status") != "passed" or receipt.get("exit_code") != 0:
                raise ValueError(f"owner_receipt_not_passed:{check_id}")
            if receipt.get("verifier_version") != VERIFIER_VERSION:
                raise ValueError(f"owner_receipt_verifier_stale:{check_id}")
            if receipt.get("check_id") != check_id:
                raise ValueError(f"owner_receipt_check_identity_mismatch:{check_id}")
            for field in ("semantic_check_id", "execution_id"):
                if receipt.get(field) != check.get(field):
                    raise ValueError(f"owner_receipt_{field}_mismatch:{check_id}")
            if receipt.get("inventory_revision") != revision or receipt.get("artifact_version") != snapshot_id:
                raise ValueError(f"owner_receipt_source_identity_stale:{check_id}")
            if receipt.get("timed_out") or receipt.get("cleanup_confirmed") is not True:
                raise ValueError(f"owner_receipt_cleanup_or_timeout_invalid:{check_id}")
            if receipt.get("receipt_hash") != _receipt_hash(receipt):
                raise ValueError(f"owner_receipt_hash_mismatch:{check_id}")
            expected_inputs = _check_manifest(
                root,
                check,
                known_hashes=known_hashes,
                selector_cache=selector_cache,
            )
            if receipt.get("input_manifest_hash") != _hash(expected_inputs):
                raise ValueError(f"owner_receipt_input_identity_stale:{check_id}")
            dependency_hashes = {
                str(dependency): validated[consumers.get(str(dependency), str(dependency))]["receipt_hash"]
                for dependency in check.get("depends_on_receipts", [])
            }
            if receipt.get("dependency_receipt_hashes") != dependency_hashes:
                raise ValueError(f"owner_receipt_dependency_identity_mismatch:{check_id}")
            _owner_context_paths(receipt, receipts, check_id=check_id)

            result_path = _safe_evidence_path(receipts, receipt.get("result_path"), field=f"result_path:{check_id}")
            if not result_path.is_file():
                raise ValueError(f"owner_result_missing:{check_id}")
            result = _read_json(result_path)
            if not isinstance(result, Mapping):
                raise ValueError(f"owner_result_not_object:{check_id}")
            if result.get("result_fingerprint") != receipt.get("result_fingerprint"):
                raise ValueError(f"owner_result_fingerprint_mismatch:{check_id}")
            if result.get("result_fingerprint") != _hash(
                {key: value for key, value in result.items() if key != "result_fingerprint"}
            ):
                raise ValueError(f"owner_result_hash_mismatch:{check_id}")
            if result.get("check_id") != check_id or result.get("execution_fingerprint") != receipt.get("execution_fingerprint"):
                raise ValueError(f"owner_result_identity_mismatch:{check_id}")

            success_path = _safe_evidence_path(
                receipts,
                Path("success") / check_id / (str(receipt.get("execution_fingerprint", "")).removeprefix("sha256:") + ".json").replace("\\", "/"),
                field=f"success_path:{check_id}",
            )
            if not success_path.is_file() or _read_json(success_path) != dict(receipt):
                raise ValueError(f"owner_success_receipt_missing_or_mismatched:{check_id}")
            validated[check_id] = receipt
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {**base, "status": "failed", "error": str(exc)}

    mesh_info = parent.get("test_mesh")
    if not isinstance(mesh_info, Mapping) or mesh_info.get("status") != "passed":
        return {**base, "status": "failed", "error": "test_mesh_terminal_receipt_missing"}
    try:
        mesh_path = _safe_evidence_path(receipts, mesh_info.get("result_path"), field="test_mesh.result_path")
        mesh_payload = _read_json(mesh_path)
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {**base, "status": "failed", "error": f"test_mesh_terminal_receipt_invalid:{exc}"}
    if not isinstance(mesh_payload, Mapping) or mesh_payload.get("status") != "passed":
        return {**base, "status": "failed", "error": "test_mesh_terminal_receipt_not_passed"}
    if mesh_info.get("result_hash") != _hash(mesh_payload):
        return {**base, "status": "failed", "error": "test_mesh_terminal_receipt_hash_mismatch"}
    return {
        **base,
        "status": "passed",
        "verifier_version": VERIFIER_VERSION,
        "inventory_revision": revision,
        "frozen_snapshot_id": snapshot_id,
        "frozen_snapshot_file_count": len(snapshot_manifest),
        "execution_owner_count": len(ordered),
        "receipt_consumer_count": len(consumers),
        "reused_check_ids": [str(item["id"]) for item in ordered],
        "consumer_owners": dict(consumers),
        "test_mesh": {"status": "passed", "result_path": mesh_info.get("result_path")},
    }


@contextmanager
def _single_owner_lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".foreground-owner.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError("another_frozen_validation_owner_is_active_or_requires_manual_lock_review") from exc
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode("ascii"))
        os.close(descriptor)
        yield
    finally:
        if lock.exists():
            lock.unlink()


def _git_clean(root: Path) -> bool:
    try:
        completed = subprocess.run(
            [_resolve_executable("git"), "status", "--porcelain"],
            cwd=root,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=30,
            check=False,
        )
        return completed.returncode == 0 and not completed.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return False


def run_validation(
    root: Path,
    contract_path: Path,
    receipt_root: Path,
    *,
    audit_only: bool,
    require_clean_git: bool,
) -> dict[str, Any]:
    root = root.resolve()
    contract_file = (root / contract_path).resolve()
    receipts = (root / receipt_root).resolve()
    contract = _load_contract(contract_file)
    ordered, consumers = _validate_plan(contract)
    revision = _inventory_revision(contract)
    snapshot_id, snapshot_manifest = _global_snapshot(root, contract)
    # Read-only audit is intentionally isolated before any executable lookup,
    # git probe, lock acquisition, directory creation, or child process.  The
    # audit must be safe to run against a live release receipt root.
    if audit_only:
        return _audit_existing_validation(
            root,
            receipts,
            contract=contract,
            ordered=ordered,
            consumers=consumers,
            revision=revision,
            snapshot_id=snapshot_id,
            snapshot_manifest=snapshot_manifest,
            require_clean_git=require_clean_git,
        )
    toolchain_observations = {
        str(check["id"]): _toolchain_observation(check) for check in ordered
    }
    if require_clean_git and not _git_clean(root):
        raise ValueError("git_worktree_not_clean_before_frozen_validation")
    index: dict[str, dict[str, Any]] = {}
    executed: list[str] = []
    reused: list[str] = []
    known_hashes: dict[str, str] = dict(snapshot_manifest)
    selector_cache: dict[str, list[Path]] = {}

    with _single_owner_lock(receipts):
        for check in ordered:
            check_id = str(check["id"])
            inputs = _check_manifest(
                root,
                check,
                known_hashes=known_hashes,
                selector_cache=selector_cache,
            )
            dependency_hashes = {
                dependency: index[consumers.get(str(dependency), str(dependency))]["receipt_hash"]
                for dependency in check.get("depends_on_receipts", [])
            }
            execution_identity = {
                "verifier_version": VERIFIER_VERSION,
                "inventory_revision": revision,
                "check": check,
                "input_manifest": inputs,
                "dependency_receipt_hashes": dependency_hashes,
                "toolchain_observation": toolchain_observations[check_id],
            }
            execution_fingerprint = _hash(execution_identity)
            success_path = receipts / "success" / check_id / f"{execution_fingerprint.removeprefix('sha256:')}.json"
            current = _load_current_success(
                success_path,
                execution_fingerprint,
                receipts=receipts,
                check_id=check_id,
            )
            if current is not None:
                index[check_id] = current
                reused.append(check_id)
                continue
            attempt_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            attempt_root = receipts / "attempts" / check_id / attempt_id
            attempt_root.mkdir(parents=True, exist_ok=False)
            owner_run_root = attempt_root / "run"
            owner_run_root.mkdir(parents=True, exist_ok=False)
            owner_environment = _owner_environment(
                check_id=check_id,
                attempt_root=attempt_root,
                run_root=owner_run_root,
                receipts=receipts,
                dependencies=(str(item) for item in check.get("depends_on_receipts", [])),
                index=index,
                consumers=consumers,
            )
            command = [
                str(check["command"]),
                *(
                    _materialize_owner_argument(
                        item,
                        attempt_root=attempt_root,
                        run_root=owner_run_root,
                        receipts=receipts,
                        index=index,
                        consumers=consumers,
                    )
                    for item in check.get("args", [])
                ),
            ]
            try:
                result = _execute(
                    command,
                    cwd=root,
                    timeout=int(check.get("timeout_seconds", 300)),
                    env=owner_environment,
                )
            except subprocess.TimeoutExpired as exc:
                result = {
                    "exit_code": None,
                    "stdout": _text(getattr(exc, "stdout", None)),
                    "stderr": f"owner_execution_timeout:{_text(getattr(exc, 'stderr', None))}",
                    "timed_out": True,
                    "cleanup_confirmed": False,
                    "remaining_process_ids": [],
                    "elapsed_seconds": 0.0,
                    "cleanup_error": "unhandled_timeout_from_owner_executor",
                }
            except (OSError, ValueError, RuntimeError) as exc:
                result = {
                    "exit_code": None,
                    "stdout": "",
                    "stderr": f"owner_execution_error:{type(exc).__name__}:{exc}",
                    "timed_out": False,
                    "cleanup_confirmed": True,
                    "remaining_process_ids": [],
                    "elapsed_seconds": 0.0,
                }
            stdout_path = attempt_root / "stdout.txt"
            stderr_path = attempt_root / "stderr.txt"
            stdout_path.write_text(result["stdout"], encoding="utf-8")
            stderr_path.write_text(result["stderr"], encoding="utf-8")
            result_payload = {
                "check_id": check_id,
                "execution_fingerprint": execution_fingerprint,
                "exit_code": result["exit_code"],
                "timed_out": result["timed_out"],
                "cleanup_confirmed": result["cleanup_confirmed"],
                "remaining_process_count": len(result["remaining_process_ids"]),
                "elapsed_seconds": result["elapsed_seconds"],
                "stdout_hash": _file_hash(stdout_path),
                "stderr_hash": _file_hash(stderr_path),
                # This artifact is consumed by the read-only mesh audit.  Its
                # semantic terminal status must be persisted explicitly so a
                # consumer does not have to infer it from transport fields.
                "status": (
                    "passed"
                    if result["exit_code"] == int((check.get("expected") or {}).get("exit_code", 0))
                    and not result["timed_out"]
                    and result["cleanup_confirmed"]
                    else "failed"
                ),
            }
            if result.get("cleanup_error") is not None:
                result_payload["cleanup_error"] = str(result["cleanup_error"])
            if result.get("pipe_drain_timeout"):
                result_payload["pipe_drain_timeout"] = True
            result_payload["result_fingerprint"] = _hash(result_payload)
            result_path = attempt_root / "result.json"
            _write_json(result_path, result_payload)
            passed = (
                result["exit_code"] == int((check.get("expected") or {}).get("exit_code", 0))
                and not result["timed_out"]
                and result["cleanup_confirmed"]
            )
            receipt: dict[str, Any] = {
                "schema_version": "logic_writing_validation_receipt.v1",
                "check_id": check_id,
                "semantic_check_id": check.get("semantic_check_id"),
                "execution_id": check.get("execution_id"),
                "execution_fingerprint": execution_fingerprint,
                "run_id": f"run:{check_id}:{execution_fingerprint[-16:]}",
                "status": "passed" if passed else "failed",
                "terminal_status": "passed" if passed else "failed",
                "exit_code": result["exit_code"],
                "inventory_revision": revision,
                "artifact_version": snapshot_id,
                "verifier_version": VERIFIER_VERSION,
                "input_manifest_hash": _hash(inputs),
                "dependency_receipt_hashes": dependency_hashes,
                "covered_obligation_ids": list(check.get("covers", [])),
                "result_path": result_path.relative_to(receipts).as_posix(),
                "result_fingerprint": result_payload["result_fingerprint"],
                "timed_out": result["timed_out"],
                "cleanup_confirmed": result["cleanup_confirmed"],
                "cleanup_error": result.get("cleanup_error"),
                "pipe_drain_timeout": bool(result.get("pipe_drain_timeout", False)),
                "owner_context": {
                    "owner_id": check_id,
                    "attempt_root": attempt_root.relative_to(receipts).as_posix(),
                    "run_root": owner_run_root.relative_to(receipts).as_posix(),
                },
                "recorded_at": _utc_now(),
                "claim_boundary": "This receipt proves only the exact declared command, inputs, dependencies, exit status, and captured result for this validation owner.",
            }
            receipt["receipt_hash"] = _receipt_hash(receipt)
            _write_json(attempt_root / "receipt.json", receipt)
            if not passed:
                _write_json(receipts / "failures" / check_id / f"{attempt_id}.json", receipt)
                if result["timed_out"] and not result["cleanup_confirmed"]:
                    raise RuntimeError(f"cleanup_unconfirmed:{check_id}")
                raise RuntimeError(f"validation_owner_failed:{check_id}")
            _write_json(success_path, receipt)
            index[check_id] = receipt
            executed.append(check_id)

        final_snapshot_id, final_manifest = _global_snapshot(root, contract)
        if final_snapshot_id != snapshot_id or final_manifest != snapshot_manifest:
            raise RuntimeError("frozen_source_changed_during_validation")
        final_toolchains = {
            str(check["id"]): _toolchain_observation(check) for check in ordered
        }
        if final_toolchains != toolchain_observations:
            raise RuntimeError("validation_toolchain_changed_during_validation")
        for consumer, owner in consumers.items():
            if owner not in index:
                raise RuntimeError(f"receipt_consumer_owner_missing:{consumer}")
        summary = {
            "schema_version": "logic_writing_validation_index.v1",
            "status": "passed",
            "verifier_version": VERIFIER_VERSION,
            "inventory_revision": revision,
            "frozen_snapshot_id": snapshot_id,
            "frozen_snapshot_file_count": len(snapshot_manifest),
            "execution_owner_count": len(ordered),
            "receipt_consumer_count": len(consumers),
            "git_clean_required": require_clean_git,
            "git_clean_observed": require_clean_git,
            "toolchain_observations": toolchain_observations,
            "executed_check_ids": executed,
            "reused_check_ids": reused,
            "receipts": index,
            "consumer_owners": consumers,
            "claim_boundary": "This parent index binds one frozen source snapshot to exact current terminal owner receipts. Receipt consumers do not rerun owner commands.",
        }
        summary["index_hash"] = _hash(summary)
        index_path = receipts / "index.json"
        _write_json(index_path, summary)

        mesh_owner = "check.testmesh.plan"
        mesh_receipt = index.get(mesh_owner)
        if mesh_receipt is not None:
            if mesh_receipt.get("status") != "passed":
                raise RuntimeError("test_mesh_contract_owner_failed")
            mesh_result_path = _safe_evidence_path(receipts, mesh_receipt.get("result_path"), field="test_mesh.owner_result_path")
            mesh_payload = _read_json(mesh_result_path)
            if not isinstance(mesh_payload, Mapping) or mesh_payload.get("status") != "passed":
                raise RuntimeError("test_mesh_contract_owner_result_not_passed")
            summary["test_mesh"] = {
                "status": "passed",
                "owner_check_id": mesh_owner,
                "result_path": mesh_receipt.get("result_path"),
                "result_hash": _hash(mesh_payload),
            }
        elif "test_mesh" in contract:
            raise RuntimeError("test_mesh_contract_owner_missing_or_failed")
        summary["index_hash"] = _hash({key: value for key, value in summary.items() if key != "index_hash"})
        _write_json(index_path, summary)
        return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--receipt-root", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--require-clean-git", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = run_validation(
            args.root,
            args.contract,
            args.receipt_root,
            audit_only=args.audit_only,
            require_clean_git=args.require_clean_git,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, yaml.YAMLError) as exc:
        report = {
            "schema_version": "logic_writing_validation_index.v1",
            "status": "failed",
            "error": str(exc),
            "claim_boundary": "No frozen-validation pass is claimed when plan, execution, cleanup, receipt, or source-currentness checks fail.",
        }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"frozen validation: {report['status']}")
        if report.get("error"):
            print(report["error"])
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
