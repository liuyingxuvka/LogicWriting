"""Execute or audit the frozen OpenSpec validation plan under one foreground owner."""

from __future__ import annotations

import argparse
import glob
import hashlib
import importlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


VERIFIER_VERSION = "logic-writing-frozen-validation.v2"
DEFAULT_CONTRACT = Path("openspec/changes/create-logic-writing/verification-contract.yaml")
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


def _load_contract(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("checks"), list):
        raise ValueError("verification_contract_invalid")
    return value


def _inventory_revision(contract: Mapping[str, Any]) -> str:
    payload = {
        "checks": contract["checks"],
        "version": contract.get("version"),
        "change_id": contract.get("change_id"),
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
    matches = [Path(item) for item in glob.glob(str(root / normalized), recursive=True)]
    files: list[Path] = []
    for match in matches:
        if match.is_dir():
            files.extend(path for path in match.rglob("*") if path.is_file())
        elif match.is_file():
            files.append(match)
    admitted = []
    for path in sorted(set(item.resolve() for item in files)):
        relative = path.relative_to(root)
        if not _is_ignored(relative, explicit=not wildcard):
            admitted.append(path)
    if not admitted:
        raise ValueError(f"input_selector_has_no_files:{selector}")
    return admitted


def _manifest(root: Path, selectors: Iterable[str]) -> dict[str, str]:
    files: dict[str, Path] = {}
    for selector in selectors:
        for path in _selector_files(root, str(selector)):
            files[path.relative_to(root).as_posix()] = path
    return {relative: _file_hash(path) for relative, path in sorted(files.items())}


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


def _check_manifest(root: Path, check: Mapping[str, Any]) -> dict[str, str]:
    selectors = [str(item) for item in check.get("input_selectors", [])]
    if not selectors:
        raise ValueError(f"check_input_selectors_missing:{check.get('id')}")
    return _manifest(root, selectors)


def _receipt_hash(receipt: Mapping[str, Any]) -> str:
    return _hash({key: value for key, value in receipt.items() if key != "receipt_hash"})


def _load_current_success(path: Path, execution_fingerprint: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("status") != "passed"
        or value.get("exit_code") != 0
        or value.get("execution_fingerprint") != execution_fingerprint
        or value.get("receipt_hash") != _receipt_hash(value)
    ):
        return None
    result_path = path.parents[2] / str(value.get("result_path", ""))
    if not result_path.is_file():
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
            return False, ids or []
        process.wait(timeout=20)
        if ids is None:
            return False, []
        remaining = []
        for pid in ids:
            probe = subprocess.run(
                [_resolve_executable("tasklist"), "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=10,
                check=False,
            )
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


def _execute(command: list[str], *, cwd: Path, timeout: int) -> dict[str, Any]:
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
    except subprocess.TimeoutExpired:
        confirmed, remaining = _terminate_and_confirm(process)
        stdout, stderr = process.communicate(timeout=10)
        return {
            "exit_code": None,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": True,
            "cleanup_confirmed": confirmed,
            "remaining_process_ids": remaining,
            "elapsed_seconds": round(time.monotonic() - started, 3),
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
    toolchain_observations = {
        str(check["id"]): _toolchain_observation(check) for check in ordered
    }
    if require_clean_git and not _git_clean(root):
        raise ValueError("git_worktree_not_clean_before_frozen_validation")
    index: dict[str, dict[str, Any]] = {}
    executed: list[str] = []
    reused: list[str] = []

    with _single_owner_lock(receipts):
        for check in ordered:
            check_id = str(check["id"])
            inputs = _check_manifest(root, check)
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
            current = _load_current_success(success_path, execution_fingerprint)
            if current is not None:
                index[check_id] = current
                reused.append(check_id)
                continue
            if audit_only:
                raise ValueError(f"current_terminal_success_missing:{check_id}")

            command = [str(check["command"]), *(str(item) for item in check.get("args", []))]
            result = _execute(command, cwd=root, timeout=int(check.get("timeout_seconds", 300)))
            attempt_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            attempt_root = receipts / "attempts" / check_id / attempt_id
            attempt_root.mkdir(parents=True, exist_ok=False)
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
            }
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
            "executed_check_ids": executed,
            "reused_check_ids": reused,
            "receipts": index,
            "consumer_owners": consumers,
            "claim_boundary": "This parent index binds one frozen source snapshot to exact current terminal owner receipts. Receipt consumers do not rerun owner commands.",
        }
        summary["index_hash"] = _hash(summary)
        index_path = receipts / "index.json"
        _write_json(index_path, summary)

        mesh = _execute(
            [sys.executable, ".flowguard/test_mesh/run_checks.py", "--receipts", str(index_path), "--json"],
            cwd=root,
            timeout=300,
        )
        mesh_path = receipts / "test-mesh-terminal.json"
        if mesh["exit_code"] != 0 or mesh["timed_out"] or not mesh["cleanup_confirmed"]:
            _write_json(
                mesh_path,
                {
                    "status": "failed",
                    "exit_code": mesh["exit_code"],
                    "timed_out": mesh["timed_out"],
                    "cleanup_confirmed": mesh["cleanup_confirmed"],
                    "stdout_hash": _hash(mesh["stdout"]),
                    "stderr_hash": _hash(mesh["stderr"]),
                },
            )
            raise RuntimeError("test_mesh_terminal_receipt_review_failed")
        mesh_payload = json.loads(mesh["stdout"])
        _write_json(mesh_path, mesh_payload)
        summary["test_mesh"] = {
            "status": "passed",
            "result_path": mesh_path.relative_to(receipts).as_posix(),
            "result_hash": _hash(mesh_payload),
        }
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
