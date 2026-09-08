#!/usr/bin/env python3
"""Emit target-native positive/shallow depth calibration for Storyline Design."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SKILL_ROOT = Path(__file__).resolve().parents[1]
_candidates = [SKILL_ROOT.parent / "skillguard"]
_codex_home = os.environ.get("CODEX_HOME", "").strip()
if _codex_home:
    _candidates.append(Path(_codex_home) / "skills" / "skillguard")
_candidates.append(Path.home() / ".codex" / "skills" / "skillguard")
SKILLGUARD_SCRIPTS = next(
    (candidate / "scripts" for candidate in _candidates if (candidate / "scripts").is_dir()),
    None,
)
if SKILLGUARD_SCRIPTS is None:
    raise SystemExit("current SkillGuard scripts are unavailable")
if str(SKILLGUARD_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILLGUARD_SCRIPTS))

from skillguard_v2.calibration_evidence_protocol import (  # noqa: E402
    CALIBRATION_EVIDENCE_DOMAIN,
    IMPORTANT_OBLIGATION_BLOCKER,
    TARGET_NATIVE_CALIBRATION_OBSERVATION_SCHEMA,
    TARGET_NATIVE_DEPTH_CALIBRATION_EVIDENCE_SCHEMA,
    TARGET_NATIVE_OUTCOME_AUTHORITY,
    build_target_native_calibration_evidence,
    calibration_contract_surface,
    calibration_input_manifest,
)
from skillguard_v2.contract_compiler import (  # noqa: E402
    canonical_hash,
    canonical_json_bytes,
    source_file_hash,
)
from skillguard_v2.run_store import (  # noqa: E402
    load_check_manifest_snapshot,
    load_contract_snapshot,
    load_run,
)
from skillguard_v2.runtime_fingerprint import RUNTIME_CAPABILITY_IDS  # noqa: E402
from skillguard_v2.target_inputs import fingerprint_target_inputs  # noqa: E402


PASS_STATUS = "EXECUTION_DEPTH_PASS"
SHALLOW_STATUS = "SHALLOW_BLOCKED"
GUARD_RECEIPT_OBLIGATION = "obligation:storyline-design:guard-receipt"
SURFACE_TO_OBLIGATION = {
    "surface:route-compiled": "obligation:storyline-design:route-authority",
    "surface:real-artifact-opened-and-hashed": "obligation:storyline-design:real-artifact",
    "surface:guard-terminal-receipt-consumed": GUARD_RECEIPT_OBLIGATION,
    "surface:project-mesh-validated": "obligation:storyline-design:project-mesh",
    "surface:claim-boundary-preserved": "obligation:storyline-design:claim-boundary",
}
_FIXTURE_FIELDS = frozenset({"schema_version", "case_id", "executed_surface_ids"})


def evaluate_executed_surfaces(
    executed_surface_ids: Sequence[str],
    *,
    important_obligation_ids: Sequence[str],
) -> tuple[str, str, str, list[str]]:
    """Return target-native status, blocker, omitted obligation, and coverage."""

    executed = [str(item) for item in executed_surface_ids]
    if len(executed) != len(set(executed)) or not set(executed).issubset(SURFACE_TO_OBLIGATION):
        return SHALLOW_STATUS, "target_native_surface_selection_invalid", "", []
    important = sorted(str(item) for item in important_obligation_ids)
    if set(important) != set(SURFACE_TO_OBLIGATION.values()):
        raise ValueError("Storyline evaluator obligation mapping is stale")
    covered = sorted(SURFACE_TO_OBLIGATION[item] for item in executed)
    missing = sorted(set(important) - set(covered))
    if not missing and set(executed) == set(SURFACE_TO_OBLIGATION):
        return PASS_STATUS, "none", "", covered
    if len(missing) == 1:
        return SHALLOW_STATUS, IMPORTANT_OBLIGATION_BLOCKER, missing[0], covered
    return SHALLOW_STATUS, "multiple_important_obligations_missing", "", covered


def _declared_case(contract: Mapping[str, Any], check_id: str) -> tuple[str, Mapping[str, Any]]:
    profile = contract.get("depth_profile", {})
    calibration = profile.get("calibration", {}) if isinstance(profile, Mapping) else {}
    matches: list[tuple[str, Mapping[str, Any]]] = []
    if isinstance(calibration, Mapping):
        for kind, rows in (
            ("positive", calibration.get("positive_cases", [])),
            ("shallow", calibration.get("shallow_cases", [])),
        ):
            if isinstance(rows, list):
                matches.extend(
                    (kind, row)
                    for row in rows
                    if isinstance(row, Mapping) and row.get("native_check_id") == check_id
                )
    if len(matches) != 1:
        raise ValueError(f"exactly one calibration case required for {check_id}")
    return matches[0]


def _declared_check(manifest: Mapping[str, Any], check_id: str) -> Mapping[str, Any]:
    matches = [
        row
        for row in manifest.get("checks", [])
        if isinstance(row, Mapping) and row.get("check_id") == check_id
    ]
    if len(matches) != 1:
        raise ValueError(f"exactly one manifest check required for {check_id}")
    return matches[0]


def _under(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(root.resolve())
    return resolved


def _write_immutable(path: Path, payload: object) -> None:
    encoded = canonical_json_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = path.open("xb")
    except FileExistsError:
        if path.read_bytes() != encoded:
            raise ValueError("native calibration receipt hash collision")
    else:
        with handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--check-id", required=True)
    args = parser.parse_args(argv)

    run_root = Path(args.run_root).resolve()
    repository_root = Path(args.repository_root).resolve()
    target_root = Path(args.target_root).resolve()
    if not repository_root.is_dir() or not target_root.is_dir():
        raise ValueError("repository root and target root must exist")
    output = _under(run_root / args.output, run_root)
    run = load_run(run_root)
    contract = load_contract_snapshot(run_root)
    manifest_snapshot = load_check_manifest_snapshot(run_root)
    case_kind, declared = _declared_case(contract, args.check_id)
    check = _declared_check(manifest_snapshot, args.check_id)
    surface = calibration_contract_surface(
        contract=contract,
        check=check,
        case_kind=case_kind,
        declared_case=declared,
    )
    evaluator_version = source_file_hash(Path(__file__))
    if surface["evaluator_version"] != evaluator_version:
        raise ValueError("target-native evaluator version is stale")
    runtime_capabilities = sorted(str(item) for item in RUNTIME_CAPABILITY_IDS)
    if runtime_capabilities != list(surface["required_capability_ids"]):
        raise ValueError("active SkillGuard runtime capability surface is stale")

    request = run.get("request", {})
    if not isinstance(request, Mapping):
        raise ValueError("run request missing")
    target_input_paths = request.get("target_input_paths")
    if not isinstance(target_input_paths, list) or not target_input_paths:
        raise ValueError("calibration requires non-empty target_input_paths")
    current_target_inputs = fingerprint_target_inputs(target_root, target_input_paths)
    if current_target_inputs.get("fingerprint") != request.get("target_input_fingerprint"):
        raise ValueError("target input fingerprint changed before calibration")

    fixture_path = Path(str(declared["fixture_path"])).as_posix()
    if Path(args.fixture).as_posix() != fixture_path:
        raise ValueError("fixture argument does not match immutable calibration case")
    declared_inputs = sorted(Path(str(path)).as_posix() for path in declared["calibration_input_paths"])
    supplied_inputs = sorted(Path(str(path)).as_posix() for path in args.input)
    if supplied_inputs != declared_inputs:
        raise ValueError("input arguments do not match immutable calibration input set")
    input_manifest = calibration_input_manifest(repository_root, supplied_inputs)
    if input_manifest["calibration_input_hashes"] != declared["calibration_input_hashes"]:
        raise ValueError("calibration input file hashes are stale")
    if input_manifest["input_fingerprint"] != declared["input_fingerprint"]:
        raise ValueError("calibration input fingerprint is stale")
    fixture_file = _under(repository_root / fixture_path, repository_root)
    fixture_hash = source_file_hash(fixture_file)
    if fixture_hash != declared["fixture_sha256"]:
        raise ValueError("calibration fixture hash is stale")
    fixture = json.loads(fixture_file.read_text(encoding="utf-8"))
    if not isinstance(fixture, Mapping) or fixture.get("case_id") != declared["case_id"]:
        raise ValueError("calibration fixture binding mismatch")
    unknown_fields = sorted(set(fixture) - _FIXTURE_FIELDS)
    if unknown_fields:
        raise ValueError("calibration fixture authors forbidden fields: " + ",".join(unknown_fields))
    executed = fixture.get("executed_surface_ids", [])
    if not isinstance(executed, list):
        raise ValueError("executed_surface_ids must be a list")
    status, blocker_code, blocker_obligation_id, covered_important = evaluate_executed_surfaces(
        executed,
        important_obligation_ids=surface["important_obligation_ids"],
    )
    if case_kind == "positive" and status != PASS_STATUS:
        raise ValueError("target-native positive evaluator did not cover all obligations")
    if case_kind == "shallow" and (
        status != SHALLOW_STATUS
        or blocker_code != IMPORTANT_OBLIGATION_BLOCKER
        or blocker_obligation_id != surface["omitted_important_obligation_id"]
    ):
        raise ValueError("target-native shallow evaluator did not block for the exact omission")

    created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    native_receipt_id = "storyline-depth-calibration:" + canonical_hash(
        {
            "run_id": run["run_id"],
            "case_id": declared["case_id"],
            "case_kind": case_kind,
            "input_fingerprint": input_manifest["input_fingerprint"],
            "executed_surface_ids": sorted(str(item) for item in executed),
            "covered_important_obligation_ids": covered_important,
            "observed_status": status,
            "native_blocker_code": blocker_code,
            "native_blocker_obligation_id": blocker_obligation_id,
        }
    )[:24].lower()
    common = {
        "target_skill_id": str(surface["target_skill_id"]),
        "target_contract_hash": str(run["contract_hash"]),
        "depth_profile_hash": str(surface["depth_profile_hash"]),
        "native_owner_id": str(surface["native_owner_id"]),
        "native_route_id": str(surface["native_route_id"]),
        "native_check_id": str(surface["native_check_id"]),
        "check_id": args.check_id,
        "calibration_check_id": args.check_id,
        "run_id": str(run["run_id"]),
        "request_fingerprint": str(run["request_fingerprint"]),
        "target_input_fingerprint": str(request["target_input_fingerprint"]),
        "target_obligation_ids": list(surface["important_obligation_ids"]),
        "evidence_domain": CALIBRATION_EVIDENCE_DOMAIN,
        "evaluator_id": str(surface["evaluator_id"]),
        "evaluator_version": str(surface["evaluator_version"]),
        "calibration_pair_id": str(surface["calibration_pair_id"]),
        "input_family_fingerprint": str(surface["input_family_fingerprint"]),
        "important_obligation_ids": list(surface["important_obligation_ids"]),
        "covered_important_obligation_ids": covered_important,
        "required_capability_ids": list(surface["required_capability_ids"]),
        "covered_capability_ids": runtime_capabilities,
        "omitted_important_obligation_id": str(surface["omitted_important_obligation_id"]),
        "native_blocker_code": blocker_code,
        "native_blocker_obligation_id": blocker_obligation_id,
        "outcome_authority": TARGET_NATIVE_OUTCOME_AUTHORITY,
        "case_id": str(declared["case_id"]),
        "case_kind": case_kind,
        "fixture_path": fixture_path,
        "fixture_sha256": fixture_hash,
        "calibration_input_paths": list(input_manifest["calibration_input_paths"]),
        "calibration_input_hashes": dict(input_manifest["calibration_input_hashes"]),
        "input_fingerprint": str(input_manifest["input_fingerprint"]),
        "observed_status": status,
        "observed_blocker_code": blocker_code,
        "native_receipt_id": native_receipt_id,
        "native_receipt_created_at": created_at,
    }
    native_receipt = {"schema_version": TARGET_NATIVE_CALIBRATION_OBSERVATION_SCHEMA, **common}
    native_receipt["receipt_hash"] = canonical_hash(native_receipt)
    native_receipt_bytes = canonical_json_bytes(native_receipt)
    native_receipt_hash = hashlib.sha256(native_receipt_bytes).hexdigest().upper()
    native_receipt_relative = Path("calibration-native-receipts") / f"{native_receipt_hash[:24].lower()}.json"
    _write_immutable(run_root / native_receipt_relative, native_receipt)
    envelope = build_target_native_calibration_evidence(
        {
            "schema_version": TARGET_NATIVE_DEPTH_CALIBRATION_EVIDENCE_SCHEMA,
            **common,
            "native_receipt_hash": native_receipt_hash,
            "native_receipt_artifact_ref": {
                "path_token": "run_root",
                "relative_path": native_receipt_relative.as_posix(),
            },
        }
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    temporary.write_bytes(canonical_json_bytes(envelope))
    os.replace(temporary, output)
    print(
        json.dumps(
            {
                "case_id": declared["case_id"],
                "status": status,
                "observed_blocker_code": blocker_code,
                "native_blocker_obligation_id": blocker_obligation_id,
                "covered_important_obligation_ids": covered_important,
                "evidence_payload_hash": envelope["evidence_payload_hash"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
