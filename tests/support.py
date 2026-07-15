from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from _common import fingerprint, fingerprint_without
from audit_reader_output import build_reader_audit_receipt
from build_reader_brief import build_reader_brief
from build_source_unit_manifest import (
    build_source_unit_manifest_receipt,
    fingerprint_bytes,
)
from select_route import select_route
from validate_adapter_result import build_adapter_receipt
from validate_judgment_receipt import build_judgment_receipt
from validate_research_packet import assemble_research_packet
from validate_revision_provenance import build_revision_provenance_receipt


SHA_EMPTY = fingerprint({})
SAFE_FINDING = "Average waiting time was lower during the observed intervention period."
LIMITATION = (
    "The available records do not establish that the intervention alone caused the change."
)
UNSAFE_FINDING = "The intervention alone caused the improvement."


def make_adapter_result(
    *,
    owner: str,
    domain: str,
    semantic_owner_id: str,
    native_route: str,
    artifact_fingerprint: str,
    input_fingerprints: Mapping[str, str],
    native_output_fingerprints: Mapping[str, str],
    evidence_payload: Mapping[str, Any],
    covered_obligation_ids: Iterable[str],
    run_id: str | None = None,
    request_id: str | None = None,
    status: str = "current_pass",
    dependencies: Iterable[str] = (),
    artifact_refs: Iterable[str] = (),
    safe_claim: str = "The native result covers only the exact observed artifact and declared scope.",
    unsafe_claim_boundary: str = "Do not extend this result beyond its declared evidence boundary.",
    next_route: str = "none",
) -> dict[str, Any]:
    run_id = run_id or f"run:{owner}:{domain}"
    request_id = request_id or f"request:{owner}:{domain}"
    obligations = list(covered_obligation_ids)
    dependencies = list(dependencies)
    unresolved = (
        []
        if status in {"current_pass", "stale"}
        else ["The native owner did not pass this scope."]
    )
    stale_inputs = ["The observed input identity has changed."] if status == "stale" else []
    native_outputs = dict(native_output_fingerprints)
    payload = {
        "producer_skill": owner,
        "semantic_owner_id": semantic_owner_id,
        "native_route": native_route,
        "run_id": run_id,
        "status": status,
        "covered_obligation_ids": obligations,
        "input_fingerprints": dict(input_fingerprints),
        "output_fingerprints": native_outputs,
        "artifact_fingerprint": artifact_fingerprint,
        "covered_scope": "the exact declared test scope",
        "evidence_domain": domain,
        "safe_claim": safe_claim,
        "unsafe_claim_boundary": unsafe_claim_boundary,
        "next_route": next_route,
        "unresolved_gaps": unresolved,
        "stale_inputs": stale_inputs,
        "dependency_receipt_fingerprints": dependencies,
        "evidence_payload": dict(evidence_payload),
    }
    native_receipt = {
        "receipt_type": f"{owner}.{domain}.v1",
        "schema_version": "1.0",
        "payload": payload,
    }
    native_receipt["fingerprint"] = fingerprint(native_receipt)
    result: dict[str, Any] = {
        "schema_version": "1.0",
        "request_id": request_id,
        "native_owner": owner,
        "semantic_owner_id": semantic_owner_id,
        "native_route": native_route,
        "run_id": run_id,
        "status": status,
        "covered_obligation_ids": obligations,
        "input_fingerprints": dict(input_fingerprints),
        "output_fingerprints": {
            **native_outputs,
            "native_receipt": native_receipt["fingerprint"],
        },
        "artifact_fingerprint": artifact_fingerprint,
        "covered_scope": "the exact declared test scope",
        "evidence_domain": domain,
        "safe_claim": safe_claim,
        "unsafe_claim_boundary": unsafe_claim_boundary,
        "native_receipt": native_receipt,
        "next_route": next_route,
        "artifact_refs": list(artifact_refs),
        "unresolved_gaps": unresolved,
        "stale_inputs": stale_inputs,
        "dependency_receipt_fingerprints": dependencies,
    }
    result["adapter_result_fingerprint"] = fingerprint(result)
    return result


def commit_adapter(root: Path, **kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    result = make_adapter_result(**kwargs)
    return result, build_adapter_receipt(result, root=root)


def make_current_packet(
    root: Path,
    *,
    final_owner: str = "investigation",
    packet_id: str = "packet:clinic-study",
    gap_id: str | None = None,
) -> dict[str, Any]:
    observed_content = b"Clinic records: mean waiting time was lower during the intervention period.\n"
    observed_fingerprint = fingerprint_bytes(observed_content)
    source_basis: dict[str, Any] = {
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
    observation_result, observation_receipt = commit_adapter(
        root,
        owner="sourceguard",
        domain="source_observation",
        semantic_owner_id="source-observation:source:clinic-evaluation",
        native_route="observe-source",
        artifact_fingerprint=observed_fingerprint,
        input_fingerprints={"source:clinic-evaluation:content": observed_fingerprint},
        native_output_fingerprints={"source_observation": fingerprint(source_basis)},
        evidence_payload={"source_record_basis": source_basis},
        covered_obligation_ids=["source.observed"],
    )
    source = {
        **source_basis,
        "observation_receipt_fingerprint": observation_receipt["receipt_fingerprint"],
    }
    registry = {
        "schema_version": "1.0",
        "registry_id": "registry:clinic-study",
        "sources": [source],
    }
    registry_fingerprint = fingerprint(registry)
    claim_basis: dict[str, Any] = {
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
    semantic_fingerprint = fingerprint(claim_basis)
    semantic_result, semantic_receipt = commit_adapter(
        root,
        owner="logicguard",
        domain="argument_model",
        semantic_owner_id="claim-semantic:claim:wait-time",
        native_route="review-claim-semantics",
        artifact_fingerprint=semantic_fingerprint,
        input_fingerprints={
            "source_registry": registry_fingerprint,
            "claim:wait-time:basis": semantic_fingerprint,
        },
        native_output_fingerprints={"claim_semantic_fit": semantic_fingerprint},
        evidence_payload={
            "claim_semantic_basis": claim_basis,
            "source_registry_fingerprint": registry_fingerprint,
        },
        covered_obligation_ids=["claim.semantic-fit"],
        dependencies=[observation_receipt["receipt_fingerprint"]],
    )
    claim = {
        **claim_basis,
        "semantic_fit_receipt_fingerprint": semantic_receipt["receipt_fingerprint"],
    }
    ledger = {
        "schema_version": "1.0",
        "ledger_id": "ledger:clinic-study",
        "source_registry_fingerprint": registry_fingerprint,
        "claims": [claim],
    }
    if final_owner == "academic-writing" and gap_id is None:
        gap_id = "gap:clinic-evidence"
    request: dict[str, Any] = {
        "schema_version": "1.0",
        "packet_id": packet_id,
        "request_fingerprint": fingerprint({"question": "What changed in the clinic?"}),
        "final_owner": final_owner,
        "source_registry": registry,
        "claim_support": ledger,
        "native_receipt_fingerprints": [
            observation_receipt["receipt_fingerprint"],
            semantic_receipt["receipt_fingerprint"],
        ],
        "additional_unresolved_gaps": [],
    }
    if gap_id is not None:
        request["gap_id"] = gap_id
    packet = assemble_research_packet(request, receipt_root=root)
    return {
        "packet": packet,
        "registry": registry,
        "ledger": ledger,
        "source": source,
        "claim": claim,
        "observation_adapter_result": observation_result,
        "observation_receipt": observation_receipt,
        "semantic_adapter_result": semantic_result,
        "semantic_receipt": semantic_receipt,
    }


def rebind_claim_semantics(
    root: Path,
    *,
    claim: dict[str, Any],
    registry: Mapping[str, Any],
    observation_receipt_fingerprint: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    basis = {
        key: value
        for key, value in claim.items()
        if key != "semantic_fit_receipt_fingerprint"
    }
    basis_fingerprint = fingerprint(basis)
    result, receipt = commit_adapter(
        root,
        owner="logicguard",
        domain="argument_model",
        semantic_owner_id=f"claim-semantic:{claim['claim_id']}",
        native_route="review-claim-semantics",
        artifact_fingerprint=basis_fingerprint,
        input_fingerprints={
            "source_registry": fingerprint(registry),
            f"{claim['claim_id']}:basis": basis_fingerprint,
        },
        native_output_fingerprints={"claim_semantic_fit": basis_fingerprint},
        evidence_payload={
            "claim_semantic_basis": basis,
            "source_registry_fingerprint": fingerprint(registry),
        },
        covered_obligation_ids=["claim.semantic-fit"],
        dependencies=[observation_receipt_fingerprint],
        run_id=f"run:claim-semantics:{claim['claim_id']}:{basis_fingerprint[-12:]}",
        request_id=f"request:claim-semantics:{claim['claim_id']}:{basis_fingerprint[-12:]}",
    )
    claim["semantic_fit_receipt_fingerprint"] = receipt["receipt_fingerprint"]
    return result, receipt


def make_reader_chain(
    root: Path,
    workdir: Path,
    *,
    final_owner: str = "investigation",
) -> dict[str, Any]:
    suffix = "academic" if final_owner == "academic-writing" else "investigation"
    packet_chain = make_current_packet(
        root,
        final_owner=final_owner,
        packet_id=f"packet:clinic-study:{suffix}",
    )
    brief_result = build_reader_brief(
        packet_chain["packet"],
        receipt_root=root,
        brief_id=f"brief:clinic-study:{suffix}",
        question="What can the clinic records support?",
        audience="A policy reader without specialist background",
        genre="research report",
        purpose="Explain the observed result and its evidential limit clearly.",
        concepts=[
            {
                "concept_id": "concept:observation-period",
                "term": "Observation period",
                "explanation": "the period covered by the available records",
                "introduction_order": 1,
            }
        ],
    )
    brief = brief_result["reader_brief"]
    marker = brief["required_citations"][0]["marker"]
    limitations = " ".join(item["text"] for item in brief["limitations"])
    artifact_text = (
        "# What the records show\n\n"
        "Observation period means the period covered by the available records. "
        f"{brief['principal_findings'][0]['text']} {marker} {limitations}\n"
    )
    artifact_path = workdir / f"reader-report-{suffix}.md"
    artifact_path.write_text(artifact_text, encoding="utf-8")
    audit_result = build_reader_audit_receipt(
        {
            "schema_version": "1.0",
            "audit_id": f"audit:clinic-study:{suffix}",
            "artifact_path": str(artifact_path),
            "audited_text_path": None,
            "artifact_extraction_receipt_fingerprint": None,
            "reader_brief": brief,
            "reader_brief_receipt_fingerprint": brief_result[
                "derivation_receipt_fingerprint"
            ],
            "run_id": f"run:reader-audit:clinic-study:{suffix}",
        },
        receipt_root=root,
    )
    paragraph_line = 3
    excerpt = brief["principal_findings"][0]["text"]
    rubric = {
        dimension: {
            "score": 4,
            "reason": "The cited sentence is clear, bounded, and appropriate for this reader.",
        }
        for dimension in (
            "clarity",
            "coherence",
            "reader_fit",
            "evidence_fidelity",
            "genre_fit",
        )
    }
    observations = [
        {
            "observation_id": f"observation:{dimension}",
            "dimension": dimension,
            "locator": f"line:{paragraph_line}",
            "excerpt": excerpt,
            "assessment": "The actual sentence states the result and keeps its limitation nearby.",
        }
        for dimension in rubric
    ]
    judgment_result = build_judgment_receipt(
        {
            "schema_version": "1.0",
            "judgment_id": f"judgment:clinic-study:{suffix}",
            "artifact_path": str(artifact_path),
            "reader_brief": brief,
            "reader_brief_receipt_fingerprint": brief_result[
                "derivation_receipt_fingerprint"
            ],
            "deterministic_receipt_fingerprint": audit_result["receipt"][
                "receipt_fingerprint"
            ],
            "judge_id": "judge:reader-review",
            "judge_kind": "model",
            "judged_at": "2026-07-14T12:00:00Z",
            "rubric": rubric,
            "observations": observations,
            "run_id": f"run:reader-judgment:clinic-study:{suffix}",
        },
        receipt_root=root,
    )
    return {
        **packet_chain,
        "brief_result": brief_result,
        "brief": brief,
        "artifact_path": artifact_path,
        "artifact_text": artifact_text,
        "artifact_fingerprint": fingerprint_bytes(artifact_path.read_bytes()),
        "audit_result": audit_result,
        "judgment_result": judgment_result,
    }


def make_revision_chain(root: Path, workdir: Path) -> dict[str, Any]:
    source_path = workdir / "source.md"
    target_path = workdir / "target.md"
    source_path.write_text(
        "# Original finding\n\nThe original paragraph describes the observation imprecisely.\n",
        encoding="utf-8",
    )
    target_path.write_text(
        "# Revised finding\n\nThe revised paragraph states the observation and its limit precisely.\n",
        encoding="utf-8",
    )
    manifest_result = build_source_unit_manifest_receipt(
        manifest_id="manifest:revision-one",
        source_path=source_path,
        target_path=target_path,
        receipt_root=root,
        run_id="run:manifest:revision-one",
    )
    manifest = manifest_result["manifest"]
    revision_id = "revision:one"
    obligation_ids = [
        f"revision:{revision_id}:{unit['unit_id']}" for unit in manifest["source"]["units"]
    ]
    decision_output = fingerprint(
        {
            "source": manifest["source"]["artifact_fingerprint"],
            "target": manifest["target"]["artifact_fingerprint"],
        }
    )
    _adapter, evidence_receipt = commit_adapter(
        root,
        owner="logicguard",
        domain="structured_artifact",
        semantic_owner_id="revision-evidence:revision:one",
        native_route="review-revision-structure",
        artifact_fingerprint=manifest["source"]["artifact_fingerprint"],
        input_fingerprints={
            "revision:one:source": manifest["source"]["artifact_fingerprint"],
            "revision:one:target": manifest["target"]["artifact_fingerprint"],
            "revision:one:manifest": manifest["manifest_fingerprint"],
        },
        native_output_fingerprints={"revision_decision": decision_output},
        evidence_payload={
            "observed_artifact_fingerprint": manifest["source"]["artifact_fingerprint"],
            "validated_output_fingerprints": {"revision_decision": decision_output},
        },
        covered_obligation_ids=obligation_ids,
        dependencies=[manifest_result["receipt"]["receipt_fingerprint"]],
    )
    entries = []
    for source_unit, target_unit in zip(
        manifest["source"]["units"], manifest["target"]["units"], strict=True
    ):
        entries.append(
            {
                "source_unit_id": source_unit["unit_id"],
                "target_unit_id": target_unit["unit_id"],
                "source_locator": source_unit["locator"],
                "target_locator": target_unit["locator"],
                "treatment": "rewritten",
                "reason": "The revised unit states the same purpose more precisely.",
                "evidence_receipt_fingerprints": [
                    evidence_receipt["receipt_fingerprint"]
                ],
                "next_owner": None,
            }
        )
    provenance_result = build_revision_provenance_receipt(
        {
            "schema_version": "1.0",
            "revision_id": revision_id,
            "revision_policy": "clean_rewrite",
            "source_unit_manifest_receipt_fingerprint": manifest_result["receipt"][
                "receipt_fingerprint"
            ],
            "entries": entries,
        },
        source_unit_manifest=manifest,
        source_path=source_path,
        target_path=target_path,
        receipt_root=root,
        run_id="run:provenance:revision-one",
    )
    return {
        "source_path": source_path,
        "target_path": target_path,
        "manifest_result": manifest_result,
        "manifest": manifest,
        "evidence_receipt": evidence_receipt,
        "provenance_result": provenance_result,
    }


def make_obligation(receipt: Mapping[str, Any], *, suffix: str = "") -> dict[str, Any]:
    obligation_id = receipt["covered_obligation_ids"][0]
    return {
        "obligation_id": obligation_id + suffix,
        "producer_skill": receipt["producer_skill"],
        "semantic_owner_id": receipt["semantic_owner_id"],
        "native_route": receipt["native_route"],
        "evidence_domain": receipt["evidence_domain"],
        "required_input_fingerprints": dict(receipt["input_fingerprints"]),
        "required_output_fingerprints": dict(receipt["output_fingerprints"]),
        "critical": True,
        "next_owner": (
            "human_review"
            if receipt["evidence_domain"] == "reader_judgment"
            else "academic-writing"
        ),
        "affected_scope": "the exact contracted artifact and evidence boundary",
        "safe_claim": "Only current evidence for this obligation may support closure.",
        "unsafe_claim_boundary": "Do not claim this obligation passed when its latest owner did not pass.",
        "action": "repair",
    }


def make_closure_contract(
    root: Path,
    receipts: Iterable[Mapping[str, Any]],
    *,
    artifact_fingerprint: str,
    final_owner: str = "investigation",
    broad_claim_requested: bool = False,
    decision_id: str = "decision:closure",
    obligation_rows: list[Mapping[str, Any]] | None = None,
    route_decision_override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if route_decision_override is not None:
        route_decision = dict(route_decision_override)
        final_owner = route_decision["final_owner"]
        decision_id = route_decision["decision_id"]
    else:
        kind = "research_report" if final_owner == "investigation" else "paper"
        route_decision = select_route(
            {
                "request_id": "request:closure",
                "decision_id": decision_id,
                "decided_at": "2026-07-14T12:00:00Z",
                "terminal_deliverable": {
                    "kind": kind,
                    "description": "A final reader-facing artifact",
                    "acceptance_criteria": ["Evidence and prose checks are current."],
                },
                "scope_class": "substantive",
                "substantial_research_required": False,
                "constraints": {},
                "material_assumptions": [],
            }
        )
    obligations = (
        [dict(item) for item in obligation_rows]
        if obligation_rows is not None
        else [make_obligation(receipt) for receipt in receipts]
    )
    payload = {
        "obligations": obligations,
        "broad_claim_requested": broad_claim_requested,
        "route_decision": route_decision,
    }
    native_outputs = {
        "obligation_manifest": fingerprint(obligations),
        "closure_contract": fingerprint(payload),
    }
    adapter_result, contract_receipt = commit_adapter(
        root,
        owner="flowguard",
        domain="process_model",
        semantic_owner_id=f"closure-contract:{decision_id}",
        native_route="closure-obligation-contract",
        artifact_fingerprint=artifact_fingerprint,
        input_fingerprints={
            "route_decision": route_decision["decision_fingerprint"],
            "closure_artifact": artifact_fingerprint,
        },
        native_output_fingerprints=native_outputs,
        evidence_payload=payload,
        covered_obligation_ids=["closure.obligation-contract"],
        run_id=f"run:closure-contract:{decision_id}",
        request_id=f"request:closure-contract:{decision_id}",
    )
    return {
        "route_decision": route_decision,
        "obligations": obligations,
        "adapter_result": adapter_result,
        "contract_receipt": contract_receipt,
    }
