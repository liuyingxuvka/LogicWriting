"""Issue managed authority for one exact ReaderBrief v2 composition packet."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from _common import (
    ValidationError,
    fingerprint,
    fingerprint_without,
    require_mapping,
    require_schema,
)
from build_source_unit_manifest import fingerprint_bytes
from receipt_authority import _commit_managed_receipt, _store_content_object


def build_reader_brief_receipt(
    *,
    reader_brief: Mapping[str, Any],
    route_content_projection_fingerprint: str,
    dependency_receipt_fingerprints: list[str],
    root: str | Path,
    run_id: str | None = None,
    sequence_id: str | None = None,
) -> dict[str, Any]:
    brief = require_mapping(reader_brief, "ReaderBrief")
    require_schema("reader-brief.schema.json", brief, label="ReaderBrief")
    if brief["brief_fingerprint"] != fingerprint_without(brief, "brief_fingerprint"):
        raise ValidationError("ReaderBrief fingerprint does not bind exact current content")
    if not isinstance(route_content_projection_fingerprint, str) or not route_content_projection_fingerprint.startswith("sha256:"):
        raise ValidationError("route_content_projection_fingerprint must be sha256")
    dependencies = list(dict.fromkeys(dependency_receipt_fingerprints))
    if dependencies != brief["native_dependency_receipt_fingerprints"]:
        raise ValidationError("ReaderBrief receipt dependencies do not match the brief")
    builder_source = fingerprint_bytes(Path(__file__).with_name("build_reader_brief.py").read_bytes())
    brief_object = _store_content_object(brief, root=root)
    plan_object = _store_content_object(brief["composition_plan"], root=root)
    brief_id = brief["brief_id"]
    actual_run_id = run_id or f"reader-brief:{brief_id}"
    actual_sequence_id = sequence_id or actual_run_id
    input_fingerprints = {
        f"reader-brief:{brief_id}:route-decision": brief["route_decision_fingerprint"],
        f"reader-brief:{brief_id}:reader-intent": brief["reader_intent_fingerprint"],
        f"reader-brief:{brief_id}:route-content": route_content_projection_fingerprint,
        f"reader-brief:{brief_id}:composition-plan": brief["composition_plan"]["plan_fingerprint"],
        f"reader-brief:{brief_id}:route-extension": brief["route_extension"]["extension_fingerprint"],
        f"reader-brief:{brief_id}:builder": builder_source,
    }
    return _commit_managed_receipt(
        {
            "schema_version": "2.0",
            "producer_skill": "logic-writing",
            "semantic_owner_id": f"reader-brief:{brief_id}",
            "native_route": "build-reader-brief",
            "run_id": actual_run_id,
            "covered_obligation_ids": [
                "reader.intent.preserved",
                "reader.composition.complete",
                "reader.brief.authoritative",
            ],
            "input_fingerprints": input_fingerprints,
            "output_fingerprints": {
                "reader_brief": brief["brief_fingerprint"],
                "reader_brief_object": brief_object,
                "composition_plan": brief["composition_plan"]["plan_fingerprint"],
                "composition_plan_object": plan_object,
            },
            "artifact_fingerprint": brief["brief_fingerprint"],
            "covered_scope": "the exact RouteDecision, ReaderIntent, route content, route extension, whole-artifact plan, dependencies, builder, and ReaderBrief",
            "evidence_domain": "reader_brief",
            "status": "current_pass",
            "safe_claim": "This ReaderBrief binds the current user delivery contract, route content boundaries, and whole-artifact composition plan.",
            "unsafe_claim_boundary": "The receipt does not prove that the final artifact has been written, integrated, audited, or judged.",
            "sequence_id": actual_sequence_id,
            "dependency_receipt_fingerprints": dependencies,
        },
        root=root,
        builder_id="logic-writing.reader-brief.v2",
        source_fingerprint=fingerprint(input_fingerprints),
    )


__all__ = ["build_reader_brief_receipt"]
