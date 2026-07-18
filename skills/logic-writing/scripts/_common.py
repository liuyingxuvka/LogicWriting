"""Portable helpers shared by Logic Writing validation scripts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


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
    "sourceguard", "logicguard", "traceguard", "worldguard",
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
    "reader_judgment",
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
        result = validate_fn(load_json(args.input))
        dump_json(result, args.output)
        return 0 if result.get("status") in {PASS, "passed"} else 1
    except (ValidationError, OSError, json.JSONDecodeError) as exc:
        dump_json(validation_result(status="blocked", errors=(str(exc),)), args.output)
        return 1
