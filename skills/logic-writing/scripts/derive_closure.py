"""Derive final closure from one current FlowGuard obligation contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from _common import (
    ValidationError,
    dump_json,
    fingerprint,
    fingerprint_without,
    load_json,
    require_mapping,
    require_schema,
    require_string,
    validation_result,
)
from build_obligation_manifest import build_obligation_manifest
from build_source_unit_manifest import fingerprint_bytes
from receipt_authority import (
    _commit_managed_receipt,
    _store_content_object,
    resolve_content_object,
    resolve_current_receipt,
    resolve_latest_receipt_by_owner,
)


REQUEST_FIELDS = {"contract_receipt_fingerprint"}
HARD_BLOCK = {
    "blocked",
    "failed",
    "provider_unavailable",
    "dependency_unavailable",
    "not_run",
    "stale",
}
DOWNGRADED = {
    "downgraded",
    "bounded",
    "access_gap",
    "planning_only",
    "saved_but_modeling_incomplete",
}
NEXT_OWNERS = {
    "investigation",
    "academic-writing",
    "sourceguard",
    "logicguard",
    "traceguard",
    "flowguard",
    "documents",
    "pdf",
    "source_access",
    "human_review",
    "user",
}
ACTIONS = {
    "rerun",
    "rerun_or_human_review",
    "repair",
    "downgrade",
    "omit",
    "request_access",
    "human_review",
    "declare_required_obligations",
    "provide_input",
}
BROAD_BASELINE_DOMAINS = {
    "investigation": {
        "source_observation",
        "source_depth",
        "argument_model",
        "reader_brief",
        "reader_deterministic",
        "reader_judgment",
    },
    "academic-writing": {
        "source_observation",
        "argument_model",
        "structured_artifact",
        "model_depth",
        "artifact_synthesis",
        "citation_semantics",
        "revision_provenance",
        "reader_brief",
        "reader_deterministic",
        "reader_judgment",
    },
}
FINAL_BASELINE_DOMAINS = {
    "investigation": {
        "source_observation",
        "argument_model",
        "reader_brief",
        "reader_deterministic",
        "reader_judgment",
    },
    "academic-writing": {
        "argument_model",
        "revision_provenance",
        "reader_brief",
        "reader_deterministic",
        "reader_judgment",
    },
}
DOMAIN_OWNER = {
    "source_observation": "sourceguard",
    "source_depth": "sourceguard",
    "argument_model": "logicguard",
    "structured_artifact": "logicguard",
    "model_depth": "logicguard",
    "artifact_synthesis": "logicguard",
    "citation_semantics": "logicguard",
    "revision_provenance": "academic-writing",
    "reader_brief": "academic-writing",
    "reader_deterministic": "academic-writing",
    "reader_judgment": "human_review",
}


def _required_subset(required: Mapping[str, str], actual: Mapping[str, str]) -> bool:
    return all(actual.get(key) == value for key, value in required.items())


def _residual(
    obligation: Mapping[str, Any],
    status: str,
) -> dict[str, Any]:
    next_owner = obligation["next_owner"]
    action = obligation["action"]
    if next_owner not in NEXT_OWNERS or action not in ACTIONS:
        raise ValidationError("obligation next owner or action is unsupported")
    return {
        "obligation_id": obligation["obligation_id"],
        "evidence_domain": obligation["evidence_domain"],
        "status": status,
        "critical": obligation["critical"],
        "affected_scope": obligation["affected_scope"],
        "safe_claim": obligation["safe_claim"],
        "unsafe_claim_boundary": obligation["unsafe_claim_boundary"],
        "next_owner": next_owner,
        "action": action,
    }


def _missing_baseline_residual(
    domain: str,
    final_owner: str,
    *,
    broad_only: bool,
) -> dict[str, Any]:
    next_owner = (
        "human_review"
        if domain == "reader_judgment"
        else final_owner
        if domain in {"reader_brief", "reader_deterministic", "revision_provenance"}
        else DOMAIN_OWNER[domain]
    )
    return {
        "obligation_id": f"{'broad' if broad_only else 'final'}.{domain}",
        "evidence_domain": domain,
        "status": "not_run",
        "critical": True,
        "affected_scope": (
            "the requested broad completion claim"
            if broad_only
            else "the final reader-facing artifact"
        ),
        "safe_claim": (
            "Only the narrower contracted scope can be described."
            if broad_only
            else "The work may be described only as an unfinished internal step."
        ),
        "unsafe_claim_boundary": (
            "Do not claim comprehensive coverage without this evidence domain."
            if broad_only
            else "Do not issue final closure without this content and reader evidence."
        ),
        "next_owner": next_owner,
        "action": "declare_required_obligations",
    }


def _chain_residual(
    *,
    obligation_id: str,
    evidence_domain: str,
    next_owner: str,
    message: str,
) -> dict[str, Any]:
    return {
        "obligation_id": obligation_id,
        "evidence_domain": evidence_domain,
        "status": "blocked",
        "critical": True,
        "affected_scope": "the final artifact evidence chain",
        "safe_claim": message,
        "unsafe_claim_boundary": "Do not issue final closure while the evidence chain refers to different artifacts or reader plans.",
        "next_owner": next_owner,
        "action": "repair",
    }


def _reader_chain_residuals(
    matched: list[dict[str, Any]],
    *,
    receipt_root: str | Path,
) -> list[dict[str, Any]]:
    receipts = [item["receipt"] for item in matched]
    briefs = [item for item in receipts if item["evidence_domain"] == "reader_brief"]
    audits = [
        item for item in receipts if item["evidence_domain"] == "reader_deterministic"
    ]
    judgments = [
        item for item in receipts if item["evidence_domain"] == "reader_judgment"
    ]
    if not any((briefs, audits, judgments)):
        return []
    if len(briefs) != 1 or len(audits) != 1 or len(judgments) != 1:
        return [
            _chain_residual(
                obligation_id="closure.reader-chain.cardinality",
                evidence_domain="reader_judgment",
                next_owner="human_review",
                message="The closure contract does not resolve to one ReaderBrief, one deterministic audit, and one judgment.",
            )
        ]
    brief, audit, judgment = briefs[0], audits[0], judgments[0]
    if brief["receipt_fingerprint"] not in audit["dependency_receipt_fingerprints"]:
        return [
            _chain_residual(
                obligation_id="closure.reader-chain.audit",
                evidence_domain="reader_deterministic",
                next_owner="academic-writing",
                message="The deterministic audit is not bound to the contracted ReaderBrief.",
            )
        ]
    if not {
        brief["receipt_fingerprint"],
        audit["receipt_fingerprint"],
    }.issubset(judgment["dependency_receipt_fingerprints"]):
        return [
            _chain_residual(
                obligation_id="closure.reader-chain.judgment",
                evidence_domain="reader_judgment",
                next_owner="human_review",
                message="The reader judgment is not bound to the same ReaderBrief and deterministic audit.",
            )
        ]
    audit_object = audit["output_fingerprints"].get("reader_audit_object")
    judgment_object = judgment["output_fingerprints"].get("reader_judgment_object")
    if not isinstance(audit_object, str) or not isinstance(judgment_object, str):
        return [
            _chain_residual(
                obligation_id="closure.reader-chain.objects",
                evidence_domain="reader_judgment",
                next_owner="human_review",
                message="The reader checks do not preserve their exact reviewed objects.",
            )
        ]
    audit_value = require_mapping(
        resolve_content_object(audit_object, root=receipt_root), "reader audit"
    )
    judgment_value = require_mapping(
        resolve_content_object(judgment_object, root=receipt_root), "reader judgment"
    )
    if (
        audit_value.get("status") != "passed"
        or judgment_value.get("status") != "passed"
        or audit_value.get("reader_brief_fingerprint")
        != judgment_value.get("reader_brief_fingerprint")
        or audit_value.get("artifact_fingerprint")
        != judgment_value.get("artifact_fingerprint")
    ):
        return [
            _chain_residual(
                obligation_id="closure.reader-chain.content",
                evidence_domain="reader_judgment",
                next_owner="human_review",
                message="The reader checks do not provide a passing judgment for the same artifact and ReaderBrief.",
            )
        ]
    return []


def _provenance_chain_residuals(
    matched: list[dict[str, Any]],
    *,
    receipt_root: str | Path,
) -> list[dict[str, Any]]:
    provenance_receipts = [
        item["receipt"]
        for item in matched
        if item["receipt"]["evidence_domain"] == "revision_provenance"
        and item["receipt"]["builder_provenance"]["builder_id"]
        == "logic-writing.revision-provenance.v1"
    ]
    for provenance in provenance_receipts:
        manifest_found = False
        for dependency in provenance["dependency_receipt_fingerprints"]:
            projection = resolve_current_receipt(dependency, root=receipt_root)
            receipt = projection["receipt"]
            if (
                projection["current"]
                and projection["status"] == "current_pass"
                and receipt["builder_provenance"]["builder_id"]
                == "logic-writing.source-unit-manifest.v1"
                and receipt["output_fingerprints"].get("source_unit_manifest")
                == provenance["output_fingerprints"].get("source_unit_manifest")
            ):
                manifest_found = True
                break
        if not manifest_found:
            return [
                _chain_residual(
                    obligation_id="closure.revision-manifest-chain",
                    evidence_domain="revision_provenance",
                    next_owner="academic-writing",
                    message="Revision provenance is not bound to a current complete source-unit manifest.",
                )
            ]
    return []


def derive_closure(
    value: Mapping[str, Any],
    *,
    receipt_root: str | Path,
) -> dict[str, Any]:
    request = require_mapping(dict(value), "closure request")
    if set(request) != REQUEST_FIELDS:
        raise ValidationError(
            "closure request accepts only contract_receipt_fingerprint"
        )
    contract_fingerprint = require_string(request, "contract_receipt_fingerprint")
    manifest_result = build_obligation_manifest(
        {"contract_receipt_fingerprint": contract_fingerprint},
        root=receipt_root,
    )
    manifest = manifest_result["manifest"]
    final_owner = manifest["final_owner"]
    artifact_fingerprint = manifest["artifact_fingerprint"]
    route_decision = manifest["route_decision"]
    decision_id = route_decision["decision_id"]
    closure_id = f"closure:{decision_id}"

    matched: list[dict[str, Any]] = []
    residuals: list[dict[str, Any]] = []
    projection_rows: list[dict[str, Any]] = []
    for obligation in manifest["obligations"]:
        try:
            projection = resolve_latest_receipt_by_owner(
                producer_skill=obligation["producer_skill"],
                semantic_owner_id=obligation["semantic_owner_id"],
                evidence_domain=obligation["evidence_domain"],
                root=receipt_root,
            )
        except ValidationError as exc:
            if str(exc) != "semantic evidence owner has no authoritative receipt":
                raise
            residuals.append(_residual(obligation, "not_run"))
            continue
        receipt = projection["receipt"]
        projection_rows.append(
            {
                "receipt_fingerprint": projection["receipt_fingerprint"],
                "projection_fingerprint": projection["projection_fingerprint"],
                "current": projection["current"],
                "status": projection["status"],
            }
        )
        exact_contract = (
            receipt["native_route"] == obligation["native_route"]
            and obligation["obligation_id"] in receipt["covered_obligation_ids"]
            and _required_subset(
                obligation["required_input_fingerprints"],
                receipt["input_fingerprints"],
            )
            and _required_subset(
                obligation["required_output_fingerprints"],
                receipt["output_fingerprints"],
            )
        )
        if (
            projection["current"]
            and projection["status"] == "current_pass"
            and exact_contract
        ):
            matched.append(projection)
        else:
            residuals.append(
                _residual(
                    obligation,
                    projection["status"] if exact_contract else "blocked",
                )
            )

    declared_domains = {
        item["evidence_domain"] for item in manifest["obligations"]
    }
    required_domains = set(FINAL_BASELINE_DOMAINS[final_owner])
    if manifest["broad_claim_requested"]:
        required_domains.update(BROAD_BASELINE_DOMAINS[final_owner])
    for domain in sorted(required_domains - declared_domains):
        residuals.append(
            _missing_baseline_residual(
                domain,
                final_owner,
                broad_only=domain not in FINAL_BASELINE_DOMAINS[final_owner],
            )
        )
    residuals.extend(
        _reader_chain_residuals(matched, receipt_root=receipt_root)
    )
    residuals.extend(
        _provenance_chain_residuals(matched, receipt_root=receipt_root)
    )

    if not residuals:
        raw_status = "passed"
    elif any(item["critical"] and item["status"] in HARD_BLOCK for item in residuals):
        raw_status = "blocked"
    elif any(item["status"] in DOWNGRADED for item in residuals):
        raw_status = "downgraded"
    else:
        raw_status = "partial"
    if manifest["broad_claim_requested"] and residuals:
        raw_status = "blocked"

    projection_rows.sort(key=lambda item: item["receipt_fingerprint"])
    contract_projection = resolve_current_receipt(
        contract_fingerprint, root=receipt_root
    )
    authority_projection_fingerprint = fingerprint(
        {
            "contract": contract_projection["projection_fingerprint"],
            "manifest_object": manifest_result["manifest_object_fingerprint"],
            "receipts": projection_rows,
        }
    )
    matched_fingerprints = sorted(
        item["receipt_fingerprint"] for item in matched
    )
    attempt_basis = {
        "obligation_manifest_fingerprint": manifest["manifest_fingerprint"],
        "artifact_fingerprint": artifact_fingerprint,
        "matched_receipt_fingerprints": matched_fingerprints,
        "authority_projection_fingerprint": authority_projection_fingerprint,
        "residual_risk": residuals,
        "raw_status": raw_status,
    }
    attempt_fingerprint = fingerprint(attempt_basis)
    status = raw_status
    semantic_owner_id = f"final-closure:{decision_id}"
    if raw_status != "passed":
        try:
            prior_projection = resolve_latest_receipt_by_owner(
                producer_skill="logic-writing",
                semantic_owner_id=semantic_owner_id,
                evidence_domain="final_closure",
                root=receipt_root,
            )
        except ValidationError as exc:
            if str(exc) != "semantic evidence owner has no authoritative receipt":
                raise
        else:
            prior_object_fingerprint = prior_projection["receipt"][
                "output_fingerprints"
            ].get("final_closure_object")
            if isinstance(prior_object_fingerprint, str):
                prior_closure = require_mapping(
                    resolve_content_object(
                        prior_object_fingerprint, root=receipt_root
                    ),
                    "prior closure",
                )
                if prior_closure.get("attempt_fingerprint") == attempt_fingerprint:
                    status = "no_progress_blocked"

    if residuals:
        safe_claim = " ".join(
            dict.fromkeys(str(item["safe_claim"]) for item in residuals)
        )
        unsafe_claim_boundary = " ".join(
            dict.fromkeys(
                str(item["unsafe_claim_boundary"]) for item in residuals
            )
        )
    else:
        safe_claim = "Every obligation in the current contract passed for this exact artifact and scope."
        unsafe_claim_boundary = "Do not extend this closure beyond the contracted artifact, owners, and evidence boundaries."
    next_actions = [
        {
            "owner": item["next_owner"],
            "action": item["action"],
            "obligation_ids": [item["obligation_id"]],
        }
        for item in residuals
    ]
    closure: dict[str, Any] = {
        "schema_version": "1.0",
        "closure_id": closure_id,
        "final_owner": final_owner,
        "artifact_fingerprint": artifact_fingerprint,
        "obligation_contract_receipt_fingerprint": contract_fingerprint,
        "obligation_manifest_fingerprint": manifest["manifest_fingerprint"],
        "route_decision_fingerprint": route_decision["decision_fingerprint"],
        "status": status,
        "matched_receipt_fingerprints": matched_fingerprints,
        "authority_projection_fingerprint": authority_projection_fingerprint,
        "residual_risk": residuals,
        "safe_claim": safe_claim,
        "unsafe_claim_boundary": unsafe_claim_boundary,
        "next_actions": next_actions,
        "broad_claim_allowed": bool(
            manifest["broad_claim_requested"] and status == "passed"
        ),
        "attempt_fingerprint": attempt_fingerprint,
        "terminal": status in {"passed", "no_progress_blocked"},
    }
    closure["closure_fingerprint"] = fingerprint_without(
        closure, "closure_fingerprint"
    )
    require_schema("closure.schema.json", closure, label="closure")
    closure_object_fingerprint = _store_content_object(
        closure, root=receipt_root
    )
    builder_fingerprint = fingerprint_bytes(Path(__file__).read_bytes())
    receipt_status = {
        "passed": "current_pass",
        "partial": "partial",
        "downgraded": "downgraded",
        "blocked": "blocked",
        "no_progress_blocked": "blocked",
    }[status]
    receipt = _commit_managed_receipt(
        {
            "schema_version": "1.0",
            "producer_skill": "logic-writing",
            "semantic_owner_id": semantic_owner_id,
            "native_route": "derive-final-closure",
            "run_id": closure_id,
            "covered_obligation_ids": ["closure.final"],
            "input_fingerprints": {
                f"final-closure:{decision_id}:contract": contract_fingerprint,
                f"final-closure:{decision_id}:manifest": manifest[
                    "manifest_fingerprint"
                ],
                f"final-closure:{decision_id}:artifact": artifact_fingerprint,
                f"final-closure:{decision_id}:authority": authority_projection_fingerprint,
                f"final-closure:{decision_id}:builder": builder_fingerprint,
            },
            "output_fingerprints": {
                "final_closure": closure["closure_fingerprint"],
                "final_closure_object": closure_object_fingerprint,
            },
            "artifact_fingerprint": artifact_fingerprint,
            "covered_scope": "the exact route decision, obligation manifest, artifact, and latest evidence owners",
            "evidence_domain": "final_closure",
            "status": receipt_status,
            "safe_claim": safe_claim,
            "unsafe_claim_boundary": unsafe_claim_boundary,
            "sequence_id": closure_id,
            "dependency_receipt_fingerprints": [
                contract_fingerprint,
                *matched_fingerprints,
            ],
        },
        root=receipt_root,
        builder_id="logic-writing.final-closure.v1",
        source_fingerprint=fingerprint(
            {
                "closure": closure["closure_fingerprint"],
                "builder": builder_fingerprint,
            }
        ),
    )
    return validation_result(status=status, closure=closure, receipt=receipt)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--receipt-root", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = derive_closure(load_json(args.input), receipt_root=args.receipt_root)
        dump_json(result, args.output)
        return 0 if result["status"] == "passed" else 1
    except (ValidationError, OSError, json.JSONDecodeError) as exc:
        dump_json(validation_result(status="blocked", errors=(str(exc),)), args.output)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["derive_closure"]
