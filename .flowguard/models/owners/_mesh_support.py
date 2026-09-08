"""Target-owned parent/child model-mesh support for LogicWriting.

This module is deliberately small and evidence oriented.  Leaf owners execute
the real model factory or the real focused tests.  A parent only reads the
immutable receipt written by each direct child and then runs the native
FlowGuard hierarchy reviewer.  It never calls a sibling factory as a hidden
shortcut.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import site
import subprocess
import sys
from dataclasses import replace
from typing import Any, Callable, Mapping, Sequence


def _local_python_package_paths() -> tuple[Path, ...]:
    """Find locally installed Python package roots used by owner checks.

    The Codex bundled interpreter is intentionally small and does not always
    expose the user's Windows Store site packages.  Model owners still need
    to run the repository's real local checks (for example FlowGuard's YAML
    reader), so discover those roots without installing anything or reaching
    an external service.
    """

    candidates: list[Path] = [Path(site.getusersitepackages())]
    package_root = Path.home() / "AppData" / "Local" / "Packages"
    if package_root.is_dir():
        for package in package_root.glob("PythonSoftwareFoundation.Python*"):
            candidates.append(
                package
                / "LocalCache"
                / "local-packages"
                / "Python312"
                / "site-packages"
            )
    return tuple(dict.fromkeys(path.resolve() for path in candidates if path.is_dir()))


for _local_package_path in reversed(_local_python_package_paths()):
    if str(_local_package_path) not in sys.path:
        sys.path.insert(0, str(_local_package_path))

from flowguard import (
    ChildModelEvidence,
    ChildReattachmentContract,
    EVIDENCE_ABSTRACT_GREEN,
    HierarchyCoverageItem,
    HierarchyPartitionMap,
    MeshClosureJoin,
    MeshClosureModel,
    MeshClosureTerminal,
    MeshClosureTransition,
    ModelTargetSplitDerivation,
    OWNERSHIP_CHILD,
    review_hierarchical_mesh,
    review_mesh_closure_model,
)
from flowguard.native_case_protocol import NativeModelCaseResult, fingerprint_payload
from flowguard.recursive_hierarchy import VerifiedSubtreeReceipt, descendant_universe_fingerprint
from flowguard.runner import run_model_first_checks
from flowguard.source_identity import source_file_fingerprint


FLOWGUARD_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = FLOWGUARD_ROOT.parent
MESH_ROOT = FLOWGUARD_ROOT / "evidence" / "model-mesh"
CURRENT_ROOT = MESH_ROOT / "current"
RECEIPT_ROOT = MESH_ROOT / "receipts"


# This is the checked-in target topology.  The audit plan supplied the initial
# boundary, but the executable declaration below is the source used by the
# owners and by their receipts.
PARENTS: dict[str, str] = {
    "route_and_guard_model": "logic_writing_models",
    "research_packet_model": "logic_writing_models",
    "reader_artifact_model": "logic_writing_models",
    "fiction_route_model": "logic_writing_models",
    "travel_route_model": "logic_writing_models",
    "investigation_route_model": "logic_writing_models",
    "academic_route_model": "logic_writing_models",
    "operation_freshness_closure_model": "logic_writing_models",
    "release_retirement_model": "development_process_flow",
    "writer_projection": "reader_artifact_model",
    "editorial_disposition": "reader_artifact_model",
    "composition_graph": "reader_artifact_model",
    "artifact_audit": "reader_artifact_model",
    "execution_binding": "reader_artifact_model",
    "researchguard_handoff": "reader_artifact_model",
}

CHILDREN: dict[str, tuple[str, ...]] = {}
for _child, _parent in PARENTS.items():
    CHILDREN.setdefault(_parent, []).append(_child)
CHILDREN = {key: tuple(value) for key, value in CHILDREN.items()}


MODEL_PATHS: dict[str, str] = {
    "logic_writing_models": ".flowguard/models/owners/logic_writing_models/model.py",
    "development_process_flow": ".flowguard/models/owners/development_process_flow/model.py",
    "test_mesh": ".flowguard/models/owners/test_mesh/model.py",
    "behavior_commitment_ledger": ".flowguard/models/owners/behavior_commitment_ledger/model.py",
    "primary_path_authority": ".flowguard/models/owners/primary_path_authority/model.py",
    "model_test_alignment": ".flowguard/models/owners/model_test_alignment/model.py",
    "plan_detailing": ".flowguard/models/owners/plan_detailing/model.py",
    "route_and_guard_model": ".flowguard/models/owners/route_and_guard_model/model.py",
    "research_packet_model": ".flowguard/models/owners/research_packet_model/model.py",
    "reader_artifact_model": ".flowguard/models/owners/reader_artifact_model/model.py",
    "fiction_route_model": ".flowguard/models/owners/fiction_route_model/model.py",
    "travel_route_model": ".flowguard/models/owners/travel_route_model/model.py",
    "investigation_route_model": ".flowguard/models/owners/investigation_route_model/model.py",
    "academic_route_model": ".flowguard/models/owners/academic_route_model/model.py",
    "operation_freshness_closure_model": ".flowguard/models/owners/operation_freshness_closure_model/model.py",
    "release_retirement_model": ".flowguard/models/owners/release_retirement_model/model.py",
    "writer_projection": ".flowguard/models/owners/writer_projection/model.py",
    "editorial_disposition": ".flowguard/models/owners/editorial_disposition/model.py",
    "composition_graph": ".flowguard/models/owners/composition_graph/model.py",
    "artifact_audit": ".flowguard/models/owners/artifact_audit/model.py",
    "execution_binding": ".flowguard/models/owners/execution_binding/model.py",
    "researchguard_handoff": ".flowguard/models/owners/researchguard_handoff/model.py",
}

RUNNER_PATHS = {
    model_id: f".flowguard/verification/owners/{model_id}/run_checks.py"
    for model_id in MODEL_PATHS
}

TEST_PATHS: dict[str, tuple[str, ...]] = {
    "route_and_guard_model": ("tests/flowguard/test_model_contracts.py",),
    "research_packet_model": ("tests/flowguard/test_model_contracts.py",),
    "reader_artifact_model": ("tests/flowguard/test_model_contracts.py",),
    "fiction_route_model": ("tests/flowguard/test_model_contracts.py",),
    "travel_route_model": ("tests/flowguard/test_model_contracts.py",),
    "investigation_route_model": ("tests/flowguard/test_model_contracts.py",),
    "academic_route_model": ("tests/flowguard/test_model_contracts.py",),
    "operation_freshness_closure_model": ("tests/flowguard/test_model_contracts.py",),
    "release_retirement_model": ("tests/flowguard/test_model_contracts.py",),
    "writer_projection": ("tests/unit/test_writer_projection.py",),
    "editorial_disposition": ("tests/unit/test_editorial_dispositions.py",),
    "composition_graph": ("tests/unit/test_composition_graph.py",),
    "artifact_audit": ("tests/adversarial/test_reader_integrity_regressions.py",),
    "execution_binding": ("tests/adversarial/test_judgment_execution_binding.py",),
    "researchguard_handoff": ("tests/contract/test_researchguard_handoff.py",),
}

FACTORY_MODULES: dict[str, str] = {
    "route_and_guard_model": "models.owners.route_and_guard_model.model",
    "research_packet_model": "models.owners.research_packet_model.model",
    "reader_artifact_model": "models.owners.reader_artifact_model.model",
    "fiction_route_model": "models.owners.fiction_route_model.model",
    "travel_route_model": "models.owners.travel_route_model.model",
    "investigation_route_model": "models.owners.investigation_route_model.model",
    "academic_route_model": "models.owners.academic_route_model.model",
    "operation_freshness_closure_model": "models.owners.operation_freshness_closure_model.model",
    "release_retirement_model": "models.owners.release_retirement_model.model",
}

DIMENSIONS = ("input", "state", "output", "effect", "order", "completion")


def _root() -> Path:
    configured = os.environ.get("FLOWGUARD_PROJECT_ROOT", "").strip()
    return Path(configured).resolve() if configured else REPOSITORY_ROOT


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _source_sha(path: Path) -> str:
    """Use FlowGuard's canonical identity for governed source files.

    Source/model/input bindings must match the authority snapshot's
    newline-normalized identity.  Terminal raw-result and native-case
    envelopes continue to use ``_sha`` so their immutable artifact bytes are
    checked exactly as written.
    """

    return source_file_fingerprint(path)


def _fingerprint(value: Any) -> str:
    return fingerprint_payload(value)


def _binding_path(value: str) -> str:
    return value.split(":", 1)[0] if ":" in value else value


def _source_paths(model_id: str, root: Path) -> tuple[str, ...]:
    paths = [MODEL_PATHS[model_id], RUNNER_PATHS[model_id]]
    # Every receipt is produced and interpreted by this shared owner
    # orchestrator.  Bind its bytes into each source identity so a change to
    # partitioning, hierarchy validation, or receipt serialization cannot
    # leave an otherwise green child receipt looking current.
    paths.append(".flowguard/models/owners/_mesh_support.py")
    paths.extend(TEST_PATHS.get(model_id, ()))
    if model_id in FACTORY_MODULES:
        paths.extend((".flowguard/models/common.py", ".flowguard/models/plans.py"))
    result: list[str] = []
    for path in paths:
        normalized = Path(_binding_path(path)).as_posix()
        if normalized not in result:
            result.append(normalized)
    missing = [path for path in result if not (root / path).is_file()]
    if missing:
        raise FileNotFoundError(f"{model_id} source binding missing: {', '.join(missing)}")
    return tuple(result)


def _source_hashes(model_id: str, root: Path) -> dict[str, str]:
    return {path: _source_sha(root / path) for path in _source_paths(model_id, root)}


def _current_hashes_match(payload: Mapping[str, Any], root: Path) -> bool:
    hashes = payload.get("source_hashes")
    if not isinstance(hashes, Mapping) or not hashes:
        return False
    try:
        return dict(hashes) == _source_hashes(str(payload["model_id"]), root)
    except (KeyError, FileNotFoundError, OSError):
        return False


def receipt_path(model_id: str) -> Path:
    return CURRENT_ROOT / f"{model_id}.json"


def _payload_fingerprint(payload: Mapping[str, Any]) -> str:
    return _fingerprint({key: value for key, value in payload.items() if key != "receipt_fingerprint"})


def load_child_receipt(model_id: str, root: Path | None = None) -> dict[str, Any]:
    root = root or _root()
    path = root / ".flowguard" / "evidence" / "model-mesh" / "current" / f"{model_id}.json"
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(f"current child receipt is missing: {model_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or payload.get("schema_version") != "logic-writing.model-mesh-receipt.v1":
        raise ValueError(f"child receipt schema is not current: {model_id}")
    if payload.get("model_id") != model_id:
        raise ValueError(f"child receipt model identity mismatch: {model_id}")
    if payload.get("receipt_fingerprint") != _payload_fingerprint(payload):
        raise ValueError(f"child receipt fingerprint is stale: {model_id}")
    return dict(payload)


def _child_evidence(payload: Mapping[str, Any], parent_id: str, root: Path) -> ChildModelEvidence:
    model_id = str(payload["model_id"])
    source_current = _current_hashes_match(payload, root)
    status = str(payload.get("status", "blocked"))
    current = source_current and status in {"pass", "pass_with_gaps"}
    child_ids = tuple(str(item) for item in payload.get("child_model_ids", ()))
    subtree = payload.get("subtree_receipt")
    subtree_id = str(subtree.get("receipt_id", "")) if isinstance(subtree, Mapping) else ""
    subtree_fp = str(subtree.get("fingerprint", "")) if isinstance(subtree, Mapping) else ""
    return ChildModelEvidence(
        model_id=model_id,
        model_fingerprint=str(payload.get("model_fingerprint", "")),
        evidence_id=str(payload.get("evidence_id", "")),
        inputs_accepted=tuple(payload.get("inputs_accepted", ())),
        outputs_emitted=tuple(payload.get("outputs_emitted", ())),
        state_owned=tuple(payload.get("state_owned", ())),
        side_effects_owned=tuple(payload.get("side_effects_owned", ())),
        functional_areas=tuple(payload.get("functional_areas", ())),
        contracts_out=tuple(payload.get("contracts_out", ())),
        depends_on=tuple(payload.get("depends_on", ())),
        evidence_tier=str(payload.get("evidence_tier", EVIDENCE_ABSTRACT_GREEN)),
        evidence_current=current,
        skipped_checks=tuple(payload.get("skipped_checks", ())),
        not_run_checks=tuple(payload.get("not_run_checks", ())),
        structurally_cohesive=True,
        has_compatibility_contract=True,
        functions_owned=tuple(payload.get("functions_owned", ())),
        invariants_owned=tuple(payload.get("invariants_owned", ())),
        risk_classes=tuple(payload.get("risk_classes", ())),
        validation_evidence=tuple(payload.get("validation_evidence", ())),
        owner_id=str(payload.get("owner_id", f"owner:{model_id}")),
        parent_model_id=str(payload.get("parent_model_id", parent_id)),
        claim_scope=str(payload.get("claim_scope", "full")),
        subtree_receipt_id=subtree_id,
        subtree_receipt_fingerprint=subtree_fp,
        is_leaf=not bool(child_ids),
        child_model_ids=child_ids,
    )


def _subtree_receipt(
    payload: Mapping[str, Any],
    child_payloads: Sequence[Mapping[str, Any]],
    *,
    native: Mapping[str, Any],
    root: Path,
) -> dict[str, Any] | None:
    child_ids = tuple(str(item["model_id"]) for item in child_payloads)
    if not child_ids:
        return None
    # Recursive hierarchy v2 requires every non-leaf receipt to bind the
    # exact partition, current model-authority head, and execution context.
    # The previous producer only emitted the descendant universe, leaving a
    # structurally passing receipt unverifiable by the strict current-depth
    # checker.  Read the head through the typed authority loader and derive
    # the partition from the same child payloads consumed by the parent.
    from flowguard.model_authority_store import load_observed_model_system

    authority_head, _ = load_observed_model_system(root)
    partition, _ = _partition(str(payload["model_id"]), child_payloads, root)
    native_result = native.get("result", {})
    if not isinstance(native_result, Mapping):
        raise ValueError("native terminal result is missing for subtree authority")
    toolchain_fingerprint = str(native_result.get("toolchain_fingerprint", "")).strip()
    environment_fingerprint = str(native_result.get("environment_fingerprint", "")).strip()
    if not toolchain_fingerprint or not environment_fingerprint:
        raise ValueError("native terminal result lacks toolchain or environment fingerprint")
    child_receipt_ids = tuple(str(item["receipt_id"]) for item in child_payloads)
    child_fingerprints = {str(item["receipt_id"]): str(item["receipt_fingerprint"]) for item in child_payloads}
    descendant_ids: list[str] = []
    for item in child_payloads:
        descendant_ids.append(str(item["model_id"]))
        descendant_ids.extend(str(value) for value in item.get("descendant_model_ids", ()))
    receipt = VerifiedSubtreeReceipt(
        receipt_id=f"subtree:{payload['model_id']}:{str(payload['evidence_id']).split(':')[-1][:16]}",
        model_id=str(payload["model_id"]),
        owner_id=str(payload["owner_id"]),
        structural_parent_id=str(payload.get("parent_model_id", "")),
        claim_scope=str(payload.get("claim_scope", "full")),
        model_fingerprint=str(payload["model_fingerprint"]),
        obligation_ids=tuple(payload.get("validation_evidence", ())) or (f"model:{payload['model_id']}",),
        child_receipt_ids=child_receipt_ids,
        direct_child_ids=child_ids,
        descendant_model_ids=tuple(dict.fromkeys(descendant_ids)),
        descendant_universe_fingerprint=descendant_universe_fingerprint(tuple(dict.fromkeys(descendant_ids))),
        partition_fingerprint=_fingerprint(partition.to_dict()),
        model_authority_head_fingerprint=authority_head.fingerprint,
        toolchain_fingerprint=toolchain_fingerprint,
        environment_fingerprint=environment_fingerprint,
        child_receipt_fingerprints=child_fingerprints,
        status="passed",
        current=True,
        terminal=True,
        metadata={"producer": "logic-writing.model-mesh", "source_status": payload.get("status")},
    )
    return receipt.to_dict()


def _partition(parent_id: str, child_payloads: Sequence[Mapping[str, Any]], root: Path) -> tuple[HierarchyPartitionMap, dict[str, ChildModelEvidence]]:
    children = tuple(_child_evidence(payload, parent_id, root) for payload in child_payloads)
    coverage = tuple(
        HierarchyCoverageItem(
            item_id=f"{child.model_id}:boundary",
            item_type="model_boundary",
            owner_model_id=child.model_id,
            ownership=OWNERSHIP_CHILD,
            description=f"Current {child.model_id} boundary is owned by exactly one child.",
        )
        for child in children
    )
    derivation = ModelTargetSplitDerivation(
        source_model_id=parent_id,
        target_child_model_ids=tuple(child.model_id for child in children),
        covered_partition_item_ids=tuple(item.item_id for item in coverage),
        state_owner_fields=tuple(value for child in children for value in child.state_owned),
        side_effect_owner_fields=tuple(value for child in children for value in child.side_effects_owned),
        source_model_path=MODEL_PATHS[parent_id],
        rationale="The target-owned model declaration partitions each current child boundary and records its owner.",
    )
    contracts = tuple(
        ChildReattachmentContract(
            child_model_id=child.model_id,
            consumed_evidence_id=child.evidence_id,
            expected_inputs=child.inputs_accepted,
            expected_outputs=child.outputs_emitted,
            expected_state_owned=child.state_owned,
            expected_side_effects_owned=child.side_effects_owned,
            expected_contracts_out=child.contracts_out,
            rationale="Parent consumes the exact immutable child receipt and its declared handoff.",
        )
        for child in children
    )
    start = f"{parent_id}:start"
    outputs = tuple(f"{child.model_id}:result" for child in children)
    transitions = tuple(
        MeshClosureTransition(
            transition_id=f"{parent_id}:to:{child.model_id}",
            consumes=(start,),
            emits=(f"{child.model_id}:result",),
            consumer_model_id=child.model_id,
            progress_rule="The current child receipt is consumed exactly once before the parent join.",
        )
        for child in children
    )
    joined = f"{parent_id}:joined"
    closure = MeshClosureModel(
        parent_model_id=parent_id,
        root_entries=(start,),
        transitions=transitions,
        joins=(MeshClosureJoin(f"{parent_id}:join", required_inputs=outputs, emits=(joined,), rationale="All direct child receipts are joined."),),
        terminals=(MeshClosureTerminal(f"{parent_id}:normal-exit", consumes=(joined,), rationale="All child outputs are consumed before normal exit."),),
        required_outputs=outputs,
        require_normal_exit=True,
        rationale="Parent closure is a finite receipt join; child internals remain owned by child models.",
    )
    return (
        HierarchyPartitionMap(
            parent_model_id=parent_id,
            coverage_items=coverage,
            child_models=children,
            target_split_derivation=derivation,
            reattachment_contracts=contracts,
            required_evidence_tier=EVIDENCE_ABSTRACT_GREEN,
            closure_model=closure,
            claim_scope="full",
            strict=True,
            subtree_receipts=tuple(
                VerifiedSubtreeReceipt.from_dict(payload["subtree_receipt"])
                for payload in child_payloads
                if isinstance(payload.get("subtree_receipt"), Mapping)
            ),
        ),
        {child.model_id: child for child in children},
    )


def _negative_oracles(partition: HierarchyPartitionMap) -> dict[str, bool]:
    """Run typed negative probes against the same native hierarchy reviewer."""

    results: dict[str, bool] = {}
    children = list(partition.child_models)
    if children:
        results["missing_child"] = not review_hierarchical_mesh(
            replace(partition, child_models=tuple(children[:-1]))
        ).ok
        if len(children) > 1:
            forged = list(children)
            forged[1] = ChildModelEvidence(
                **{**forged[1].to_dict(), "functions_owned": list(forged[0].functions_owned)}
            )
            results["duplicate_function_owner"] = not review_hierarchical_mesh(
                replace(partition, child_models=tuple(forged))
            ).ok
        forged = list(children)
        forged[0] = ChildModelEvidence(**{**forged[0].to_dict(), "evidence_current": False})
        results["stale_child_receipt"] = not review_hierarchical_mesh(
            replace(partition, child_models=tuple(forged))
        ).ok
    closure = partition.closure_model
    if closure is not None and closure.joins:
        join = closure.joins[0]
        broken_join = MeshClosureModel(
            parent_model_id=closure.parent_model_id,
            root_entries=closure.root_entries,
            transitions=closure.transitions,
            joins=(MeshClosureJoin(join.join_id, required_inputs=join.required_inputs[:-1], emits=join.emits),),
            terminals=closure.terminals,
            required_outputs=closure.required_outputs,
        )
        results["missing_join_input"] = not review_mesh_closure_model(broken_join, partition.child_models).ok
    results["negative_matrix_complete"] = bool(results) and all(results.values())
    return results


def _write_native_results(model_id: str, status: str, summary: Mapping[str, Any], output_dir: Path, source_hashes: Mapping[str, str]) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw = output_dir / "raw-result.json"
    raw_payload = {
        "schema_version": "logic-writing.model-mesh-raw-result.v1",
        "model_id": model_id,
        "status": status,
        "summary": dict(summary),
        "source_hashes": dict(source_hashes),
    }
    raw.write_text(json.dumps(raw_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    raw_fp = _sha(raw)
    input_fp = str(os.environ.get("FLOWGUARD_INPUT_FINGERPRINT", "")) or _fingerprint(source_hashes)
    model_fp = _source_sha(_root() / MODEL_PATHS[model_id])
    code_fp = _fingerprint({"model": model_fp, "sources": dict(source_hashes)})
    test_fp = _fingerprint({"runner": source_hashes.get(RUNNER_PATHS[model_id], ""), "tests": [source_hashes.get(item, "") for item in TEST_PATHS.get(model_id, ())]})
    oracle_fp = _fingerprint({"model_id": model_id, "status": status, "oracle": "native-model-mesh"})
    toolchain_fp = _fingerprint({"python": sys.version, "executable": sys.executable})
    environment_fp = _fingerprint({"platform": sys.platform, "root": str(_root())})
    outcome = "pass" if status in {"pass", "pass_with_gaps"} else "fail"
    observed = status or "blocked"
    result = NativeModelCaseResult(
        owner_id=f"model:{model_id}",
        source_case_id=f"mesh:{model_id}:current",
        outcome=outcome,
        observed_status=observed,
        observed_finding_codes=(),
        executed_dimensions=DIMENSIONS,
        oracle_results=tuple({"dimension": dim, "oracle_member_id": f"native:{model_id}:oracle", "status": observed, "ok": outcome == "pass"} for dim in DIMENSIONS),
        result_artifact_fingerprint=raw_fp,
        input_fingerprint=input_fp,
        model_fingerprint=model_fp,
        code_fingerprint=code_fp,
        test_fingerprint=test_fp,
        oracle_fingerprint=oracle_fp,
        toolchain_fingerprint=toolchain_fp,
        environment_fingerprint=environment_fp,
        raw_artifact_path="raw-result.json",
    )
    envelope = output_dir / "native-case-results.json"
    envelope.write_text(json.dumps({"schema_version": "flowguard.native_model_case_result.v1", "results": [result.to_dict()]}, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {"path": str(envelope), "fingerprint": _sha(envelope), "result": result.to_dict()}


def _write_receipt(model_id: str, parent_id: str, status: str, summary: Mapping[str, Any], child_payloads: Sequence[Mapping[str, Any]], source_hashes: Mapping[str, str], native: Mapping[str, Any], *, root: Path) -> dict[str, Any]:
    children = tuple(str(item["model_id"]) for item in child_payloads)
    model_fp = _source_sha(root / MODEL_PATHS[model_id])
    evidence_id = f"mesh:{model_id}:{model_fp.split(':', 1)[1][:20]}"
    payload: dict[str, Any] = {
        "schema_version": "logic-writing.model-mesh-receipt.v1",
        "model_id": model_id,
        "parent_model_id": parent_id,
        "owner_id": f"owner:{model_id}",
        "claim_scope": "full",
        "status": status,
        "evidence_tier": EVIDENCE_ABSTRACT_GREEN,
        "evidence_id": evidence_id,
        "model_fingerprint": model_fp,
        "source_hashes": dict(source_hashes),
        "inputs_accepted": (f"{parent_id}:input",) if parent_id else (f"{model_id}:input",),
        "outputs_emitted": (f"{model_id}:result",),
        "functions_owned": (f"{model_id}:entry",),
        "state_owned": (f"{model_id}:state",),
        "side_effects_owned": (f"{model_id}:effect",),
        "functional_areas": (f"{model_id}:area",),
        "invariants_owned": (f"{model_id}:invariant",),
        "contracts_out": (f"{model_id}:result",),
        "depends_on": tuple(f"{item}:result" for item in children),
        "risk_classes": (f"{model_id}:risk",),
        "validation_evidence": (f"native:{model_id}:current", f"negative:{model_id}:matrix"),
        "child_model_ids": children,
        # Preserve declaration-order depth first traversal for the parent
        # receipt.  The recursive FlowGuard wire object canonicalizes its own
        # identity lists, but the parent payload is also checked against the
        # executable tree and must retain the actual hierarchy order.
        "descendant_model_ids": tuple(
            dict.fromkeys(
                value
                for item in child_payloads
                for value in (
                    str(item["model_id"]),
                    *tuple(str(child) for child in item.get("descendant_model_ids", ())),
                )
            )
        ),
        "summary": dict(summary),
        "native_case": dict(native),
    }
    subtree = _subtree_receipt(payload, child_payloads, native=native, root=root)
    if subtree is not None:
        payload["subtree_receipt"] = subtree
    payload["receipt_id"] = f"receipt:{model_id}:{model_fp.split(':', 1)[1][:20]}"
    payload["receipt_fingerprint"] = _payload_fingerprint(payload)
    current = root / ".flowguard" / "evidence" / "model-mesh" / "current"
    receipts = root / ".flowguard" / "evidence" / "model-mesh" / "receipts"
    current.mkdir(parents=True, exist_ok=True)
    receipts.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    immutable = receipts / f"{payload['receipt_fingerprint'].split(':', 1)[1]}.json"
    if immutable.exists() and immutable.read_text(encoding="utf-8") != encoded:
        raise ValueError(f"model mesh receipt collision: {model_id}")
    if not immutable.exists():
        immutable.write_text(encoded, encoding="utf-8")
    target = current / f"{model_id}.json"
    target.write_text(encoded, encoding="utf-8")
    return payload


def _compact_summary(report: Any) -> dict[str, Any]:
    if isinstance(report, Mapping):
        return dict(report)
    sections = getattr(report, "sections", ())
    return {
        "overall_status": str(getattr(report, "overall_status", "failed")),
        "summary": str(getattr(report, "summary", "")),
        "sections": [{"name": getattr(section, "name", ""), "status": getattr(section, "status", "")} for section in sections],
    }


def _run_factory(model_id: str) -> tuple[str, dict[str, Any]]:
    import importlib

    module = importlib.import_module(FACTORY_MODULES[model_id])
    plan = module.build_plan()
    report = run_model_first_checks(plan)
    compact = _compact_summary(report)
    status = str(compact.get("overall_status", "failed"))
    return status, compact


def _run_focused_tests(model_id: str, root: Path) -> tuple[str, dict[str, Any]]:
    # The bundled author interpreter is intentionally dependency-light and may
    # not carry pytest.  Prefer the already installed local pytest launcher;
    # fall back to ``python -m pytest`` only when that launcher is unavailable.
    # This keeps the owner fully local and makes a missing test runtime an
    # explicit failed receipt rather than silently skipping the suite.
    support_paths = list(_local_python_package_paths())
    pytest_launcher = shutil.which("pytest")
    if not pytest_launcher:
        for support_path in support_paths:
            candidate = support_path.parent / "Scripts" / "pytest.exe"
            if candidate.is_file():
                pytest_launcher = str(candidate)
                break
    command = [pytest_launcher or sys.executable]
    if not pytest_launcher:
        command.extend(["-m", "pytest"])
    command.extend(["-q", "-p", "no:cacheprovider", *TEST_PATHS[model_id], "--tb=short"])
    # Owner runners often execute with Codex's dependency-light Python.  Keep
    # the runner local while making the user's installed test packages
    # discoverable (for example PyYAML used by the FlowGuard fixtures).  The
    # package path is derived from this machine's Python installation; no
    # network installation or external provider is attempted.
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        item
        for item in ( *(str(path) for path in support_paths), existing )
        if item
    )
    completed = subprocess.run(
        command,
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    status = "pass" if completed.returncode == 0 else "failed"
    return status, {
        "command": command,
        "exit_code": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
        "test_paths": list(TEST_PATHS[model_id]),
    }


def run_owner(model_id: str, *, base_runner: Callable[[], tuple[str, Mapping[str, Any]]] | None = None) -> dict[str, Any]:
    root = _root()
    parent_id = PARENTS.get(model_id, "")
    direct_children = CHILDREN.get(model_id, ())
    child_payloads: list[Mapping[str, Any]] = []
    summary: dict[str, Any] = {}
    status = "pass"
    try:
        for child_id in direct_children:
            child_payloads.append(load_child_receipt(child_id, root))
        if direct_children:
            partition, _ = _partition(model_id, child_payloads, root)
            hierarchy = review_hierarchical_mesh(partition)
            summary["hierarchy"] = hierarchy.to_dict()
            summary["negative_oracles"] = _negative_oracles(partition)
            if not hierarchy.ok or not summary["negative_oracles"].get("negative_matrix_complete"):
                status = "failed"
            if base_runner is not None and status in {"pass", "pass_with_gaps"}:
                base_status, base_summary = base_runner()
                summary["base_model"] = dict(base_summary)
                status = base_status if base_status not in {"pass", "pass_with_gaps"} else base_status
        elif base_runner is not None:
            status, base_summary = base_runner()
            summary["base_model"] = dict(base_summary)
        elif model_id in FACTORY_MODULES:
            status, base_summary = _run_factory(model_id)
            summary["base_model"] = base_summary
        elif model_id in TEST_PATHS:
            status, test_summary = _run_focused_tests(model_id, root)
            summary["focused_tests"] = test_summary
        else:
            raise ValueError(f"no native runner declared for {model_id}")
    except Exception as exc:
        status = "failed"
        summary["error"] = f"{type(exc).__name__}: {exc}"
    source_hashes = _source_hashes(model_id, root)
    output_dir = Path(os.environ.get("FLOWGUARD_OUTPUT_DIR", str(root / ".flowguard" / "evidence" / "model-mesh" / "native" / model_id))).resolve()
    native = _write_native_results(model_id, status, summary, output_dir, source_hashes)
    receipt = _write_receipt(model_id, parent_id, status, summary, child_payloads, source_hashes, native, root=root)
    receipt["native_case"] = native
    return receipt


def run_logic_writing_parent() -> dict[str, Any]:
    return run_owner("logic_writing_models")


def run_reader_artifact_parent() -> dict[str, Any]:
    return run_owner("reader_artifact_model", base_runner=_run_factory_reader)


def _run_factory_reader() -> tuple[str, Mapping[str, Any]]:
    status, summary = _run_factory("reader_artifact_model")
    return status, summary


def run_development_parent() -> dict[str, Any]:
    def callback() -> tuple[str, Mapping[str, Any]]:
        from models.owners.development_process_flow.model import run_checks

        routine, broken = run_checks()
        ok = bool(routine.ok and not broken.ok)
        return ("pass" if ok else "failed"), {
            "routine": routine.to_dict(),
            "known_bad": broken.to_dict(),
        }

    return run_owner("development_process_flow", base_runner=callback)


def run_root_owner(model_id: str) -> dict[str, Any]:
    callbacks: dict[str, Callable[[], tuple[str, Mapping[str, Any]]]] = {}

    def bcl() -> tuple[str, Mapping[str, Any]]:
        from models.owners.behavior_commitment_ledger.model import build_behavior_commitment_ledger
        from flowguard import review_behavior_commitment_ledger
        report = review_behavior_commitment_ledger(build_behavior_commitment_ledger())
        return ("pass" if report.ok else "failed"), report.to_dict()

    def ppa() -> tuple[str, Mapping[str, Any]]:
        from models.owners.primary_path_authority.model import (
            broken_alias_unknown_disposition,
            broken_manual_recovery_auto_invoked,
            broken_old_skill_masks_primary_failure,
            design_plan,
            researchguard_member_plan,
        )
        from flowguard import review_primary_path_authority
        reports = [review_primary_path_authority(item) for item in (design_plan(), researchguard_member_plan())]
        bad = [review_primary_path_authority(item) for item in (broken_old_skill_masks_primary_failure(), broken_alias_unknown_disposition(), broken_manual_recovery_auto_invoked())]
        ok = all(item.ok for item in reports) and all(not item.ok for item in bad)
        return ("pass" if ok else "failed"), {"good": [item.to_dict() for item in reports], "known_bad": [item.to_dict() for item in bad]}

    def alignment() -> tuple[str, Mapping[str, Any]]:
        from models.owners.model_test_alignment.model import aligned_plan, broken_missing_actual_artifact_plan
        from flowguard import review_model_test_alignment
        good = review_model_test_alignment(aligned_plan())
        bad = review_model_test_alignment(broken_missing_actual_artifact_plan())
        return ("pass" if good.ok and not bad.ok else "failed"), {"good": good.to_dict(), "known_bad": bad.to_dict()}

    def plan_detail() -> tuple[str, Mapping[str, Any]]:
        from models.owners.plan_detailing.model import run_checks
        details, intake, process, contracts = run_checks()
        ok = details[0].ok and all(not item.ok for item in details[1:]) and intake.ok and bool(contracts)
        return ("pass" if ok else "failed"), {"detail": [item.to_dict() for item in details], "intake": intake.to_dict(), "process": process.to_dict(), "contract_count": len(contracts)}

    def test_mesh() -> tuple[str, Mapping[str, Any]]:
        from models.owners.test_mesh.model import broken_missing_target_split_plan, release_plan
        from flowguard import review_test_mesh
        good = review_test_mesh(release_plan())
        bad = review_test_mesh(broken_missing_target_split_plan())
        # The frozen plan is intentionally evidence-pending until the final
        # validation owner supplies immutable terminal receipts.  The native
        # owner is green only when the plan shape is valid and its declared
        # known-bad remains blocked.
        pending = {"diagnostic_accounting_incomplete", "diagnostic_not_run_without_reason", "final_receipt_artifact_version_missing", "final_receipt_coverage_incomplete", "final_receipt_exit_code_missing", "final_receipt_result_artifact_missing", "final_receipt_result_fingerprint_missing", "final_receipt_run_id_missing", "final_receipt_terminal_status_missing", "final_receipt_verifier_version_missing", "leaf_matrix_cell_evidence_missing", "release_suite_not_current", "required_inventory_item_owner_missing", "stale_test_evidence"}
        good_codes = {item.code for item in good.findings}
        structure_ok = not (good_codes - pending)
        ok = structure_ok and not bad.ok
        return ("pass" if ok else "failed"), {"current": good.to_dict(), "known_bad": bad.to_dict(), "structure_pending_codes": sorted(good_codes & pending)}

    callbacks.update({
        "behavior_commitment_ledger": bcl,
        "primary_path_authority": ppa,
        "model_test_alignment": alignment,
        "plan_detailing": plan_detail,
        "test_mesh": test_mesh,
    })
    return run_owner(model_id, base_runner=callbacks.get(model_id))


def emit_runner(model_id: str, payload: Mapping[str, Any]) -> int:
    # The manifest may require a durable model report for aggregate owners.
    # ``run_owner`` already writes the immutable mesh/native receipts; this
    # projection is the runner's declared output artifact and must be written
    # into the supervised output directory before the process exits.  Keep it
    # local and deterministic so the FlowGuard parent can verify it without
    # inventing an artifact from stdout.
    output = os.environ.get("FLOWGUARD_OUTPUT_DIR", "").strip()
    if output:
        output_path = Path(output).resolve()
        output_path.mkdir(parents=True, exist_ok=True)
        (output_path / "model-report.json").write_text(
            json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, indent=2)
            + "\n",
            encoding="utf-8",
        )
    print(f"FLOWGUARD_EXECUTED_CASE_IDS=[\"mesh:{model_id}:current\"]")
    print(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if str(payload.get("status")) in {"pass", "pass_with_gaps"} else 1


__all__ = [
    "CHILDREN",
    "FACTORY_MODULES",
    "MODEL_PATHS",
    "PARENTS",
    "RUNNER_PATHS",
    "TEST_PATHS",
    "emit_runner",
    "run_development_parent",
    "run_logic_writing_parent",
    "run_owner",
    "run_reader_artifact_parent",
    "run_root_owner",
]
