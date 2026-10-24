"""Portable helpers shared by Logic Writing validation scripts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


PASS = "current_pass"
DEGRADED_STATUSES = {
    "not_run",
    "stale",
    "provider_unavailable",
    "dependency_unavailable",
    "access_gap",
    "render_not_run",
    "bounded",
    "downgraded",
    "partial",
    "blocked",
    "failed",
    "planning_only",
    "saved_but_modeling_incomplete",
}
ALL_STATUSES = {PASS, *DEGRADED_STATUSES}
NATIVE_OWNERS = {
    "researchguard", "sourceguard", "logicguard", "traceguard", "worldguard",
    "flowguard", "documents", "pdf",
}
EVIDENCE_DOMAINS = {
    "source_discovery",
    "source_observation",
    "source_depth",
    "source_library",
    "argument_model",
    "structured_artifact",
    "model_depth",
    "artifact_synthesis",
    "temporal_trace",
    "causal_trace",
    "competing_storyline",
    "prediction_boundary",
    "world_consistency",
    "process_model",
    "process_freshness",
    "document_content",
    "document_mutation",
    "document_render",
    "document_visual",
    "pdf_content",
    "pdf_render",
    "pdf_visual",
    "citation_semantics",
    "revision_provenance",
    "reader_brief",
    "reader_deterministic",
    "reader_route_audit",
    "reader_judgment",
    "reader_repair",
    "shared_writing",
    "story_model",
    "story_continuity",
    "model_artifact_binding",
    "travel_evidence",
    "travel_feasibility",
    "traveler_fit",
    "travel_fallback",
    "final_closure",
    "development_validation",
    "installation",
    "global_routing",
    "release",
    "retirement",
}


class ValidationError(ValueError):
    """Raised when a typed Logic Writing contract is invalid."""


IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value: Any, prefix: str = "sha256") -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def fingerprint_text(text: str, prefix: str = "sha256") -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return f"{prefix}:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"


def fingerprint_without(value: dict[str, Any], *keys: str) -> str:
    return fingerprint({key: item for key, item in value.items() if key not in set(keys)})


def fill_fingerprint(record: Any, field: str) -> None:
    """Compute a record's own fingerprint when the caller left it out; a given value is kept and checked."""
    if isinstance(record, dict) and record.get(field) is None:
        record[field] = fingerprint_without(record, field)


def fill_missing(record: Any, field: str, value: Any) -> None:
    """Copy a missing field from the record it must match; a given value is kept and checked."""
    if isinstance(record, dict) and record.get(field) is None and value is not None:
        record[field] = value


def require_mapping(value: Any, label: str = "value") -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be an object")
    return value


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValidationError(f"{label} must be an array")
    return value


def require_string(mapping: dict[str, Any], key: str, *, allow_empty: bool = False) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValidationError(f"{key} must be a non-empty string")
    return value


def require_identifier(
    mapping: dict[str, Any],
    key: str,
    *,
    min_length: int = 2,
    max_length: int = 160,
) -> str:
    value = require_string(mapping, key)
    if not min_length <= len(value) <= max_length or not IDENTIFIER.fullmatch(value):
        raise ValidationError(
            f"{key} must be a {min_length}-{max_length} character identifier using letters, digits, dot, underscore, colon, or hyphen"
        )
    return value


def require_datetime(mapping: dict[str, Any], key: str) -> str:
    value = require_string(mapping, key)
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValidationError(f"{key} must be an RFC 3339 date-time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValidationError(f"{key} must include a UTC offset")
    return value


def require_unique(values: Iterable[str], label: str) -> tuple[str, ...]:
    items = tuple(values)
    if len(set(items)) != len(items):
        raise ValidationError(f"{label} contains duplicate values")
    return items


def require_fingerprint(mapping: dict[str, Any], key: str) -> str:
    value = require_string(mapping, key)
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", value):
        raise ValidationError(f"{key} must be a lowercase sha256 fingerprint")
    return value


def require_fingerprint_map(value: Any, label: str, *, nonempty: bool = True) -> dict[str, str]:
    entries = require_mapping(value, label)
    if nonempty and not entries:
        raise ValidationError(f"{label} must contain at least one fingerprint")
    for key, item in entries.items():
        if not isinstance(key, str) or not 2 <= len(key) <= 160 or not IDENTIFIER.fullmatch(key):
            raise ValidationError(f"{label} keys must be valid identifiers")
        if not isinstance(item, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", item):
            raise ValidationError(f"{label}.{key} must be a lowercase sha256 fingerprint")
    return entries


def require_schema(schema_name: str, artifact: Any, *, label: str | None = None) -> None:
    """Enforce one bundled current JSON contract and expose one error vocabulary.

    The schema runtime is deliberately imported here rather than at module load
    time so ordinary helper use does not hide a broken contract inventory.  A
    missing, stale, or invalid contract is a hard validation failure; there is
    no secondary validator or compatibility path.
    """

    from schema_validation import (
        SchemaRuntimeConfigurationError,
        SchemaValidationError,
        UnknownSchemaError,
        assert_schema_valid,
    )

    try:
        assert_schema_valid(schema_name, artifact)
    except (SchemaRuntimeConfigurationError, SchemaValidationError, UnknownSchemaError) as exc:
        prefix = label or schema_name
        raise ValidationError(f"{prefix} violates the current schema authority: {exc}") from exc


def require_string_list(
    value: Any,
    label: str,
    *,
    nonempty: bool = False,
    unique: bool = True,
) -> list[str]:
    items = require_list(value, label)
    if nonempty and not items:
        raise ValidationError(f"{label} must contain at least one item")
    if not all(isinstance(item, str) and item.strip() for item in items):
        raise ValidationError(f"{label} must contain non-empty strings")
    if unique and len(items) != len(set(items)):
        raise ValidationError(f"{label} contains duplicate values")
    return items


def reject_unknown_keys(mapping: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise ValidationError(f"{label} contains unsupported fields: {', '.join(unknown)}")


def contains_internal_language(text: str) -> tuple[str, ...]:
    patterns = {
        "guard_name": r"\b(?:SourceGuard|LogicGuard|TraceGuard|FlowGuard)\b",
        "route_id": r"\b(?:investigation-route|academic-writing-route|route_id|model_id|gap_id)\b",
        "status_field": r"\b(?:closure_status|reader_native|current_pass|provider_unavailable|render_not_run)\b",
        "agent_instruction": r"\b(?:the agent must|invoke the skill|run the workflow|internal ledger)\b",
        "snake_case": r"\b[a-z]+(?:_[a-z0-9]+){1,}\b",
    }
    hits = [name for name, pattern in patterns.items() if re.search(pattern, text, flags=re.IGNORECASE)]
    return tuple(hits)


def load_json(path: str | Path | None) -> Any:
    if path in {None, "-"}:
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text(encoding="utf-8"))


_REQUEST_CONTAINER_FIELDS = frozenset({
    # Reviewed envelopes for the route, brief, map/audit, review and closure CLIs.
    "writing_request", "material_assumptions", "intent_conflicts",
    "route_decision", "content_boundaries", "composition_plan", "route_composition",
    "native_handoff", "native_plan", "native_handoff_mapping", "artifact_map",
    "reader_brief", "contract", "shared_writing", "review", "route_review",
    "deterministic_audit", "judgment", "revision_provenance", "provenance",
})


def _absolute_artifact_path(record: dict[str, Any], base: Path) -> None:
    value = record.get("artifact_path")
    if isinstance(value, str) and value:
        artifact_path = Path(value).expanduser()
        if not artifact_path.is_absolute():
            record["artifact_path"] = str((base / artifact_path).resolve())


def load_request(path: str | Path | None) -> Any:
    """Load a request whose top-level object fields may name JSON files instead.

    Only known container fields accept file references; scalar IDs, artifact
    paths and opaque native locators remain strings. A reference is relative to
    the request file. A file that holds another script's result contributes the
    object stored under the same field name, or its only object. Relative
    artifact paths use the containing file; stdin retains current-directory behavior.
    """
    value = load_json(path)
    if not isinstance(value, dict):
        return value
    if "sourceguard_model" in value:
        raise ValidationError("`sourceguard_model` is retired; use research_folder (a ResearchGuard research folder)")
    file_request = path not in {None, "-"}
    base = Path(path).resolve().parent if file_request else Path.cwd()
    if file_request:
        _absolute_artifact_path(value, base)
    for report in value.get("provider_reports", []) if isinstance(value.get("provider_reports", []), list) else []:
        if isinstance(report, dict) and isinstance(report.get("path"), str):
            report["path"] = str((base / Path(report["path"]).expanduser()).resolve())
    for key, item in list(value.items()):
        record_base = base
        if key in _REQUEST_CONTAINER_FIELDS and isinstance(item, str) and item.endswith(".json"):
            reference_path = base / Path(item).expanduser()
            loaded = load_json(reference_path)
            record_base = reference_path.resolve().parent
            if isinstance(loaded, dict) and {"status", "errors", "warnings"} <= set(loaded):
                if isinstance(loaded.get(key), dict):
                    loaded = loaded[key]
                elif loaded["errors"] or loaded["status"] == "blocked":
                    errors = loaded["errors"]
                    detail = errors[0] if isinstance(errors, list) and errors else errors or "no error detail"
                    detail = " ".join(str(detail).split())
                    raise ValidationError(
                        f"input {reference_path.name} is a failed result (status {loaded['status']}): {detail}"
                    )
                else:
                    objects = [entry for entry in loaded.values() if isinstance(entry, dict)]
                    if len(objects) == 1:
                        loaded = objects[0]
            value[key] = loaded
        if key == "route_composition" and isinstance(value[key], dict):
            for field in ("longform_project", "world_contract", "trip_plan"):
                reference = value[key].get(field)
                if isinstance(reference, str) and reference:
                    value[key][field] = str((record_base / Path(reference).expanduser()).resolve())
        if file_request and key in {"contract", "shared_writing"} and isinstance(value[key], dict):
            _absolute_artifact_path(value[key], record_base)
        if file_request and key in {"revision_provenance", "provenance"} and isinstance(value[key], dict):
            source = value[key].get("source_artifact_path")
            if isinstance(source, str) and source:
                value[key]["source_artifact_path"] = str((record_base / Path(source).expanduser()).resolve())
    if file_request and isinstance(value.get("source_artifact_path"), str):
        value["source_artifact_path"] = str((base / Path(value["source_artifact_path"]).expanduser()).resolve())
    if "research_folder" in value:
        folder = value["research_folder"]
        if not isinstance(folder, str) or not folder.strip():
            raise ValidationError("research_folder must be a nonempty ResearchGuard research folder path")
        value["research_folder"] = str((base / Path(folder).expanduser()).resolve())
    if "research_status" in value:
        status = value["research_status"]
        if not isinstance(status, str) or not status.strip():
            raise ValidationError("research_status must be a nonempty path to a saved researchguard status --json report")
        value["research_status"] = str((base / Path(status).expanduser()).resolve())
    return value


def dump_json(value: Any, path: str | Path | None = None) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path in {None, "-"}:
        sys.stdout.write(text)
    else:
        Path(path).write_text(text, encoding="utf-8")


def validation_result(*, status: str, errors=(), warnings=(), **values: Any) -> dict[str, Any]:
    return {
        "status": status,
        "errors": list(errors),
        "warnings": list(warnings),
        **values,
    }


def cli_validate(validate_fn, description: str) -> int:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = validate_fn(load_request(args.input))
        dump_json(result, args.output)
        return 0 if result.get("status") in {PASS, "passed"} else 1
    except (ValidationError, OSError, json.JSONDecodeError) as exc:
        dump_json(validation_result(status="blocked", errors=(str(exc),)), args.output)
        return 1


RESEARCHGUARD_MIN_VERSION = (0, 5, 15)
RESEARCHGUARD_INSTALL_HINT = 'python -m pip install "git+https://github.com/liuyingxuvka/ResearchGuard.git"'


def researchguard_version_problem(version: str | None) -> str | None:
    match = re.match(r"^\s*(\d+)\.(\d+)\.(\d+)", version or "")
    if match and tuple(int(part) for part in match.groups()) >= RESEARCHGUARD_MIN_VERSION:
        return None
    minimum = ".".join(str(part) for part in RESEARCHGUARD_MIN_VERSION)
    return f"ResearchGuard >= {minimum} is required, found {version or 'not installed'}; install with: {RESEARCHGUARD_INSTALL_HINT}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_exact_fingerprint(value: Mapping[str, Any], field: str) -> None:
    if value.get(field) != fingerprint_without(dict(value), field):
        raise ValidationError(f"{field} does not bind the exact current object")


def _ids(rows: Iterable[Mapping[str, Any]], field: str, label: str) -> tuple[str, ...]:
    values = tuple(str(row.get(field, "")) for row in rows)
    if not all(values) or len(values) != len(set(values)):
        raise ValidationError(f"{label} ids must be non-empty and unique")
    return values


def read_worldguard_report(path: str | Path) -> str:
    """Read one saved native check status; malformed reports never mean PASS."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError):
        return "unreadable"
    status = document.get("status") if isinstance(document, dict) else None
    return status if isinstance(status, str) and status in {"PASS", "FAIL", "GAP", "BOUNDARY_EXCEEDED"} else "unreadable"


def worldguard_report_identity_problems(report_path: str | Path, world_contract: str | Path | None) -> list[str]:
    """Problem codes when a saved WorldGuard report does not name the brief's world contract.

    The expected id follows WorldGuard: the contract's ``contract_id``, else ``claim.claim_id``.
    """
    if not isinstance(world_contract, (str, Path)) or not str(world_contract):
        return ["world_report_unbound:world_contract"]
    try:
        import yaml
    except ImportError:
        return ["world_report_unbound:world_contract"]
    try:
        contract = yaml.safe_load(Path(world_contract).expanduser().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, yaml.YAMLError):
        return ["world_report_unbound:world_contract"]
    if not isinstance(contract, Mapping):
        return ["world_report_unbound:world_contract"]
    expected = contract.get("contract_id")
    if not isinstance(expected, str) or not expected:
        claim = contract.get("claim")
        expected = claim.get("claim_id") if isinstance(claim, Mapping) else None
    if not isinstance(expected, str) or not expected:
        return ["world_report_unbound:world_contract"]
    try:
        report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError):
        report = None
    actual = report.get("contract_id") if isinstance(report, Mapping) else None
    return [] if actual == expected else ["world_report_mismatch:contract_id"]
