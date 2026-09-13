"""Run native model-authority operations with LogicWriting's root contract.

The shared FlowGuard builders remain responsible for all model, relation,
coverage, revision, receipt, and activation validation.  This target-owned
adapter changes only the root selection supplied to those builders.  It is
kept explicit so an authority refresh cannot silently fall back to the
lexically first model.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from logic_writing_model_root import build_logic_writing_model_snapshot


@contextmanager
def logic_writing_root_builder(
    *,
    force_current_subject_revision: bool = False,
) -> Iterator[None]:
    """Temporarily bind every imported native builder to the project root.

    FlowGuard imports its inventory builder in a few native modules.  The
    context patches those module-local references for one operation and
    restores them even when validation fails.  No shared file is changed.
    """

    import flowguard.model_authority_store as authority_store
    import flowguard.model_revision_builder as revision_builder
    import flowguard.model_revision_owner_evidence as owner_evidence
    import flowguard.model_revision_plan as revision_plan
    import flowguard.model_system_inventory as inventory
    import flowguard.self_path_quality as self_path_quality

    target = build_logic_writing_model_snapshot
    if force_current_subject_revision:
        # ``model_revision_owner_evidence`` builds its frozen candidate without
        # an explicit subject revision, which makes the native builder derive
        # the current source-inventory identity.  The generic revision builder
        # passes the observed (possibly older) subject revision explicitly.
        # Both operations must therefore use the same candidate identity or
        # their otherwise valid receipts cannot be composed.  Keep this
        # normalization local to the target adapter; it does not change the
        # shared FlowGuard builder or create a compatibility path.
        def target(
            root: str | Path,
            *,
            snapshot_id: str,
            system_id: str = "logic-writing",
            subject_lane: str = "observed_implementation",
            lifecycle: str = "active",
            subject_revision: str = "",
            accepted_boundary_contract: Any = None,
        ):
            return build_logic_writing_model_snapshot(
                root,
                snapshot_id=snapshot_id,
                system_id=system_id,
                subject_lane=subject_lane,
                lifecycle=lifecycle,
                subject_revision="",
                accepted_boundary_contract=accepted_boundary_contract,
            )
    refs: list[tuple[Any, str, Any]] = [
        (inventory, "build_manifest_model_system_snapshot", inventory.build_manifest_model_system_snapshot),
        (revision_builder, "build_manifest_model_system_snapshot", revision_builder.build_manifest_model_system_snapshot),
        (owner_evidence, "build_manifest_model_system_snapshot", owner_evidence.build_manifest_model_system_snapshot),
        (revision_plan, "build_manifest_model_system_snapshot", revision_plan.build_manifest_model_system_snapshot),
        (self_path_quality, "build_manifest_model_system_snapshot", self_path_quality.build_manifest_model_system_snapshot),
    ]
    for module, name, original in refs:
        setattr(module, name, target)
    try:
        yield
    finally:
        for module, name, original in refs:
            setattr(module, name, original)


def build_current_logic_writing_model_revision(
    root: str | Path,
    **kwargs: Any,
):
    """Build a typed current revision through FlowGuard's native builder."""

    import flowguard.model_revision_builder as revision_builder

    with logic_writing_root_builder(force_current_subject_revision=True):
        return revision_builder.build_current_model_revision(root, **kwargs)


def produce_current_logic_writing_owner_evidence(
    root: str | Path,
    **kwargs: Any,
):
    """Produce typed owner evidence against the project-root candidate."""

    import flowguard.model_revision_owner_evidence as owner_evidence

    with logic_writing_root_builder():
        return owner_evidence.produce_model_revision_owner_evidence(
            root,
            **kwargs,
        )


def activate_current_logic_writing_revision(
    root: str | Path,
    *,
    candidate_snapshot: Any,
    revision_set: Any,
    receipt_id: str,
):
    """Activate a typed project-root revision through the native store."""

    import flowguard.model_authority_store as authority_store

    with logic_writing_root_builder():
        return authority_store.activate_model_revision_set(
            root,
            candidate_snapshot,
            revision_set,
            receipt_id=receipt_id,
        )


def audit_current_logic_writing_model_authority(root: str | Path):
    """Audit current authority with LogicWriting's declared model root.

    The shared FlowGuard CLI intentionally uses its generic root selection.
    LogicWriting has a project-owned root contract, so its audit must run
    through the same adapter used for revision and activation.  Keeping this
    wrapper here makes the project-specific command fail closed instead of
    reporting a false stale-snapshot finding for the generic lexical root.
    """

    import flowguard.model_authority_store as authority_store

    with logic_writing_root_builder():
        return authority_store.audit_model_authority(root)


__all__ = [
    "audit_current_logic_writing_model_authority",
    "activate_current_logic_writing_revision",
    "build_current_logic_writing_model_revision",
    "logic_writing_root_builder",
    "produce_current_logic_writing_owner_evidence",
]
