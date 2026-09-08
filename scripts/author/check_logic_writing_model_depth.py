"""Check LogicWriting's current model, source bindings, and mesh receipts.

This author-side check is read-only.  It consumes current typed authority and
target-owned receipts, runs the native hierarchy reviewers against those
receipts, and never runs an owner or writes evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


SCHEMA_VERSION = "logic-writing.model-depth-check.v1"
EXPECTED_SYSTEM_ID = "logic-writing"
EXPECTED_OBLIGATION = "obligation:logic-writing:model-depth"
EXPECTED_DIMENSIONS = ("input", "state", "output", "effect", "order", "completion")
EXPECTED_MODEL_IDS = (
    "academic_route_model",
    "artifact_audit",
    "behavior_commitment_ledger",
    "composition_graph",
    "development_process_flow",
    "editorial_disposition",
    "execution_binding",
    "fiction_route_model",
    "investigation_route_model",
    "logic_writing_models",
    "model_test_alignment",
    "operation_freshness_closure_model",
    "plan_detailing",
    "primary_path_authority",
    "reader_artifact_model",
    "release_retirement_model",
    "research_packet_model",
    "researchguard_handoff",
    "route_and_guard_model",
    "test_mesh",
    "travel_route_model",
    "writer_projection",
)


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _source_sha(path: Path) -> str:
    """Use FlowGuard's canonical source identity for text bindings.

    Authority snapshots are built with ``canonical_source_bytes`` so an
    equivalent CRLF/LF checkout has the same source identity.  Native
    execution envelopes still use ``_sha`` for their immutable artifact bytes;
    keeping the two helpers separate prevents a source-normalization rule from
    weakening artifact-integrity checks.
    """
    from flowguard.source_identity import source_file_fingerprint

    return source_file_fingerprint(path)


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _model_id(value: Any) -> str:
    return str(value or "").strip().removeprefix("model:")


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _finding(findings: list[dict[str, str]], code: str, detail: Any = "", model_id: str = "") -> None:
    row: dict[str, str] = {"code": code}
    if model_id:
        row["model_id"] = model_id
    if detail:
        row["detail"] = _text(detail)
    findings.append(row)


def _mesh(root: Path):
    flowguard_root = root / ".flowguard"
    if str(flowguard_root) not in sys.path:
        sys.path.insert(0, str(flowguard_root))
    from models.owners import _mesh_support

    return _mesh_support


def _descendants(model_id: str, children: Mapping[str, tuple[str, ...]]) -> tuple[str, ...]:
    result: list[str] = []
    for child_id in children.get(model_id, ()):
        result.append(child_id)
        result.extend(_descendants(child_id, children))
    return tuple(result)


def _source_inventory(root: Path, mesh: Any, checker_path: Path, findings: list[dict[str, str]]) -> dict[str, str]:
    inventory: dict[str, str] = {}
    for model_id in EXPECTED_MODEL_IDS:
        try:
            source_hashes = mesh._source_hashes(model_id, root)
        except Exception as exc:
            _finding(findings, "current_source_binding_unavailable", f"{type(exc).__name__}: {exc}", model_id)
            continue
        inventory.update({str(path): str(value) for path, value in sorted(source_hashes.items())})
    for path in (
        checker_path,
        root / "scripts" / "author" / "skillguard_contract_model.py",
        root / "skills" / "logic-writing" / ".skillguard" / "contract-source.json",
    ):
        relative = _relative(path, root)
        if not path.is_file() or path.is_symlink():
            _finding(findings, "current_source_binding_unavailable", f"missing or symlink: {relative}")
            inventory[relative] = "missing"
        else:
            inventory[relative] = _source_sha(path)
    return inventory


def _authority(root: Path, findings: list[dict[str, str]]) -> tuple[Any, str, str]:
    try:
        from flowguard.model_authority_store import load_current_model_authority_state

        state = load_current_model_authority_state(root, reverify_current_sources=True)
    except Exception as exc:
        _finding(findings, "current_model_authority_unavailable", f"{type(exc).__name__}: {exc}")
        return None, "", ""
    head = state.head
    snapshot = state.snapshot
    revision = state.accepted_revision
    head_fp = str(getattr(head, "fingerprint", ""))
    revision_id = str(getattr(revision, "revision_set_id", "")) if revision is not None else ""
    if head.system_id != EXPECTED_SYSTEM_ID or snapshot.system_id != EXPECTED_SYSTEM_ID:
        _finding(findings, "current_model_authority_system_mismatch", {"head": head.system_id, "snapshot": snapshot.system_id, "expected": EXPECTED_SYSTEM_ID})
    if revision is None:
        _finding(findings, "accepted_model_revision_missing")
        return state, revision_id, head_fp
    if revision.status != "accepted":
        _finding(findings, "accepted_model_revision_not_accepted", revision.status)
    if revision.schema != "flowguard.model_revision_set.v5":
        _finding(findings, "accepted_model_revision_schema_invalid", revision.schema)
    if revision.candidate_snapshot_fingerprint != snapshot.fingerprint:
        _finding(findings, "accepted_model_revision_snapshot_mismatch")
    if head.snapshot_fingerprint != snapshot.fingerprint:
        _finding(findings, "authority_head_snapshot_mismatch")
    if head.accepted_revision_set_fingerprint != revision.fingerprint:
        _finding(findings, "authority_head_revision_mismatch")
    view = revision.current_effective_intent_view
    if view is None:
        _finding(findings, "current_effective_intent_view_missing")
    else:
        if view.candidate_snapshot_fingerprint != snapshot.fingerprint:
            _finding(findings, "current_effective_intent_snapshot_mismatch")
        contributions = tuple(view.active_contributions) + tuple(revision.intent_contributions)
        if not any(
            _model_id(getattr(row, "logical_model_id", "")) == "logic_writing_models"
            or EXPECTED_OBLIGATION in set(getattr(row, "target_obligation_ids", ()))
            or any("logic_writing_models" in str(item) for item in getattr(row, "target_relation_ids", ()))
            for row in contributions
        ):
            _finding(findings, "model_depth_intent_contribution_missing")
    return state, revision_id, head_fp


def _snapshot(root: Path, mesh: Any, state: Any, findings: list[dict[str, str]]) -> None:
    if state is None:
        return
    snapshot = state.snapshot
    expected = set(EXPECTED_MODEL_IDS)
    instances = tuple(snapshot.model_instances)
    by_id = {_model_id(item.logical_model_id): item for item in instances}
    if set(by_id) != expected:
        _finding(findings, "current_model_topology_mismatch", {"missing": sorted(expected - set(by_id)), "unexpected": sorted(set(by_id) - expected)})
    root_instance = by_id.get("logic_writing_models")
    if root_instance is None or root_instance.fingerprint not in set(snapshot.root_instance_fingerprints):
        _finding(findings, "current_model_root_missing")
    for model_id in EXPECTED_MODEL_IDS:
        instance = by_id.get(model_id)
        if instance is None:
            continue
        expected_model = Path(mesh.MODEL_PATHS[model_id]).as_posix()
        expected_runner = Path(mesh.RUNNER_PATHS[model_id]).as_posix()
        if str(instance.model_path).replace("\\", "/") != expected_model:
            _finding(findings, "current_model_path_mismatch", {"actual": instance.model_path, "expected": expected_model}, model_id)
        if str(instance.runner_path).replace("\\", "/") != expected_runner:
            _finding(findings, "current_runner_path_mismatch", {"actual": instance.runner_path, "expected": expected_runner}, model_id)
        for label, relative, declared in (("model", expected_model, instance.model_sha256), ("runner", expected_runner, instance.runner_sha256)):
            path = root / relative
            if not path.is_file() or path.is_symlink():
                _finding(findings, "current_model_binding_missing", relative, model_id)
            elif _source_sha(path) != declared:
                _finding(findings, "current_model_binding_stale", label, model_id)
        try:
            source_paths = set(mesh._source_paths(model_id, root))
        except Exception as exc:
            _finding(findings, "current_source_binding_unavailable", f"{type(exc).__name__}: {exc}", model_id)
            continue
        declared_inputs = {str(item.path).replace("\\", "/"): item for item in instance.inputs}
        missing = sorted(source_paths - set(declared_inputs))
        if missing:
            _finding(findings, "current_model_test_binding_missing", missing, model_id)
        for relative, item in sorted(declared_inputs.items()):
            path = root / relative
            if not path.is_file() or path.is_symlink():
                _finding(findings, "current_model_input_missing", relative, model_id)
            elif _source_sha(path) != item.sha256:
                _finding(findings, "current_model_input_stale", relative, model_id)


def _native(root: Path, mesh: Any, model_id: str, payload: Mapping[str, Any], findings: list[dict[str, str]]) -> None:
    native = payload.get("native_case")
    if not isinstance(native, Mapping):
        _finding(findings, "native_terminal_receipt_missing", model_id=model_id)
        return
    candidate = Path(str(native.get("path", ""))).expanduser()
    actual = candidate.resolve()
    # The native owner may receive FLOWGUARD_OUTPUT_DIR from the real execution
    # launcher. Consume its declared terminal artifact, then verify its exact
    # content/owner/source identity; a historical default directory is not authority.
    if not candidate.is_absolute() or candidate.is_symlink() or candidate.name != "native-case-results.json":
        _finding(findings, "native_terminal_receipt_path_mismatch", str(candidate), model_id)
        return
    if not actual.is_file():
        _finding(findings, "native_terminal_receipt_missing", str(actual), model_id)
        return
    if native.get("fingerprint") != _sha(actual):
        _finding(findings, "native_terminal_receipt_fingerprint_stale", model_id=model_id)
    try:
        from flowguard.native_case_protocol import load_native_model_case_results

        rows = load_native_model_case_results(actual)
    except Exception as exc:
        _finding(findings, "native_terminal_receipt_unreadable", f"{type(exc).__name__}: {exc}", model_id)
        return
    if len(rows) != 1:
        _finding(findings, "native_terminal_receipt_cardinality_invalid", len(rows), model_id)
        return
    result = rows[0]
    if native.get("result") != result.to_dict():
        _finding(findings, "native_terminal_receipt_result_mismatch", model_id=model_id)
    if result.owner_id != f"model:{model_id}" or result.source_case_id != f"mesh:{model_id}:current":
        _finding(findings, "native_terminal_receipt_identity_mismatch", {"owner": result.owner_id, "case": result.source_case_id}, model_id)
    if result.outcome != "pass" or result.observed_status != str(payload.get("status", "")):
        _finding(findings, "native_terminal_receipt_not_current_pass", {"outcome": result.outcome, "observed_status": result.observed_status, "receipt_status": payload.get("status")}, model_id)
    if tuple(result.executed_dimensions) != EXPECTED_DIMENSIONS:
        _finding(findings, "native_terminal_receipt_dimensions_incomplete", list(result.executed_dimensions), model_id)
    if result.observed_finding_codes:
        _finding(findings, "native_terminal_receipt_has_findings", list(result.observed_finding_codes), model_id)
    oracle_by_dimension = {str(row.get("dimension")): row for row in result.oracle_results}
    if set(oracle_by_dimension) != set(EXPECTED_DIMENSIONS):
        _finding(findings, "native_terminal_receipt_oracles_incomplete", sorted(oracle_by_dimension), model_id)
    else:
        for dimension in EXPECTED_DIMENSIONS:
            row = oracle_by_dimension[dimension]
            if row.get("ok") is not True or row.get("status") != result.observed_status:
                _finding(findings, "native_terminal_receipt_oracle_failed", {"dimension": dimension, "row": row}, model_id)
    if result.model_fingerprint != payload.get("model_fingerprint"):
        _finding(findings, "native_terminal_receipt_model_mismatch", model_id=model_id)
    raw = actual.parent / result.raw_artifact_path
    if result.raw_artifact_path != "raw-result.json" or not raw.is_file() or raw.is_symlink():
        _finding(findings, "native_terminal_raw_artifact_missing", result.raw_artifact_path, model_id)
    elif result.result_artifact_fingerprint != _sha(raw):
        _finding(findings, "native_terminal_raw_artifact_stale", model_id=model_id)
    else:
        try:
            observed = json.loads(raw.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            _finding(findings, "native_terminal_raw_payload_mismatch", f"unreadable raw payload: {exc}", model_id)
            return
        expected_raw = {
            "schema_version": "logic-writing.model-mesh-raw-result.v1",
            "model_id": model_id,
            "status": payload.get("status"),
            "summary": payload.get("summary"),
            "source_hashes": payload.get("source_hashes"),
        }
        if not isinstance(observed, Mapping):
            _finding(findings, "native_terminal_raw_payload_mismatch", "raw payload is not an object", model_id)
        else:
            for field, expected_value in expected_raw.items():
                if observed.get(field) != expected_value:
                    _finding(findings, "native_terminal_raw_payload_mismatch", field, model_id)
        sources = payload.get("source_hashes", {})
        if not isinstance(sources, Mapping):
            _finding(findings, "native_terminal_raw_payload_mismatch", "source_hashes is not an object", model_id)
            return
        expected_bindings = {
            "code": _fingerprint({"model": payload.get("model_fingerprint"), "sources": dict(sources)}),
            "test": _fingerprint({
                "runner": sources.get(mesh.RUNNER_PATHS[model_id], ""),
                "tests": [sources.get(path, "") for path in mesh.TEST_PATHS.get(model_id, ())],
            }),
            "oracle": _fingerprint({"model_id": model_id, "status": payload.get("status"), "oracle": "native-model-mesh"}),
        }
        for field, expected_value in expected_bindings.items():
            if getattr(result, f"{field}_fingerprint") != expected_value:
                _finding(findings, f"native_terminal_receipt_{field}_mismatch", model_id=model_id)


def _subtree(payload: Mapping[str, Any], model_id: str, children: tuple[str, ...], descendants: tuple[str, ...], payloads: Mapping[str, Mapping[str, Any]], authority_head: str, findings: list[dict[str, str]]) -> None:
    subtree = payload.get("subtree_receipt")
    if not children:
        if subtree is not None:
            _finding(findings, "leaf_has_unexpected_subtree_receipt", model_id=model_id)
        return
    if not isinstance(subtree, Mapping):
        _finding(findings, "missing_grandchild_receipt", model_id=model_id)
        return
    try:
        from flowguard.recursive_hierarchy import VerifiedSubtreeReceipt

        typed = VerifiedSubtreeReceipt.from_dict(subtree)
    except Exception as exc:
        _finding(findings, "subtree_receipt_invalid", f"{type(exc).__name__}: {exc}", model_id)
        return
    # FlowGuard's recursive receipt wire format canonicalizes identity lists
    # with sorted, de-duplicated ids.  The product mesh keeps declaration order
    # for execution, so compare the serialized subtree against that canonical
    # form instead of falsely marking every fresh parent receipt stale.
    canonical_children = tuple(sorted(set(children)))
    canonical_descendants = tuple(sorted(set(descendants)))
    child_ids = tuple(
        sorted(str(payloads[item]["receipt_id"]) for item in children if item in payloads)
    )
    child_fps = {str(payloads[item]["receipt_id"]): str(payloads[item]["receipt_fingerprint"]) for item in children if item in payloads}
    checks = (
        (typed.model_id == model_id, "model identity"),
        (typed.owner_id == payload.get("owner_id"), "owner identity"),
        (typed.structural_parent_id == payload.get("parent_model_id", ""), "structural parent"),
        (typed.model_fingerprint == payload.get("model_fingerprint"), "model fingerprint"),
        (typed.status == "passed" and typed.current is True and typed.terminal is True, "terminal currentness"),
        (tuple(typed.direct_child_ids) == canonical_children, "direct children"),
        (tuple(typed.descendant_model_ids) == canonical_descendants, "descendants"),
        (tuple(typed.child_receipt_ids) == child_ids, "child receipt ids"),
        (dict(typed.child_receipt_fingerprints) == child_fps, "child receipt fingerprints"),
    )
    for ok, label in checks:
        if not ok:
            _finding(findings, "old_parent_summary", f"subtree {label} is stale", model_id)
    if authority_head:
        if typed.model_authority_head_fingerprint != authority_head:
            _finding(findings, "subtree_authority_binding_missing", model_id=model_id)
        try:
            verified = typed.is_verified(require_authority=True, expected_model_authority_head_fingerprint=authority_head)
        except Exception as exc:
            _finding(findings, "subtree_authority_verification_error", exc, model_id)
            verified = False
        if verified is not True:
            _finding(findings, "subtree_authority_verification_failed", model_id=model_id)


def _parent_review(root: Path, mesh: Any, parent_id: str, payloads: Mapping[str, Mapping[str, Any]], authority_head: str, findings: list[dict[str, str]]) -> None:
    if parent_id not in payloads:
        _finding(findings, "missing_parent_receipt", parent_id, parent_id)
        return
    children = tuple(mesh.CHILDREN.get(parent_id, ()))
    if any(child not in payloads for child in children):
        _finding(findings, "parent_child_receipt_missing", {"expected": list(children), "loaded": sorted(payloads)}, parent_id)
        return
    child_payloads = [payloads[child] for child in children]
    try:
        partition, _ = mesh._partition(parent_id, child_payloads, root)
        hierarchy = mesh.review_hierarchical_mesh(partition)
        closure = mesh.review_mesh_closure_model(partition.closure_model, partition.child_models)
        negative = mesh._negative_oracles(partition)
    except Exception as exc:
        _finding(findings, "model_mesh_review_unavailable", f"{type(exc).__name__}: {exc}", parent_id)
        return
    if getattr(hierarchy, "ok", False) is not True:
        _finding(findings, "hierarchy_review_failed", getattr(hierarchy, "findings", ()), parent_id)
    if getattr(closure, "ok", False) is not True:
        _finding(findings, "closure_review_failed", getattr(closure, "findings", ()), parent_id)
    if negative.get("negative_matrix_complete") is not True or any(value is not True for key, value in negative.items() if key != "negative_matrix_complete"):
        _finding(findings, "negative_counterexample_matrix_incomplete", negative, parent_id)
    parent = payloads[parent_id]
    summary = parent.get("summary")
    if not isinstance(summary, Mapping):
        _finding(findings, "old_parent_summary", "summary is missing", parent_id)
    else:
        hierarchy_summary = summary.get("hierarchy")
        recorded_negative = summary.get("negative_oracles")
        if not isinstance(hierarchy_summary, Mapping) or not isinstance(recorded_negative, Mapping):
            _finding(findings, "old_parent_summary", "hierarchy or negative_oracles is missing", parent_id)
        else:
            if hierarchy_summary.get("parent_model_id") != parent_id or hierarchy_summary.get("ok") is not True or hierarchy_summary.get("findings") != []:
                _finding(findings, "old_parent_summary", hierarchy_summary, parent_id)
            if dict(recorded_negative) != dict(negative):
                _finding(findings, "old_parent_summary", {"recorded": recorded_negative, "observed": negative}, parent_id)
    expected_descendants = _descendants(parent_id, mesh.CHILDREN)
    if tuple(parent.get("child_model_ids", ())) != children:
        _finding(findings, "old_parent_summary", "direct child identity or order is stale", parent_id)
    if tuple(parent.get("descendant_model_ids", ())) != expected_descendants:
        _finding(findings, "old_parent_summary", "descendant identity or order is stale", parent_id)
    _subtree(parent, parent_id, children, expected_descendants, payloads, authority_head, findings)


def run_check(root: Path) -> dict[str, Any]:
    root = root.resolve()
    findings: list[dict[str, str]] = []
    required = (
        root / "skills" / "logic-writing" / "SKILL.md",
        root / "skills" / "logic-writing" / ".skillguard" / "contract-source.json",
        root / ".flowguard" / "models" / "owners",
        root / ".flowguard" / "verification" / "owners",
    )
    if any(not path.exists() for path in required):
        _finding(findings, "wrong_repository_or_source", [str(path) for path in required if not path.exists()])
    checker_path = Path(__file__).resolve()
    try:
        mesh = _mesh(root)
    except Exception as exc:
        _finding(findings, "current_model_mesh_unavailable", f"{type(exc).__name__}: {exc}")
        return {
            "schema_version": SCHEMA_VERSION,
            "source_fingerprint": _fingerprint({"checker": _sha(checker_path) if checker_path.is_file() else "missing"}),
            "model_revision_set_id": "",
            "checked_model_ids": [],
            "consumed_receipt_refs": [],
            "findings": findings,
            "status": "blocked",
        }
    actual_ids = set(mesh.MODEL_PATHS)
    if actual_ids != set(EXPECTED_MODEL_IDS):
        _finding(findings, "current_model_topology_mismatch", {"missing": sorted(set(EXPECTED_MODEL_IDS) - actual_ids), "unexpected": sorted(actual_ids - set(EXPECTED_MODEL_IDS))})
    inventory = _source_inventory(root, mesh, checker_path, findings)
    state, revision_id, authority_head = _authority(root, findings)
    _snapshot(root, mesh, state, findings)
    payloads: dict[str, Mapping[str, Any]] = {}
    consumed: list[dict[str, str]] = []
    receipt_root = root / ".flowguard" / "evidence" / "model-mesh" / "current"
    for model_id in EXPECTED_MODEL_IDS:
        try:
            payload = mesh.load_child_receipt(model_id, root)
        except Exception as exc:
            _finding(findings, "current_owner_receipt_unavailable", f"{type(exc).__name__}: {exc}", model_id)
            continue
        payloads[model_id] = payload
        native = payload.get("native_case")
        consumed.append({
            "model_id": model_id,
            "receipt_id": str(payload.get("receipt_id", "")),
            "receipt_path": _relative(receipt_root / f"{model_id}.json", root),
            "receipt_fingerprint": str(payload.get("receipt_fingerprint", "")),
            "native_case_path": str(native.get("path", "")) if isinstance(native, Mapping) else "",
            "native_case_fingerprint": str(native.get("fingerprint", "")) if isinstance(native, Mapping) else "",
        })
        expected_parent = mesh.PARENTS.get(model_id, "")
        if payload.get("parent_model_id", "") != expected_parent:
            _finding(findings, "owner_receipt_parent_mismatch", {"actual": payload.get("parent_model_id"), "expected": expected_parent}, model_id)
        if payload.get("owner_id") != f"owner:{model_id}":
            _finding(findings, "owner_receipt_owner_mismatch", payload.get("owner_id"), model_id)
        if payload.get("status") not in {"pass", "pass_with_gaps"}:
            _finding(findings, "owner_receipt_not_terminal_pass", payload.get("status"), model_id)
        try:
            if payload.get("model_fingerprint") != _source_sha(root / mesh.MODEL_PATHS[model_id]):
                _finding(findings, "owner_receipt_model_stale", model_id=model_id)
            if not mesh._current_hashes_match(payload, root):
                _finding(findings, "owner_receipt_source_stale", model_id=model_id)
        except Exception as exc:
            _finding(findings, "owner_receipt_source_unavailable", f"{type(exc).__name__}: {exc}", model_id)
        required_evidence = {f"native:{model_id}:current", f"negative:{model_id}:matrix"}
        if not required_evidence <= set(payload.get("validation_evidence", ())):
            _finding(findings, "owner_receipt_evidence_incomplete", sorted(required_evidence - set(payload.get("validation_evidence", ()))), model_id)
        if payload.get("skipped_checks") or payload.get("not_run_checks"):
            _finding(findings, "owner_receipt_has_unrun_checks", model_id=model_id)
        _native(root, mesh, model_id, payload, findings)
    for parent_id in sorted(mesh.CHILDREN):
        _parent_review(root, mesh, parent_id, payloads, authority_head, findings)
    findings.sort(key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True))
    return {
        "schema_version": SCHEMA_VERSION,
        "source_fingerprint": _fingerprint(inventory),
        "model_revision_set_id": revision_id,
        "checked_model_ids": list(EXPECTED_MODEL_IDS),
        "consumed_receipt_refs": sorted(consumed, key=lambda row: row["model_id"]),
        "findings": findings,
        "status": "pass" if not findings else "blocked",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run_check(args.root)
    except Exception as exc:
        result = {
            "schema_version": SCHEMA_VERSION,
            "source_fingerprint": "",
            "model_revision_set_id": "",
            "checked_model_ids": [],
            "consumed_receipt_refs": [],
            "findings": [{"code": "model_depth_check_error", "detail": f"{type(exc).__name__}: {exc}"}],
            "status": "blocked",
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
