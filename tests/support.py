from __future__ import annotations

from typing import Any
from _common import fingerprint
from build_source_unit_manifest import fingerprint_bytes
from validate_research_packet import assemble_research_packet


SAFE_FINDING = "Average waiting time was lower during the observed intervention period."
LIMITATION = (
    "The available records do not establish that the intervention alone caused the change."
)
UNSAFE_FINDING = "The intervention alone caused the improvement."






def make_current_packet(
    *,
    final_owner: str = "investigation",
    packet_id: str = "packet:clinic-study",
    gap_id: str | None = None,
) -> dict[str, Any]:
    observed_content = b"Clinic records: mean waiting time was lower during the intervention period.\n"
    observed_fingerprint = fingerprint_bytes(observed_content)
    source: dict[str, Any] = {
        "source_id": "source:clinic-evaluation",
        "locator": "https://example.test/clinic-evaluation",
        "citation_label": "Clinic evaluation (2025)",
        "source_date": "2025-01-15",
        "coverage_period": {
            "start": "2024-01-01",
            "end": "2024-12-31",
            "description": "The clinic records cover the 2024 observation period.",
        },
        "role": "outcome",
        "lineage_id": "lineage:clinic-records",
        "independence": "independent",
        "observation_status": "claim_usable",
        "access_status": "available",
        "observed_content_fingerprint": observed_fingerprint,
        "anchors": [
            {
                "anchor_id": "anchor:wait-time",
                "locator": "Results, paragraph 2",
                "observed_summary": SAFE_FINDING,
            }
        ],
        "can_support": [SAFE_FINDING],
        "cannot_support": [LIMITATION],
    }
    registry = {
        "schema_version": "1.0",
        "registry_id": "registry:clinic-study",
        "sources": [source],
    }
    registry_fingerprint = fingerprint(registry)
    claim: dict[str, Any] = {
        "claim_id": "claim:wait-time",
        "text": SAFE_FINDING,
        "claim_type": "fact",
        "critical": True,
        "strength": "supported",
        "reader_order": 1,
        "reader_job": "evidence",
        "reader_disposition": "principal",
        "depends_on_claim_ids": [],
        "source_ids": [source["source_id"]],
        "source_roles": [source["role"]],
        "support_links": [
            {
                "source_id": source["source_id"],
                "anchor_ids": ["anchor:wait-time"],
                "relation": "support",
            }
        ],
        "can_support": [SAFE_FINDING],
        "cannot_support": [LIMITATION],
        "alternatives": [],
        "safe_wording": SAFE_FINDING,
        "unsafe_wording": UNSAFE_FINDING,
        "requires_independent_support": False,
        "mechanism_source_ids": [],
        "forecast_validation_source_ids": [],
    }
    ledger = {
        "schema_version": "1.0",
        "ledger_id": "ledger:clinic-study",
        "source_registry_fingerprint": registry_fingerprint,
        "claims": [claim],
    }
    if final_owner != "investigation" and gap_id is None:
        gap_id = "gap:clinic-evidence"
    request: dict[str, Any] = {
        "schema_version": "1.0",
        "packet_id": packet_id,
        "request_fingerprint": fingerprint({"question": "What changed in the clinic?"}),
        "final_owner": final_owner,
        "source_registry": registry,
        "claim_support": ledger,
        "additional_unresolved_gaps": [],
    }
    if gap_id is not None:
        request["gap_id"] = gap_id
    packet = assemble_research_packet(request)
    return {
        "packet": packet,
        "registry": registry,
        "ledger": ledger,
        "source": source,
        "claim": claim,
    }
