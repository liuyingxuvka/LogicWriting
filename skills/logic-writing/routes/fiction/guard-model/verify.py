#!/usr/bin/env python3
"""StorylineDesign-owned Guard-purpose declaration and executable proofs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


sys.dont_write_bytecode = True

CONTRACT_SCHEMA = "storyline-design.guard_model_contract.v1"
ORACLE_SCHEMA = "storyline-design.guard_oracle_set.v1"
GOOD_SCHEMA = "storyline-design.guard_known_good_set.v1"
BAD_SCHEMA = "storyline-design.guard_known_bad_set.v1"
RESULT_SCHEMA = "storyline-design.guard_model_proof_result.v1"
EXPECTED_FAILURE_COUNT = 25


class GuardModelContractError(ValueError):
    """The StorylineDesign-owned purpose contract or proof is invalid."""


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest().upper()


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardModelContractError(f"cannot load {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise GuardModelContractError(f"{path} must contain one object")
    return payload


def _safe_file(skill_root: Path, relative: object, label: str) -> Path:
    text = str(relative or "").strip()
    if not text or Path(text).is_absolute():
        raise GuardModelContractError(f"{label} must be a non-empty target-relative path")
    root = skill_root.resolve()
    path = (root / text).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise GuardModelContractError(f"{label} escapes the target skill root: {text}") from exc
    if not path.is_file():
        raise GuardModelContractError(f"{label} does not exist: {text}")
    return path


def _bundle(skill_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = skill_root / "guard-model"
    return tuple(  # type: ignore[return-value]
        _load(root / name)
        for name in ("contract.json", "oracles.json", "known-good.json", "known-bad.json")
    )


def _require_text(row: Mapping[str, Any], fields: tuple[str, ...], label: str) -> None:
    for field in fields:
        if not str(row.get(field, "")).strip():
            raise GuardModelContractError(f"{label}.{field} is required")


def validate_bundle(skill_root: Path) -> dict[str, Any]:
    contract, oracle_set, good_set, bad_set = _bundle(skill_root)
    target = str(contract.get("target_skill_id", ""))
    if contract.get("schema_version") != CONTRACT_SCHEMA or target != "storyline-design":
        raise GuardModelContractError("invalid StorylineDesign Guard-purpose contract identity")
    if contract.get("protected_failure_count") != EXPECTED_FAILURE_COUNT:
        raise GuardModelContractError("the current protected failure count must be exactly 25")
    if contract.get("authoring_order") != [
        "freeze_prevented_failure_contract",
        "build_candidate",
        "prove_known_good",
        "prove_every_known_bad",
        "issue_native_receipt",
    ]:
        raise GuardModelContractError("the purpose-before-candidate proof chain is missing")
    if contract.get("candidate_requires_contract_fingerprint") is not True:
        raise GuardModelContractError("candidate admission must require the frozen contract fingerprint")
    if contract.get("selectable_modes") != []:
        raise GuardModelContractError("the Guard-purpose contract has no selectable enforcement mode")
    _require_text(
        contract,
        ("prevented_failure_purpose", "native_owner_id", "native_route_id", "claim_boundary"),
        "contract",
    )
    external = contract.get("external_evidence_universe")
    if not isinstance(external, list) or not external:
        raise GuardModelContractError("an independently declared external evidence universe is required")
    boundary_ids: set[str] = set()
    for index, row in enumerate(external):
        if not isinstance(row, Mapping):
            raise GuardModelContractError("external evidence boundary rows must be objects")
        _require_text(row, ("boundary_id", "description", "authority_source"), f"external[{index}]")
        boundary_id = str(row["boundary_id"])
        if boundary_id in boundary_ids or row.get("required") is not True:
            raise GuardModelContractError("external evidence boundaries must be unique and required")
        boundary_ids.add(boundary_id)

    failures = contract.get("prevented_failure_classes")
    if not isinstance(failures, list) or len(failures) != EXPECTED_FAILURE_COUNT:
        raise GuardModelContractError("the independently declared failure universe must contain exactly 25 rows")
    failure_by_id: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(failures):
        if not isinstance(row, Mapping):
            raise GuardModelContractError("failure rows must be objects")
        _require_text(
            row,
            ("failure_id", "title", "block_when", "expected_finding_code", "proof_strength", "known_limit"),
            f"failures[{index}]",
        )
        failure_id = str(row["failure_id"])
        if failure_id in failure_by_id:
            raise GuardModelContractError(f"duplicate failure id: {failure_id}")
        failure_by_id[failure_id] = row

    if oracle_set.get("schema_version") != ORACLE_SCHEMA or oracle_set.get("target_skill_id") != target:
        raise GuardModelContractError("oracle set does not match the target contract")
    obligations = oracle_set.get("required_obligation_ids")
    oracles = oracle_set.get("oracles")
    if not isinstance(obligations, list) or len(obligations) != EXPECTED_FAILURE_COUNT:
        raise GuardModelContractError("the semantic obligation universe must contain exactly 25 ids")
    obligation_ids = {str(value) for value in obligations}
    if len(obligation_ids) != EXPECTED_FAILURE_COUNT:
        raise GuardModelContractError("semantic obligation ids must be unique")
    if not isinstance(oracles, list) or len(oracles) != EXPECTED_FAILURE_COUNT:
        raise GuardModelContractError("exactly one native oracle is required per failure class")
    oracle_by_id: dict[str, Mapping[str, Any]] = {}
    oracle_by_failure: dict[str, Mapping[str, Any]] = {}
    mapped_obligations: set[str] = set()
    for index, oracle in enumerate(oracles):
        if not isinstance(oracle, Mapping):
            raise GuardModelContractError("oracle rows must be objects")
        _require_text(
            oracle,
            ("oracle_id", "obligation_id", "failure_id", "native_validator", "predicate", "expected_finding_code"),
            f"oracles[{index}]",
        )
        oracle_id = str(oracle["oracle_id"])
        failure_id = str(oracle["failure_id"])
        obligation_id = str(oracle["obligation_id"])
        if oracle.get("predicate_kind") != "target_native_json_reaction_must_block":
            raise GuardModelContractError(f"unsupported oracle predicate: {oracle_id}")
        if oracle_id in oracle_by_id or failure_id in oracle_by_failure:
            raise GuardModelContractError("oracle ids and failure mappings must be one-to-one")
        if failure_id not in failure_by_id or obligation_id not in obligation_ids:
            raise GuardModelContractError(f"oracle references an unknown failure or obligation: {oracle_id}")
        if oracle.get("expected_finding_code") != failure_by_id[failure_id]["expected_finding_code"]:
            raise GuardModelContractError(f"oracle finding differs from failure declaration: {oracle_id}")
        reaction = oracle.get("expected_reaction")
        if not isinstance(reaction, Mapping) or reaction.get("source") not in {"issues", "stale_evidence"}:
            raise GuardModelContractError(f"oracle requires one actionable JSON reaction: {oracle_id}")
        if reaction.get("source") == "issues":
            _require_text(reaction, ("code", "path", "message_contains"), f"{oracle_id}.expected_reaction")
        else:
            _require_text(reaction, ("surface", "next_action"), f"{oracle_id}.expected_reaction")
        _safe_file(skill_root, oracle["native_validator"], f"{oracle_id}.native_validator")
        oracle_by_id[oracle_id] = oracle
        oracle_by_failure[failure_id] = oracle
        mapped_obligations.add(obligation_id)
    if set(oracle_by_failure) != set(failure_by_id) or mapped_obligations != obligation_ids:
        raise GuardModelContractError("failure and semantic obligation universes are not exhausted by native oracles")

    if good_set.get("schema_version") != GOOD_SCHEMA or good_set.get("target_skill_id") != target:
        raise GuardModelContractError("known-good set does not match the target")
    good_cases = good_set.get("cases")
    if not isinstance(good_cases, list) or not good_cases:
        raise GuardModelContractError("at least one known-good case is required")
    covered_good_obligations: set[str] = set()
    good_case_ids: set[str] = set()
    for index, case in enumerate(good_cases):
        if not isinstance(case, Mapping):
            raise GuardModelContractError("known-good rows must be objects")
        _require_text(case, ("case_id", "native_validator", "fixture_path"), f"known-good[{index}]")
        case_id = str(case["case_id"])
        if case_id in good_case_ids or case.get("expected_native_status") != "pass":
            raise GuardModelContractError("known-good ids must be unique and require native pass")
        if case.get("self_reported_outcome_allowed") is not False:
            raise GuardModelContractError("known-good outcomes must be target-native, not self-reported")
        covered = case.get("covered_obligation_ids")
        if not isinstance(covered, list) or not covered:
            raise GuardModelContractError(f"known-good coverage is missing: {case_id}")
        unknown = {str(value) for value in covered} - obligation_ids
        if unknown:
            raise GuardModelContractError(f"known-good case covers unknown obligations: {sorted(unknown)}")
        covered_good_obligations.update(str(value) for value in covered)
        _safe_file(skill_root, case["native_validator"], f"{case_id}.native_validator")
        _safe_file(skill_root, case["fixture_path"], f"{case_id}.fixture_path")
        good_case_ids.add(case_id)
    if covered_good_obligations != obligation_ids:
        missing = sorted(obligation_ids - covered_good_obligations)
        raise GuardModelContractError(f"known-good cases do not cover the semantic universe: {missing}")

    if bad_set.get("schema_version") != BAD_SCHEMA or bad_set.get("target_skill_id") != target:
        raise GuardModelContractError("known-bad set does not match the target")
    bad_cases = bad_set.get("cases")
    if not isinstance(bad_cases, list) or len(bad_cases) != EXPECTED_FAILURE_COUNT:
        raise GuardModelContractError("exactly 25 known-bad cases are required")
    case_by_failure: dict[str, Mapping[str, Any]] = {}
    fixture_paths: set[str] = set()
    case_ids: set[str] = set()
    for index, case in enumerate(bad_cases):
        if not isinstance(case, Mapping):
            raise GuardModelContractError("known-bad rows must be objects")
        _require_text(
            case,
            ("case_id", "failure_id", "oracle_id", "trigger_obligation_id", "fixture_path", "expected_finding_code"),
            f"known-bad[{index}]",
        )
        case_id = str(case["case_id"])
        failure_id = str(case["failure_id"])
        fixture_path = str(case["fixture_path"])
        oracle = oracle_by_failure.get(failure_id)
        if failure_id not in failure_by_id or failure_id in case_by_failure:
            raise GuardModelContractError("each declared failure must own exactly one known-bad case")
        if case_id in case_ids or fixture_path in fixture_paths:
            raise GuardModelContractError("known-bad case ids and fixture paths must be unique")
        if oracle is None or case.get("oracle_id") != oracle.get("oracle_id"):
            raise GuardModelContractError(f"known-bad case is not bound to its sole oracle: {case_id}")
        if case.get("trigger_obligation_id") != oracle.get("obligation_id"):
            raise GuardModelContractError(f"known-bad obligation differs from its oracle: {case_id}")
        if case.get("expected_finding_code") != failure_by_id[failure_id]["expected_finding_code"]:
            raise GuardModelContractError(f"known-bad finding differs from its failure: {case_id}")
        if case.get("expected_native_status") != "blocked" or case.get("self_reported_outcome_allowed") is not False:
            raise GuardModelContractError(f"known-bad case must require target-native blocking: {case_id}")
        _safe_file(skill_root, fixture_path, f"{case_id}.fixture_path")
        case_by_failure[failure_id] = case
        case_ids.add(case_id)
        fixture_paths.add(fixture_path)
    if set(case_by_failure) != set(failure_by_id):
        raise GuardModelContractError("known-bad fixtures do not exhaust the independently declared failure universe")

    skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    reference_text = (skill_root / "references" / "guard-purpose-contract.md").read_text(encoding="utf-8")
    for required in (
        "## Guard Purpose Contract",
        "guard-model/contract.json",
        "exactly one target-native oracle",
        "does not prove literary quality",
    ):
        if required not in skill_text:
            raise GuardModelContractError(f"SKILL.md is missing Guard-purpose text: {required}")
    for required in ("Purpose Before Candidate", "Independent Failure Universe", "Fixed Closure", "Claim Boundary"):
        if required not in reference_text:
            raise GuardModelContractError(f"Guard-purpose reference is incomplete: {required}")

    return {
        "target_skill_id": target,
        "contract_fingerprint": _fingerprint(contract),
        "claim_boundary": str(contract["claim_boundary"]),
        "required_obligation_ids": sorted(obligation_ids),
        "failure_by_id": failure_by_id,
        "oracle_by_failure": oracle_by_failure,
        "case_by_failure": case_by_failure,
        "good_cases": good_cases,
    }


def _run_native(skill_root: Path, validator: object, fixture: object) -> tuple[int, dict[str, Any], str]:
    validator_path = _safe_file(skill_root, validator, "native_validator")
    fixture_path = _safe_file(skill_root, fixture, "fixture_path")
    completed = subprocess.run(
        [sys.executable, str(validator_path), str(fixture_path), "--json"],
        cwd=skill_root.parents[1],
        text=True,
        capture_output=True,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise GuardModelContractError(
            f"native validator did not return JSON: {validator_path.name}: {completed.stdout!r}"
        ) from exc
    if not isinstance(payload, dict):
        raise GuardModelContractError(f"native validator returned a non-object: {validator_path.name}")
    return completed.returncode, payload, completed.stderr


def _matches_reaction(payload: Mapping[str, Any], reaction: Mapping[str, Any]) -> bool:
    rows = payload.get(str(reaction["source"]))
    if not isinstance(rows, list):
        return False
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        matched = True
        for field in ("code", "path", "surface", "next_action"):
            expected = reaction.get(field)
            if expected is not None and row.get(field) != expected:
                matched = False
                break
        message_contains = reaction.get("message_contains")
        if matched and message_contains is not None and str(message_contains) not in str(row.get("message", "")):
            matched = False
        if matched:
            return True
    return False


def prove_known_good(skill_root: Path, bundle: Mapping[str, Any]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in bundle["good_cases"]:
        exit_code, payload, stderr = _run_native(skill_root, case["native_validator"], case["fixture_path"])
        if exit_code != 0 or payload.get("passed") is not True:
            raise GuardModelContractError(
                f"known-good did not pass natively: {case['case_id']}; exit={exit_code}; stderr={stderr}"
            )
        results.append(
            {
                "case_id": case["case_id"],
                "status": "pass",
                "covered_obligation_ids": case["covered_obligation_ids"],
            }
        )
    return {"status": "pass", "case_count": len(results), "results": results}


def prove_known_bad(skill_root: Path, bundle: Mapping[str, Any], failure_id: str) -> dict[str, Any]:
    case = bundle["case_by_failure"].get(failure_id)
    oracle = bundle["oracle_by_failure"].get(failure_id)
    if case is None or oracle is None:
        raise GuardModelContractError(f"undeclared or unproved failure: {failure_id}")
    exit_code, payload, stderr = _run_native(skill_root, oracle["native_validator"], case["fixture_path"])
    if exit_code != 1 or payload.get("passed") is not False:
        raise GuardModelContractError(
            f"known-bad did not block natively: {failure_id}; exit={exit_code}; stderr={stderr}"
        )
    reaction = oracle["expected_reaction"]
    if not _matches_reaction(payload, reaction):
        raise GuardModelContractError(
            f"known-bad did not expose its declared native reaction: {failure_id}; expected={reaction}"
        )
    return {
        "status": "blocked_as_expected",
        "failure_id": failure_id,
        "case_id": case["case_id"],
        "obligation_id": oracle["obligation_id"],
        "finding_code": case["expected_finding_code"],
        "native_reaction": reaction,
    }


def prove_all_known_bad(skill_root: Path, bundle: Mapping[str, Any]) -> dict[str, Any]:
    results = [
        prove_known_bad(skill_root, bundle, failure_id)
        for failure_id in sorted(bundle["failure_by_id"])
    ]
    return {"status": "pass", "case_count": len(results), "results": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=("check-contract", "prove-known-good", "prove-known-bad", "prove-all-known-bad"),
    )
    parser.add_argument("--skill-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--failure-id")
    args = parser.parse_args(argv)
    skill_root = Path(args.skill_root).resolve()
    try:
        bundle = validate_bundle(skill_root)
        if args.action == "check-contract":
            detail: dict[str, Any] = {
                "status": "pass",
                "failure_count": len(bundle["failure_by_id"]),
                "good_case_count": len(bundle["good_cases"]),
            }
        elif args.action == "prove-known-good":
            if args.failure_id:
                raise GuardModelContractError("known-good proof does not take a failure id")
            detail = prove_known_good(skill_root, bundle)
        elif args.action == "prove-known-bad":
            if not args.failure_id:
                raise GuardModelContractError("known-bad proof requires --failure-id")
            detail = prove_known_bad(skill_root, bundle, args.failure_id)
        else:
            if args.failure_id:
                raise GuardModelContractError("aggregate known-bad proof does not take a failure id")
            detail = prove_all_known_bad(skill_root, bundle)
        result = {
            "schema_version": RESULT_SCHEMA,
            "status": "pass",
            "action": args.action,
            "target_skill_id": bundle["target_skill_id"],
            "contract_fingerprint": bundle["contract_fingerprint"],
            "detail": detail,
            "claim_boundary": bundle["claim_boundary"],
        }
    except (GuardModelContractError, KeyError, TypeError, ValueError) as exc:
        result = {
            "schema_version": RESULT_SCHEMA,
            "status": "blocked",
            "action": args.action,
            "error": str(exc),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
