"""Managed receipt authority and the sole current-receipt resolver.

Receipt JSON is an immutable claim.  It becomes authoritative only when a
managed builder commits the exact original plus a store-owned attestation and
advances the latest pointer for that logical evidence owner.  The public
``resolve_current_receipt`` function is the only receipt resolution path.
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Mapping

from _common import (
    ALL_STATUSES,
    EVIDENCE_DOMAINS,
    ValidationError,
    fingerprint,
    fingerprint_without,
    require_fingerprint,
    require_mapping,
    require_string,
    require_string_list,
)
from schema_validation import assert_schema_valid


AUTHORITY_ENV = "LOGIC_WRITING_RECEIPT_ROOT"
INDEX_VERSION = "1.0"
BUILDER_VERSION = "1.0"
MANAGED_BUILDERS = {
    "logic-writing.adapter-result.v1",
    "logic-writing.source-unit-manifest.v1",
    "logic-writing.revision-provenance.v1",
    "logic-writing.reader-brief.v1",
    "logic-writing.reader-deterministic.v1",
    "logic-writing.reader-judgment.v1",
    "logic-writing.final-closure.v1",
}
RECEIPT_BASE_FIELDS = {
    "schema_version",
    "producer_skill",
    "semantic_owner_id",
    "native_route",
    "run_id",
    "covered_obligation_ids",
    "input_fingerprints",
    "output_fingerprints",
    "artifact_fingerprint",
    "covered_scope",
    "evidence_domain",
    "status",
    "safe_claim",
    "unsafe_claim_boundary",
    "sequence_id",
    "dependency_receipt_fingerprints",
}
RECEIPT_FIELDS = {
    *RECEIPT_BASE_FIELDS,
    "builder_provenance",
    "authority_key_fingerprint",
    "authority_sequence",
    "receipt_fingerprint",
}
ATTESTATION_FIELDS = {
    "schema_version",
    "receipt_fingerprint",
    "authority_key_fingerprint",
    "authority_sequence",
    "builder_provenance_fingerprint",
    "receipt_content_fingerprint",
    "attestation_fingerprint",
}
INDEX_FIELDS = {
    "schema_version",
    "next_sequence",
    "current_inputs",
    "latest_by_authority_key",
    "receipts",
    "index_fingerprint",
}
INDEX_RECEIPT_ENTRY_FIELDS = {
    "authority_key_fingerprint",
    "authority_sequence",
    "attestation_fingerprint",
    "receipt_content_fingerprint",
}


def _root_path(root: str | Path | None) -> Path:
    selected = root if root is not None else os.environ.get(AUTHORITY_ENV)
    if selected is None or not str(selected).strip():
        raise ValidationError(
            f"receipt authority root is required (pass root or set {AUTHORITY_ENV})"
        )
    return Path(selected).expanduser().resolve()


def _require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        raise ValidationError(f"{label} must be a lowercase sha256 fingerprint")
    digest = value[7:]
    if any(character not in "0123456789abcdef" for character in digest):
        raise ValidationError(f"{label} must be a lowercase sha256 fingerprint")
    return value


def _fingerprint_map(value: Any, label: str) -> dict[str, str]:
    mapping = require_mapping(value, label)
    if not mapping:
        raise ValidationError(f"{label} must contain at least one fingerprint")
    normalized: dict[str, str] = {}
    for key, item in mapping.items():
        if not isinstance(key, str) or not key.strip():
            raise ValidationError(f"{label} keys must be non-empty strings")
        normalized[key] = _require_sha256(item, f"{label}.{key}")
    return normalized


def _canonical_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(_canonical_text(value), encoding="utf-8")
    os.replace(temporary, path)


def _store_content_object(value: Any, *, root: str | Path | None) -> str:
    """Persist an immutable full JSON object and return its content identity."""

    authority_root = _root_path(root)
    object_fingerprint = fingerprint(value)
    digest = object_fingerprint.split(":", 1)[1]
    path = authority_root / "content" / f"{digest}.json"
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValidationError("authority content object is unreadable") from exc
        if existing != value:
            raise ValidationError("authority content path collision")
        return object_fingerprint
    _atomic_write_json(path, value)
    return object_fingerprint


def resolve_content_object(
    object_fingerprint: str,
    *,
    root: str | Path | None,
) -> Any:
    """Resolve one immutable full JSON object by its canonical fingerprint."""

    object_fingerprint = _require_sha256(object_fingerprint, "object_fingerprint")
    authority_root = _root_path(root)
    digest = object_fingerprint.split(":", 1)[1]
    path = authority_root / "content" / f"{digest}.json"
    if not path.is_file():
        raise ValidationError("authority content object is missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError("authority content object is unreadable") from exc
    if fingerprint(value) != object_fingerprint:
        raise ValidationError("authority content object fingerprint does not match")
    return value


@contextmanager
def _authority_lock(root: Path):
    """Serialize authority-index mutation; a stale lock fails visibly."""

    lock_path = root / "authority" / ".write.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + 30.0
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
            os.write(descriptor, str(os.getpid()).encode("ascii"))
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ValidationError(
                    "receipt authority write lock did not clear; no mutation was attempted"
                )
            time.sleep(0.01)
    try:
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _new_index() -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema_version": INDEX_VERSION,
        "next_sequence": 1,
        "current_inputs": {},
        "latest_by_authority_key": {},
        "receipts": {},
    }
    value["index_fingerprint"] = fingerprint(value)
    return value


def _load_index(root: Path) -> dict[str, Any]:
    path = root / "authority" / "index.json"
    if not path.exists():
        return _new_index()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"receipt authority index is unreadable: {exc}") from exc
    value = require_mapping(value, "receipt authority index")
    if set(value) != INDEX_FIELDS:
        raise ValidationError("receipt authority index has a non-current shape")
    if value.get("schema_version") != INDEX_VERSION:
        raise ValidationError("receipt authority index schema is not current")
    declared = _require_sha256(value.get("index_fingerprint"), "index_fingerprint")
    if declared != fingerprint_without(value, "index_fingerprint"):
        raise ValidationError("receipt authority index fingerprint does not match its content")
    if not isinstance(value.get("next_sequence"), int) or value["next_sequence"] < 1:
        raise ValidationError("receipt authority index has an invalid next_sequence")
    _fingerprint_map(value.get("current_inputs"), "current_inputs") if value["current_inputs"] else None
    for label in ("latest_by_authority_key", "receipts"):
        if not isinstance(value.get(label), dict):
            raise ValidationError(f"receipt authority index {label} must be an object")
    _verify_index_inventory(root, value)
    return value


def _read_attestation(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"receipt authority attestation is unreadable: {path.name}: {exc}") from exc
    value = require_mapping(value, "receipt authority attestation")
    if set(value) != ATTESTATION_FIELDS:
        raise ValidationError("receipt authority attestation has a non-current shape")
    if value.get("schema_version") != INDEX_VERSION:
        raise ValidationError("receipt authority attestation schema is not current")
    declared = _require_sha256(value.get("attestation_fingerprint"), "attestation_fingerprint")
    if declared != fingerprint_without(value, "attestation_fingerprint"):
        raise ValidationError("receipt authority attestation fingerprint does not match")
    return value


def _verify_index_inventory(root: Path, index: Mapping[str, Any]) -> None:
    """Detect index rollback by reconciling every immutable attestation."""

    attestations_root = root / "authority" / "attestations"
    paths = sorted(attestations_root.glob("*.json")) if attestations_root.is_dir() else []
    seen_receipts: set[str] = set()
    seen_sequences: set[int] = set()
    latest_by_owner: dict[str, tuple[int, str]] = {}
    for path in paths:
        attestation = _read_attestation(path)
        receipt_fingerprint = _require_sha256(
            attestation.get("receipt_fingerprint"), "receipt_fingerprint"
        )
        if path.stem != receipt_fingerprint.removeprefix("sha256:"):
            raise ValidationError("attestation filename and receipt fingerprint disagree")
        entry = index["receipts"].get(receipt_fingerprint)
        if not isinstance(entry, dict) or set(entry) != INDEX_RECEIPT_ENTRY_FIELDS:
            raise ValidationError(
                "receipt authority index rollback or omission detected: "
                f"{receipt_fingerprint}"
            )
        expected_entry = {
            "authority_key_fingerprint": attestation["authority_key_fingerprint"],
            "authority_sequence": attestation["authority_sequence"],
            "attestation_fingerprint": attestation["attestation_fingerprint"],
            "receipt_content_fingerprint": attestation["receipt_content_fingerprint"],
        }
        if entry != expected_entry:
            raise ValidationError("receipt authority index entry does not match attestation")
        sequence = attestation.get("authority_sequence")
        if not isinstance(sequence, int) or sequence < 1 or sequence in seen_sequences:
            raise ValidationError("receipt authority sequence inventory is invalid")
        seen_sequences.add(sequence)
        seen_receipts.add(receipt_fingerprint)
        owner = _require_sha256(
            attestation.get("authority_key_fingerprint"),
            "authority_key_fingerprint",
        )
        previous = latest_by_owner.get(owner)
        if previous is None or sequence > previous[0]:
            latest_by_owner[owner] = (sequence, receipt_fingerprint)
    if set(index["receipts"]) != seen_receipts:
        raise ValidationError("receipt authority index references an unbacked receipt")
    expected_sequences = set(range(1, index["next_sequence"]))
    if seen_sequences != expected_sequences:
        raise ValidationError("receipt authority index sequence rollback detected")
    expected_latest = {owner: row[1] for owner, row in latest_by_owner.items()}
    if index["latest_by_authority_key"] != expected_latest:
        raise ValidationError("receipt authority latest-owner pointer rollback detected")


def _write_index(root: Path, value: dict[str, Any]) -> None:
    payload = {key: item for key, item in value.items() if key != "index_fingerprint"}
    payload["index_fingerprint"] = fingerprint(payload)
    _atomic_write_json(root / "authority" / "index.json", payload)


def _authority_key(base: Mapping[str, Any]) -> str:
    return fingerprint(
        {
            "producer_skill": base["producer_skill"],
            "semantic_owner_id": base["semantic_owner_id"],
            "evidence_domain": base["evidence_domain"],
        }
    )


def validate_receipt(value: Any) -> dict[str, Any]:
    """Validate the exact current Receipt shape and content identity."""

    receipt = require_mapping(value, "receipt")
    unknown = sorted(set(receipt) - RECEIPT_FIELDS)
    if unknown:
        raise ValidationError(f"unsupported receipt fields: {', '.join(unknown)}")
    missing = sorted(RECEIPT_FIELDS - set(receipt))
    if missing:
        raise ValidationError(f"receipt is missing required fields: {', '.join(missing)}")
    if require_string(receipt, "schema_version") != "1.0":
        raise ValidationError("schema_version must be 1.0")
    for field in (
        "producer_skill",
        "semantic_owner_id",
        "native_route",
        "run_id",
        "covered_scope",
        "evidence_domain",
        "status",
        "safe_claim",
        "unsafe_claim_boundary",
        "sequence_id",
    ):
        require_string(receipt, field)
    require_fingerprint(receipt, "artifact_fingerprint")
    if receipt["status"] not in ALL_STATUSES:
        raise ValidationError(f"unsupported receipt status: {receipt['status']}")
    if receipt["evidence_domain"] not in EVIDENCE_DOMAINS:
        raise ValidationError(f"unsupported receipt evidence_domain: {receipt['evidence_domain']}")
    require_string_list(
        receipt.get("covered_obligation_ids"),
        "covered_obligation_ids",
        nonempty=True,
    )
    dependencies = require_string_list(
        receipt.get("dependency_receipt_fingerprints"),
        "dependency_receipt_fingerprints",
    )
    for index, dependency in enumerate(dependencies):
        _require_sha256(dependency, f"dependency_receipt_fingerprints[{index}]")
    _fingerprint_map(receipt.get("input_fingerprints"), "input_fingerprints")
    _fingerprint_map(receipt.get("output_fingerprints"), "output_fingerprints")
    provenance = require_mapping(receipt.get("builder_provenance"), "builder_provenance")
    if set(provenance) != {"builder_id", "builder_version", "source_fingerprint"}:
        raise ValidationError("builder_provenance has a non-current shape")
    if require_string(provenance, "builder_id") not in MANAGED_BUILDERS:
        raise ValidationError("builder_provenance names an unmanaged builder")
    if require_string(provenance, "builder_version") != BUILDER_VERSION:
        raise ValidationError("builder_provenance version is not current")
    require_fingerprint(provenance, "source_fingerprint")
    require_fingerprint(receipt, "authority_key_fingerprint")
    if receipt["authority_key_fingerprint"] != _authority_key(receipt):
        raise ValidationError("authority_key_fingerprint does not match receipt ownership")
    if not isinstance(receipt.get("authority_sequence"), int) or receipt["authority_sequence"] < 1:
        raise ValidationError("authority_sequence must be a positive integer")
    declared = require_fingerprint(receipt, "receipt_fingerprint")
    if declared in dependencies:
        raise ValidationError("receipt cannot depend on its own receipt_fingerprint")
    if declared != fingerprint_without(receipt, "receipt_fingerprint"):
        raise ValidationError("receipt_fingerprint does not match canonical receipt content")
    assert_schema_valid("evidence-receipt.schema.json", receipt)
    return receipt


def _record_current_inputs_unlocked(
    root: str | Path | None,
    current_inputs: Mapping[str, str],
) -> str:
    """Advance the store's current-input projection without creating evidence."""

    authority_root = _root_path(root)
    normalized = _fingerprint_map(dict(current_inputs), "current_inputs")
    index = _load_index(authority_root)
    index["current_inputs"].update(normalized)
    _write_index(authority_root, index)
    return fingerprint(index["current_inputs"])


def _record_current_inputs(
    root: str | Path | None,
    current_inputs: Mapping[str, str],
) -> str:
    """Internal current-input mutation used only by governed orchestration."""

    authority_root = _root_path(root)
    with _authority_lock(authority_root):
        return _record_current_inputs_unlocked(authority_root, current_inputs)


def _load_original(root: Path, receipt_fingerprint: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    index = _load_index(root)
    entry = index["receipts"].get(receipt_fingerprint)
    if not isinstance(entry, dict):
        raise ValidationError(
            f"authoritative receipt original is not registered: {receipt_fingerprint}"
        )
    digest = receipt_fingerprint.split(":", 1)[1]
    object_path = root / "objects" / f"{digest}.json"
    attestation_path = root / "authority" / "attestations" / f"{digest}.json"
    if not object_path.is_file():
        raise ValidationError(f"authoritative receipt original is missing: {receipt_fingerprint}")
    if not attestation_path.is_file():
        raise ValidationError(f"receipt authority attestation is missing: {receipt_fingerprint}")
    try:
        receipt = json.loads(object_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"authoritative receipt material is unreadable: {exc}") from exc
    receipt = validate_receipt(receipt)
    if receipt["receipt_fingerprint"] != receipt_fingerprint:
        raise ValidationError("receipt object path and receipt_fingerprint disagree")
    attestation = _read_attestation(attestation_path)
    expected_attestation = {
        "receipt_fingerprint": receipt_fingerprint,
        "authority_key_fingerprint": receipt["authority_key_fingerprint"],
        "authority_sequence": receipt["authority_sequence"],
        "builder_provenance_fingerprint": fingerprint(receipt["builder_provenance"]),
        "receipt_content_fingerprint": fingerprint(receipt),
    }
    for key, expected in expected_attestation.items():
        if attestation.get(key) != expected:
            raise ValidationError(f"receipt authority attestation {key} does not match original")
    if entry.get("authority_key_fingerprint") != receipt["authority_key_fingerprint"]:
        raise ValidationError("receipt authority index owner key does not match original")
    if entry.get("authority_sequence") != receipt["authority_sequence"]:
        raise ValidationError("receipt authority index sequence does not match original")
    if entry.get("attestation_fingerprint") != attestation["attestation_fingerprint"]:
        raise ValidationError("receipt authority index attestation pointer does not match")
    if entry.get("receipt_content_fingerprint") != fingerprint(receipt):
        raise ValidationError("receipt authority index content pointer does not match")
    return receipt, attestation, index


def _resolve_current_receipt(
    receipt_fingerprint: str,
    *,
    root: str | Path | None = None,
    current_inputs: Mapping[str, str] | None = None,
    expected: Mapping[str, Any] | None = None,
    _stack: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Resolve and verify one authoritative receipt and its currentness projection.

    A non-passing latest receipt can still be fresh.  ``current`` therefore
    means latest, input-current, dependency-current, and not explicitly stale;
    it does not mean ``status == current_pass``.
    """

    receipt_fingerprint = _require_sha256(receipt_fingerprint, "receipt_fingerprint")
    if receipt_fingerprint in _stack:
        cycle = " -> ".join((*_stack, receipt_fingerprint))
        raise ValidationError(f"receipt dependency cycle detected: {cycle}")
    authority_root = _root_path(root)
    receipt, _attestation, index = _load_original(authority_root, receipt_fingerprint)
    expected = dict(expected or {})
    allowed_expected = {
        "producer_skill",
        "semantic_owner_id",
        "native_route",
        "evidence_domain",
        "status",
        "artifact_fingerprint",
        "input_fingerprints",
        "output_fingerprints",
        "covered_scope",
        "covered_obligation_ids",
    }
    unknown_expected = sorted(set(expected) - allowed_expected)
    if unknown_expected:
        raise ValidationError(
            "unsupported expected receipt fields: " + ", ".join(unknown_expected)
        )
    for field, wanted in expected.items():
        if receipt.get(field) != wanted:
            raise ValidationError(
                f"resolved receipt {field} does not match expected value"
            )

    latest_fingerprint = index["latest_by_authority_key"].get(
        receipt["authority_key_fingerprint"]
    )
    if latest_fingerprint is None:
        raise ValidationError("receipt owner has no current authority pointer")
    latest_fingerprint = _require_sha256(latest_fingerprint, "latest receipt fingerprint")
    effective_inputs = (
        _fingerprint_map(dict(current_inputs), "current_inputs")
        if current_inputs is not None
        else dict(index["current_inputs"])
    )
    reasons: list[str] = []
    if latest_fingerprint != receipt_fingerprint:
        reasons.append(f"superseded_by:{latest_fingerprint}")
    for input_id, consumed in receipt["input_fingerprints"].items():
        current = effective_inputs.get(input_id)
        if current is None:
            reasons.append(f"current_input_missing:{input_id}")
        elif current != consumed:
            reasons.append(f"input_changed:{input_id}")

    dependency_projections: list[dict[str, Any]] = []
    for dependency in receipt["dependency_receipt_fingerprints"]:
        projection = _resolve_current_receipt(
            dependency,
            root=authority_root,
            current_inputs=effective_inputs,
            _stack=(*_stack, receipt_fingerprint),
        )
        dependency_projections.append(projection)
        if not projection["current"]:
            reasons.append(f"dependency_not_current:{dependency}")
        if receipt["status"] == "current_pass" and projection["status"] != "current_pass":
            reasons.append(f"dependency_not_passing:{dependency}")
    if receipt["status"] == "stale":
        reasons.append("receipt_status_stale")

    current = not reasons
    return {
        "receipt_fingerprint": receipt_fingerprint,
        "latest_receipt_fingerprint": latest_fingerprint,
        "receipt": receipt,
        "authoritative": True,
        "is_latest": latest_fingerprint == receipt_fingerprint,
        "inputs_current": not any(
            item.startswith("current_input_missing:") or item.startswith("input_changed:")
            for item in reasons
        ),
        "dependencies_current": not any(
            item.startswith("dependency_") for item in reasons
        ),
        "current": current,
        "status": receipt["status"] if current else "stale",
        "declared_status": receipt["status"],
        "reasons": reasons,
        "dependency_receipt_fingerprints": [
            item["receipt_fingerprint"] for item in dependency_projections
        ],
        "projection_fingerprint": fingerprint(
            {
                "receipt_fingerprint": receipt_fingerprint,
                "latest_receipt_fingerprint": latest_fingerprint,
                "current": current,
                "declared_status": receipt["status"],
                "reasons": reasons,
            }
        ),
    }


def resolve_current_receipt(
    receipt_fingerprint: str,
    *,
    root: str | Path | None = None,
    expected: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve currentness exclusively from the authority store projection.

    There is intentionally no public current-input override: callers cannot
    rewind currentness by supplying an old input map.
    """

    return _resolve_current_receipt(
        receipt_fingerprint,
        root=root,
        expected=expected,
    )


def resolve_latest_receipt_by_owner(
    *,
    producer_skill: str,
    semantic_owner_id: str,
    evidence_domain: str,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve the latest immutable receipt for one stable semantic owner."""

    require_string({"producer_skill": producer_skill}, "producer_skill")
    require_string({"semantic_owner_id": semantic_owner_id}, "semantic_owner_id")
    require_string({"evidence_domain": evidence_domain}, "evidence_domain")
    authority_root = _root_path(root)
    index = _load_index(authority_root)
    authority_key = _authority_key(
        {
            "producer_skill": producer_skill,
            "semantic_owner_id": semantic_owner_id,
            "evidence_domain": evidence_domain,
        }
    )
    receipt_fingerprint = index["latest_by_authority_key"].get(authority_key)
    if not isinstance(receipt_fingerprint, str):
        raise ValidationError(
            "semantic evidence owner has no authoritative receipt"
        )
    return resolve_current_receipt(
        receipt_fingerprint,
        root=authority_root,
        expected={
            "producer_skill": producer_skill,
            "semantic_owner_id": semantic_owner_id,
            "evidence_domain": evidence_domain,
        },
    )


def _commit_managed_receipt_unlocked(
    base_receipt: Mapping[str, Any],
    *,
    root: str | Path | None,
    builder_id: str,
    source_fingerprint: str,
    current_inputs: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build, attest, and commit an authoritative Receipt.

    Callers provide evidence fields, but never authority metadata or the final
    identity.  Those are assigned by this managed path and covered by the
    receipt fingerprint.
    """

    authority_root = _root_path(root)
    base = dict(require_mapping(dict(base_receipt), "managed receipt input"))
    unknown = sorted(set(base) - RECEIPT_BASE_FIELDS)
    missing = sorted(RECEIPT_BASE_FIELDS - set(base))
    if unknown:
        raise ValidationError(f"managed receipt input has unsupported fields: {', '.join(unknown)}")
    if missing:
        raise ValidationError(f"managed receipt input is missing fields: {', '.join(missing)}")
    if builder_id not in MANAGED_BUILDERS:
        raise ValidationError(f"unmanaged receipt builder: {builder_id}")
    source_fingerprint = _require_sha256(source_fingerprint, "source_fingerprint")
    if base.get("schema_version") != "1.0":
        raise ValidationError("schema_version must be 1.0")
    for field in (
        "producer_skill",
        "semantic_owner_id",
        "native_route",
        "run_id",
        "covered_scope",
        "evidence_domain",
        "status",
        "safe_claim",
        "unsafe_claim_boundary",
        "sequence_id",
    ):
        require_string(base, field)
    if base["evidence_domain"] not in EVIDENCE_DOMAINS:
        raise ValidationError("unsupported receipt evidence domain")
    if base["status"] not in ALL_STATUSES:
        raise ValidationError(f"unsupported receipt status: {base['status']}")
    require_fingerprint(base, "artifact_fingerprint")
    require_string_list(base["covered_obligation_ids"], "covered_obligation_ids", nonempty=True)
    dependencies = require_string_list(
        base["dependency_receipt_fingerprints"],
        "dependency_receipt_fingerprints",
    )
    for index_number, dependency in enumerate(dependencies):
        _require_sha256(dependency, f"dependency_receipt_fingerprints[{index_number}]")
    base["input_fingerprints"] = _fingerprint_map(base["input_fingerprints"], "input_fingerprints")
    base["output_fingerprints"] = _fingerprint_map(base["output_fingerprints"], "output_fingerprints")
    if builder_id == "logic-writing.adapter-result.v1" and base["producer_skill"] not in {
        "sourceguard",
        "logicguard",
        "traceguard",
        "flowguard",
        "documents",
        "pdf",
    }:
        raise ValidationError("adapter-result builder requires a native specialist producer")
    builder_contracts = {
        "logic-writing.revision-provenance.v1": (
            "logic-writing",
            "validate-revision-provenance",
            "revision_provenance",
        ),
        "logic-writing.source-unit-manifest.v1": (
            "logic-writing",
            "build-source-unit-manifest",
            "revision_provenance",
        ),
        "logic-writing.reader-brief.v1": (
            "logic-writing",
            "build-reader-brief",
            "reader_brief",
        ),
        "logic-writing.reader-deterministic.v1": (
            "logic-writing",
            "audit-reader-output",
            "reader_deterministic",
        ),
        "logic-writing.reader-judgment.v1": (
            "logic-writing",
            "judge-reader-output",
            "reader_judgment",
        ),
        "logic-writing.final-closure.v1": (
            "logic-writing",
            "derive-final-closure",
            "final_closure",
        ),
    }
    contract = builder_contracts.get(builder_id)
    if contract is not None and (
        base["producer_skill"],
        base["native_route"],
        base["evidence_domain"],
    ) != contract:
        raise ValidationError(f"{builder_id} does not own this receipt route/domain")

    index = _load_index(authority_root)
    prospective_inputs = dict(index["current_inputs"])
    supplied_current = dict(current_inputs or base["input_fingerprints"])
    normalized_current = _fingerprint_map(supplied_current, "current_inputs")
    for input_id, consumed in base["input_fingerprints"].items():
        if normalized_current.get(input_id) != consumed:
            raise ValidationError(
                f"managed builder current input does not match consumed input: {input_id}"
            )
    prospective_inputs.update(normalized_current)
    for dependency in dependencies:
        projection = _resolve_current_receipt(
            dependency,
            root=authority_root,
            current_inputs=prospective_inputs,
        )
        if not projection["current"]:
            raise ValidationError(f"managed receipt dependency is not current: {dependency}")
        if base["status"] == "current_pass" and projection["status"] != "current_pass":
            raise ValidationError(
                f"current_pass receipt cannot depend on non-passing receipt: {dependency}"
            )

    authority_key = _authority_key(base)
    provenance = {
        "builder_id": builder_id,
        "builder_version": BUILDER_VERSION,
        "source_fingerprint": source_fingerprint,
    }
    latest = index["latest_by_authority_key"].get(authority_key)
    if isinstance(latest, str):
        try:
            previous, _attestation, _current_index = _load_original(authority_root, latest)
        except ValidationError:
            previous = None
        if previous is not None:
            previous_base = {key: previous[key] for key in RECEIPT_BASE_FIELDS}
            if previous_base == base and previous["builder_provenance"] == provenance:
                projection = _resolve_current_receipt(
                    latest,
                    root=authority_root,
                    current_inputs=prospective_inputs,
                )
                if projection["current"]:
                    return previous

    sequence = index["next_sequence"]
    receipt = {
        **base,
        "builder_provenance": provenance,
        "authority_key_fingerprint": authority_key,
        "authority_sequence": sequence,
    }
    receipt["receipt_fingerprint"] = fingerprint(receipt)
    validate_receipt(receipt)
    if receipt["receipt_fingerprint"] in dependencies:
        raise ValidationError("receipt cannot depend on itself")

    attestation = {
        "schema_version": INDEX_VERSION,
        "receipt_fingerprint": receipt["receipt_fingerprint"],
        "authority_key_fingerprint": authority_key,
        "authority_sequence": sequence,
        "builder_provenance_fingerprint": fingerprint(provenance),
        "receipt_content_fingerprint": fingerprint(receipt),
    }
    attestation["attestation_fingerprint"] = fingerprint(attestation)
    digest = receipt["receipt_fingerprint"].split(":", 1)[1]
    object_path = authority_root / "objects" / f"{digest}.json"
    attestation_path = authority_root / "authority" / "attestations" / f"{digest}.json"
    if object_path.exists() or attestation_path.exists():
        raise ValidationError("managed receipt destination already exists without reusable authority")
    _atomic_write_json(object_path, receipt)
    _atomic_write_json(attestation_path, attestation)

    index["current_inputs"] = prospective_inputs
    index["receipts"][receipt["receipt_fingerprint"]] = {
        "authority_key_fingerprint": authority_key,
        "authority_sequence": sequence,
        "attestation_fingerprint": attestation["attestation_fingerprint"],
        "receipt_content_fingerprint": attestation["receipt_content_fingerprint"],
    }
    index["latest_by_authority_key"][authority_key] = receipt["receipt_fingerprint"]
    index["next_sequence"] = sequence + 1
    _write_index(authority_root, index)
    return receipt


def _commit_managed_receipt(
    base_receipt: Mapping[str, Any],
    *,
    root: str | Path | None,
    builder_id: str,
    source_fingerprint: str,
    current_inputs: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Internal generic commit; public producers must expose dedicated builders."""

    authority_root = _root_path(root)
    with _authority_lock(authority_root):
        return _commit_managed_receipt_unlocked(
            base_receipt,
            root=authority_root,
            builder_id=builder_id,
            source_fingerprint=source_fingerprint,
            current_inputs=current_inputs,
        )


__all__ = [
    "AUTHORITY_ENV",
    "resolve_content_object",
    "resolve_current_receipt",
    "resolve_latest_receipt_by_owner",
    "validate_receipt",
]
