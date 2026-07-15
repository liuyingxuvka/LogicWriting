"""Issue independent authority for one schema-valid, packet-bound ReaderBrief."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from _common import (
    ValidationError,
    fingerprint,
    fingerprint_without,
    require_mapping,
    require_schema,
    require_string,
    require_string_list,
)
from build_source_unit_manifest import fingerprint_bytes
from receipt_authority import _commit_managed_receipt, _store_content_object
def build_reader_brief_receipt(
    *,
    reader_brief: Mapping[str, Any],
    packet_fingerprint: str,
    reader_context_fingerprint: str,
    dependency_receipt_fingerprints: list[str],
    root: str | Path,
    run_id: str | None = None,
    sequence_id: str | None = None,
) -> dict[str, Any]:
    """Validate exact inputs, derive status, and commit a managed ReaderBrief receipt."""

    brief = require_mapping(reader_brief, "ReaderBrief")
    require_schema("reader-brief.schema.json", brief, label="ReaderBrief")
    brief_fingerprint = require_string(brief, "brief_fingerprint")
    if brief_fingerprint != fingerprint_without(brief, "brief_fingerprint"):
        raise ValidationError("ReaderBrief fingerprint does not match exact content")
    if not isinstance(packet_fingerprint, str) or not packet_fingerprint.startswith("sha256:") or len(packet_fingerprint) != 71:
        raise ValidationError("packet_fingerprint must be a sha256 fingerprint")
    if not isinstance(reader_context_fingerprint, str) or not reader_context_fingerprint.startswith("sha256:") or len(reader_context_fingerprint) != 71:
        raise ValidationError("reader_context_fingerprint must be a sha256 fingerprint")
    if brief.get("packet_fingerprint") != packet_fingerprint:
        raise ValidationError("ReaderBrief does not bind the validated ResearchPacket")
    if brief.get("reader_context_fingerprint") != reader_context_fingerprint:
        raise ValidationError("ReaderBrief does not bind the validated reader context")
    native_dependencies = require_string_list(
        dependency_receipt_fingerprints,
        "dependency_receipt_fingerprints",
    )
    if not native_dependencies:
        raise ValidationError("ReaderBrief authority requires current packet dependencies")
    builder_source_fingerprint = fingerprint_bytes(
        (Path(__file__).with_name("build_reader_brief.py")).read_bytes()
    )
    brief_object_fingerprint = _store_content_object(brief, root=root)
    brief_id = require_string(brief, "brief_id")
    run_id = require_string({"run_id": run_id or f"reader-brief:{brief_id}"}, "run_id")
    sequence_id = require_string(
        {"sequence_id": sequence_id or run_id}, "sequence_id"
    )
    return _commit_managed_receipt(
        {
            "schema_version": "1.0",
            "producer_skill": "logic-writing",
            "semantic_owner_id": f"reader-brief:{brief_id}",
            "native_route": "build-reader-brief",
            "run_id": run_id,
            "covered_obligation_ids": ["reader.brief.authoritative"],
            "input_fingerprints": {
                f"reader-brief:{brief_id}:packet": packet_fingerprint,
                f"reader-brief:{brief_id}:context": reader_context_fingerprint,
                f"reader-brief:{brief_id}:builder": builder_source_fingerprint,
            },
            "output_fingerprints": {
                "reader_brief": brief_fingerprint,
                "reader_brief_object": brief_object_fingerprint,
            },
            "artifact_fingerprint": brief_fingerprint,
            "covered_scope": "the exact validated packet, reader context, builder source, and ReaderBrief output",
            "evidence_domain": "reader_brief",
            "status": "current_pass",
            "safe_claim": "This ReaderBrief is bound to its exact current packet and reader context.",
            "unsafe_claim_boundary": "The ReaderBrief receipt does not prove final prose or reader quality.",
            "sequence_id": sequence_id,
            "dependency_receipt_fingerprints": list(dict.fromkeys(native_dependencies)),
        },
        root=root,
        builder_id="logic-writing.reader-brief.v1",
        source_fingerprint=fingerprint(
            {
                "reader_brief": brief_fingerprint,
                "research_packet": packet_fingerprint,
                "reader_context": reader_context_fingerprint,
                "builder_source": builder_source_fingerprint,
            }
        ),
    )


__all__ = ["build_reader_brief_receipt"]
