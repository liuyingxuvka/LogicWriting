"""Project-owned root contract for LogicWriting's 22-model mesh.

The shared FlowGuard manifest builder has a generic lexical fallback when a
project does not expose a named authoritative-model-system instance.  This
module keeps LogicWriting's root choice in the project source and applies it
to the typed native snapshot returned by FlowGuard.  It never edits shared
FlowGuard code and never manufactures a receipt.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import Any

# Capture the shared builder before the project authority adapter temporarily
# replaces the module-level export with this target-owned builder.  The target
# builder must keep calling this original typed implementation; resolving the
# import again while the adapter is active would call itself recursively.
from flowguard.model_system_inventory import (
    build_manifest_model_system_snapshot as _GENERIC_BUILD_MANIFEST_MODEL_SYSTEM_SNAPSHOT,
)


ROOT_CONTRACT_RELATIVE_PATH = Path(
    "scripts/author/logic_writing_model_root_contract.json"
)
ROOT_CONTRACT_SCHEMA = "logic-writing.model-root-contract.v1"
LOGIC_WRITING_MODEL_IDS = (
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


@dataclass(frozen=True)
class LogicWritingModelRootContract:
    schema_version: str
    system_id: str
    root_model_id: str
    expected_model_ids: tuple[str, ...]
    claim_boundary: str

    @property
    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "claim_boundary": self.claim_boundary,
            "expected_model_ids": list(self.expected_model_ids),
            "root_model_id": self.root_model_id,
            "schema_version": self.schema_version,
            "system_id": self.system_id,
        }


def load_logic_writing_model_root_contract(
    root: str | Path,
    *,
    expected_model_ids: tuple[str, ...] | None = None,
) -> LogicWritingModelRootContract:
    """Load and validate the project-owned root declaration."""

    path = Path(root).resolve() / ROOT_CONTRACT_RELATIVE_PATH
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"missing or symlinked root contract: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("root contract must be a JSON object")
    required = {
        "claim_boundary",
        "expected_model_ids",
        "root_model_id",
        "schema_version",
        "system_id",
    }
    if set(value) != required:
        raise ValueError(
            "root contract fields must be exactly "
            + ", ".join(sorted(required))
        )
    ids = tuple(str(item) for item in value["expected_model_ids"])
    contract = LogicWritingModelRootContract(
        schema_version=str(value["schema_version"]),
        system_id=str(value["system_id"]),
        root_model_id=str(value["root_model_id"]),
        expected_model_ids=ids,
        claim_boundary=str(value["claim_boundary"]),
    )
    if contract.schema_version != ROOT_CONTRACT_SCHEMA:
        raise ValueError(
            f"root contract schema must be {ROOT_CONTRACT_SCHEMA}"
        )
    if contract.system_id != "logic-writing":
        raise ValueError("root contract system_id must be logic-writing")
    if contract.root_model_id != "logic_writing_models":
        raise ValueError(
            "root contract root_model_id must be logic_writing_models"
        )
    if not contract.root_model_id:
        raise ValueError("root contract root_model_id must be non-empty")
    if len(ids) != len(set(ids)):
        raise ValueError("root contract model ids must be unique")
    if contract.root_model_id not in ids:
        raise ValueError("root contract root model must be in expected_model_ids")
    if expected_model_ids is not None and ids != tuple(expected_model_ids):
        raise ValueError("root contract model denominator is stale")
    if len(contract.claim_boundary) < 40:
        raise ValueError("root contract claim_boundary is too short")
    return contract


def build_logic_writing_model_snapshot(
    root: str | Path,
    *,
    snapshot_id: str,
    system_id: str = "logic-writing",
    subject_lane: str = "observed_implementation",
    lifecycle: str = "active",
    subject_revision: str = "",
    accepted_boundary_contract: Any = None,
):
    """Build a native snapshot with the declared project root.

    The generic builder remains the sole producer of model instances,
    relations, coverage, and owner references.  ``dataclasses.replace`` only
    applies the project-owned root selection to that typed result so the
    resulting snapshot is still validated and fingerprinted by FlowGuard.
    """

    contract = load_logic_writing_model_root_contract(
        root,
        expected_model_ids=LOGIC_WRITING_MODEL_IDS,
    )
    if system_id != contract.system_id:
        raise ValueError("snapshot system_id does not match root contract")
    generic = _GENERIC_BUILD_MANIFEST_MODEL_SYSTEM_SNAPSHOT(
        root,
        snapshot_id=snapshot_id,
        system_id=system_id,
        subject_lane=subject_lane,
        lifecycle=lifecycle,
        subject_revision=subject_revision,
        accepted_boundary_contract=accepted_boundary_contract,
    )
    by_id = {
        str(item.logical_model_id): item for item in generic.model_instances
    }
    if set(by_id) != set(contract.expected_model_ids):
        raise ValueError("native candidate model denominator disagrees with root contract")
    target = by_id.get(contract.root_model_id)
    if target is None:
        raise ValueError("native candidate is missing the project root model")
    return replace(
        generic,
        root_instance_fingerprints=(target.fingerprint,),
    )


__all__ = [
    "ROOT_CONTRACT_RELATIVE_PATH",
    "ROOT_CONTRACT_SCHEMA",
    "LOGIC_WRITING_MODEL_IDS",
    "LogicWritingModelRootContract",
    "build_logic_writing_model_snapshot",
    "load_logic_writing_model_root_contract",
]
