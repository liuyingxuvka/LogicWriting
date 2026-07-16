from __future__ import annotations

import hashlib
from pathlib import Path

from _common import fingerprint_without
from validate_shared_writing import validate_shared_writing


def _contract(path: Path, *, owner: str = "fiction-writing") -> dict:
    text = path.read_text(encoding="utf-8")
    value = {
        "schema_version": "1.0",
        "contract_id": "contract:shared-reader",
        "final_owner": owner,
        "artifact_path": str(path),
        "artifact_fingerprint": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        "audience": "A reader who knows the premise but not the consequence",
        "purpose": "Make the decisive change understandable through concrete action",
        "incoming_reader_state": "The reader knows the promise but not its cost",
        "artifact_form": "chapter",
        "units": [
            {
                "unit_id": "unit:one",
                "important": True,
                "contribution": "The promise acquires a visible cost",
                "incoming_reader_state": "The promise still looks easy",
                "outgoing_reader_state": "The reader sees that keeping it will cost trust",
                "unresolved_or_terminal": "Whether Mara will pay that cost remains open",
                "downstream_consumer": "unit:two tests Mara's willingness to lose Tomas's trust",
                "register_owner": "Mara owns the clipped first-person wording",
                "variation_effect": "The first instance establishes the cost",
                "model_row_ids": ["row:promise-cost"],
                "artifact_span": text,
            }
        ],
        "route_extension": {
            "owner": owner,
            "profile": "fiction" if owner == "fiction-writing" else "travel",
            "required_surface_ids": ["surface:route-native"],
        },
    }
    value["contract_fingerprint"] = fingerprint_without(value, "contract_fingerprint")
    return value


def test_current_artifact_with_concrete_handoff_and_binding_passes(tmp_path: Path):
    path = tmp_path / "chapter.md"
    path.write_text("Mara signed the pledge, and Tomas quietly took back his key.", encoding="utf-8")

    result = validate_shared_writing(_contract(path))

    assert result["status"] == "current_pass"
    assert result["findings"] == []


def test_material_byte_change_stales_binding(tmp_path: Path):
    path = tmp_path / "chapter.md"
    path.write_text("Mara signed the pledge, and Tomas quietly took back his key.", encoding="utf-8")
    contract = _contract(path)
    path.write_text(path.read_text(encoding="utf-8") + "\nThe key returned.", encoding="utf-8")

    result = validate_shared_writing(contract)

    assert "stale_artifact" in {row["code"] for row in result["findings"]}


def test_generic_handoff_and_unbound_prose_fail(tmp_path: Path):
    path = tmp_path / "guide.md"
    path.write_text("Rain closes the ridge path after noon.", encoding="utf-8")
    contract = _contract(path, owner="travel-guide")
    contract["units"][0]["downstream_consumer"] = "sets up the next section"
    contract["units"][0]["model_row_ids"] = []
    contract["contract_fingerprint"] = fingerprint_without(contract, "contract_fingerprint")

    result = validate_shared_writing(contract)

    assert result["status"] == "failed"
    assert {row["code"] for row in result["findings"]} >= {"generic_handoff", "unbound_prose"}


def test_route_extension_cannot_belong_to_sibling(tmp_path: Path):
    path = tmp_path / "itinerary.md"
    path.write_text("Take the covered ferry at 09:10; the exposed trail is the rain fallback.", encoding="utf-8")
    contract = _contract(path, owner="travel-guide")
    contract["route_extension"]["owner"] = "fiction-writing"
    contract["contract_fingerprint"] = fingerprint_without(contract, "contract_fingerprint")

    result = validate_shared_writing(contract)

    assert "foreign_route_extension" in {row["code"] for row in result["findings"]}
