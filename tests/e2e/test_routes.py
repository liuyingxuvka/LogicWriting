from __future__ import annotations

from pathlib import Path

from audit_reader_output import build_reader_audit_receipt
from derive_closure import derive_closure
from receipt_authority import resolve_current_receipt
from select_route import select_route
from tests.support import make_closure_contract, make_reader_chain, make_revision_chain


def _route(*, owner: str, research_child: bool, decision_id: str) -> dict:
    kind = "research_report" if owner == "investigation" else "thesis_chapter"
    return select_route(
        {
            "request_id": f"request:{decision_id}",
            "decision_id": decision_id,
            "decided_at": "2026-07-14T12:00:00Z",
            "terminal_deliverable": {
                "kind": kind,
                "description": "A reader-ready evidence-backed artifact",
                "acceptance_criteria": [
                    "The actual artifact is cited, bounded, readable, and current."
                ],
            },
            "scope_class": "substantive",
            "substantial_research_required": research_child,
            "constraints": {},
            "material_assumptions": [],
        }
    )


def _reader_receipts(chain: dict, receipt_root: Path) -> list[dict]:
    brief = resolve_current_receipt(
        chain["brief_result"]["derivation_receipt_fingerprint"], root=receipt_root
    )["receipt"]
    return [
        chain["observation_receipt"],
        chain["semantic_receipt"],
        brief,
        chain["audit_result"]["receipt"],
        chain["judgment_result"]["receipt"],
    ]


def test_investigation_route_runs_from_question_to_reader_closure(tmp_path: Path):
    receipt_root = tmp_path / "receipts"
    route = _route(
        owner="investigation",
        research_child=False,
        decision_id="decision:e2e-investigation",
    )
    chain = make_reader_chain(receipt_root, tmp_path, final_owner="investigation")
    contract = make_closure_contract(
        receipt_root,
        _reader_receipts(chain, receipt_root),
        artifact_fingerprint=chain["artifact_fingerprint"],
        route_decision_override=route,
    )
    closure = derive_closure(
        {
            "contract_receipt_fingerprint": contract["contract_receipt"][
                "receipt_fingerprint"
            ]
        },
        receipt_root=receipt_root,
    )

    assert route["final_owner"] == "investigation"
    assert route["child_routes"] == []
    assert chain["packet"]["status"] == "current_pass"
    assert chain["brief_result"]["status"] == "current_pass"
    assert chain["audit_result"]["status"] == "current_pass"
    assert chain["judgment_result"]["status"] == "current_pass"
    assert closure["status"] == "passed"
    assert closure["closure"]["route_decision_fingerprint"] == route[
        "decision_fingerprint"
    ]
    assert "FlowGuard" not in chain["artifact_text"]
    assert "route_id" not in chain["artifact_text"]


def test_academic_route_uses_bounded_investigation_child_and_keeps_final_owner(tmp_path: Path):
    receipt_root = tmp_path / "receipts"
    route = _route(
        owner="academic-writing",
        research_child=True,
        decision_id="decision:e2e-academic",
    )
    reader = make_reader_chain(
        receipt_root, tmp_path, final_owner="academic-writing"
    )
    revision = make_revision_chain(receipt_root, tmp_path)
    receipts = [
        *_reader_receipts(reader, receipt_root),
        revision["provenance_result"]["receipt"],
    ]
    contract = make_closure_contract(
        receipt_root,
        receipts,
        artifact_fingerprint=reader["artifact_fingerprint"],
        route_decision_override=route,
    )
    closure = derive_closure(
        {
            "contract_receipt_fingerprint": contract["contract_receipt"][
                "receipt_fingerprint"
            ]
        },
        receipt_root=receipt_root,
    )

    assert route["final_owner"] == "academic-writing"
    assert route["child_routes"] == ["investigation"]
    assert reader["packet"]["final_owner"] == "academic-writing"
    assert reader["packet"]["gap_id"] == "gap:clinic-evidence"
    assert revision["provenance_result"]["status"] == "current_pass"
    assert closure["status"] == "passed"
    assert closure["closure"]["final_owner"] == "academic-writing"


def test_postwrite_material_edit_reopens_the_end_to_end_chain(tmp_path: Path):
    receipt_root = tmp_path / "receipts"
    route = _route(
        owner="investigation",
        research_child=False,
        decision_id="decision:e2e-edit",
    )
    chain = make_reader_chain(receipt_root, tmp_path)
    receipts = _reader_receipts(chain, receipt_root)
    contract = make_closure_contract(
        receipt_root,
        receipts,
        artifact_fingerprint=chain["artifact_fingerprint"],
        route_decision_override=route,
    )
    first = derive_closure(
        {
            "contract_receipt_fingerprint": contract["contract_receipt"][
                "receipt_fingerprint"
            ]
        },
        receipt_root=receipt_root,
    )
    changed = tmp_path / "reader-report-edited.md"
    changed.write_text(
        chain["artifact_text"] + "\nFlowGuard route_id leaked after the final review.\n",
        encoding="utf-8",
    )
    changed_audit = build_reader_audit_receipt(
        {
            "schema_version": "1.0",
            "audit_id": "audit:clinic-study:investigation",
            "artifact_path": str(changed),
            "audited_text_path": None,
            "artifact_extraction_receipt_fingerprint": None,
            "reader_brief": chain["brief"],
            "reader_brief_receipt_fingerprint": chain["brief_result"][
                "derivation_receipt_fingerprint"
            ],
            "run_id": "run:e2e-edited-audit",
        },
        receipt_root=receipt_root,
    )
    reopened = derive_closure(
        {
            "contract_receipt_fingerprint": contract["contract_receipt"][
                "receipt_fingerprint"
            ]
        },
        receipt_root=receipt_root,
    )

    assert first["status"] == "passed"
    assert changed_audit["status"] == "failed"
    assert reopened["status"] == "blocked"
    assert reopened["closure"]["terminal"] is False
