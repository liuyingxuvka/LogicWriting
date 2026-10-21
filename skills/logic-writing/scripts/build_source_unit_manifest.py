"""Build and verify the exact source/target unit universe for revision provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from _common import (
    ValidationError,
    dump_json,
    fingerprint_without,
    load_json,
    require_mapping,
    require_schema,
    require_string,
    validation_result,
)


HEADING = re.compile(r"^#{1,6}\s+")
LIST_ITEM = re.compile(r"^(?:[-*+]\s+|\d+[.)]\s+)")
TABLE_ROW = re.compile(r"^\|.*\|\s*$")
BLOCKQUOTE = re.compile(r"^>\s+")
MANIFEST_FIELDS = {"schema_version", "manifest_id", "source", "target", "manifest_fingerprint"}


def fingerprint_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def read_text_artifact(path: str | Path) -> tuple[Path, bytes, str]:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise ValidationError(f"artifact file is missing: {resolved}")
    data = resolved.read_bytes()
    if not data:
        raise ValidationError(f"artifact file is empty: {resolved}")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(
            f"artifact must be exact UTF-8 text for unit extraction: {resolved}"
        ) from exc
    return resolved, data, text


def _kind(text: str) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None
    if HEADING.match(stripped):
        return "heading"
    if LIST_ITEM.match(stripped):
        return "list_item"
    if TABLE_ROW.match(stripped):
        return "table_row"
    if BLOCKQUOTE.match(stripped):
        return "blockquote"
    return "paragraph"


def extract_visible_units(data: bytes, *, namespace: str) -> list[dict[str, Any]]:
    """Partition every nonblank visible UTF-8 byte into a stable unit."""

    text = data.decode("utf-8")
    encoded_lines = text.splitlines(keepends=True)
    if not encoded_lines and text:
        encoded_lines = [text]
    rows: list[dict[str, Any]] = []
    offset = 0
    for line_number, line in enumerate(encoded_lines, start=1):
        encoded = line.encode("utf-8")
        rows.append(
            {
                "line_number": line_number,
                "text": line,
                "byte_start": offset,
                "byte_end": offset + len(encoded),
                "kind": _kind(line),
            }
        )
        offset += len(encoded)
    if offset < len(data):
        tail = data[offset:]
        decoded_tail = tail.decode("utf-8")
        rows.append(
            {
                "line_number": len(rows) + 1,
                "text": decoded_tail,
                "byte_start": offset,
                "byte_end": len(data),
                "kind": _kind(decoded_tail),
            }
        )

    groups: list[tuple[str, int, int, int, int]] = []
    paragraph_start: dict[str, Any] | None = None
    paragraph_end: dict[str, Any] | None = None

    def flush_paragraph() -> None:
        nonlocal paragraph_start, paragraph_end
        if paragraph_start is not None and paragraph_end is not None:
            groups.append(
                (
                    "paragraph",
                    paragraph_start["line_number"],
                    paragraph_end["line_number"],
                    paragraph_start["byte_start"],
                    paragraph_end["byte_end"],
                )
            )
        paragraph_start = None
        paragraph_end = None

    for row in rows:
        kind = row["kind"]
        if kind is None:
            flush_paragraph()
            continue
        if kind == "paragraph":
            paragraph_start = paragraph_start or row
            paragraph_end = row
            continue
        flush_paragraph()
        groups.append(
            (
                kind,
                row["line_number"],
                row["line_number"],
                row["byte_start"],
                row["byte_end"],
            )
        )
    flush_paragraph()

    units: list[dict[str, Any]] = []
    for index, (kind, line_start, line_end, byte_start, byte_end) in enumerate(groups, start=1):
        raw = data[byte_start:byte_end]
        if not raw.decode("utf-8").strip():
            continue
        locator = f"line:{line_start}" if line_start == line_end else f"line:{line_start}-{line_end}"
        units.append(
            {
                "unit_id": f"{namespace}:{kind}:{index:04d}",
                "kind": kind,
                "locator": locator,
                "line_start": line_start,
                "line_end": line_end,
                "byte_start": byte_start,
                "byte_end": byte_end,
                "content_fingerprint": fingerprint_bytes(raw),
            }
        )
    if not units:
        raise ValidationError(f"{namespace} artifact has no visible units")
    return units


def _artifact_record(path: str | Path, *, namespace: str) -> dict[str, Any]:
    resolved, data, _text = read_text_artifact(path)
    return {
        "locator": str(resolved),
        "artifact_fingerprint": fingerprint_bytes(data),
        "byte_length": len(data),
        "units": extract_visible_units(data, namespace=namespace),
    }


def build_source_unit_manifest(
    *,
    manifest_id: str,
    source_path: str | Path,
    target_path: str | Path,
) -> dict[str, Any]:
    if not isinstance(manifest_id, str) or not manifest_id.strip():
        raise ValidationError("manifest_id must be a non-empty identifier")
    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "manifest_id": manifest_id,
        "source": _artifact_record(source_path, namespace="source"),
        "target": _artifact_record(target_path, namespace="target"),
    }
    if manifest["source"]["artifact_fingerprint"] == manifest["target"]["artifact_fingerprint"]:
        raise ValidationError("source and target bytes must differ for revision provenance")
    manifest["manifest_fingerprint"] = fingerprint_without(manifest, "manifest_fingerprint")
    require_schema("source-unit-manifest.schema.json", manifest, label="source-unit manifest")
    return manifest


def validate_source_unit_manifest(
    value: Any,
    *,
    source_path: str | Path,
    target_path: str | Path,
) -> dict[str, Any]:
    manifest = require_mapping(value, "source-unit manifest")
    if set(manifest) != MANIFEST_FIELDS:
        raise ValidationError("source-unit manifest has a non-current shape")
    require_schema("source-unit-manifest.schema.json", manifest, label="source-unit manifest")
    if require_string(manifest, "schema_version") != "1.0":
        raise ValidationError("source-unit manifest schema_version must be 1.0")
    manifest_id = require_string(manifest, "manifest_id")
    expected = build_source_unit_manifest(
        manifest_id=manifest_id,
        source_path=source_path,
        target_path=target_path,
    )
    if manifest != expected:
        raise ValidationError(
            "source-unit manifest does not match the complete current source/target bytes"
        )
    return manifest




def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--manifest-id")
    parser.add_argument("--input")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = (
            validate_source_unit_manifest(
                load_json(args.input),
                source_path=args.source,
                target_path=args.target,
            )
            if args.input
            else build_source_unit_manifest(
                manifest_id=require_string({"manifest_id": args.manifest_id}, "manifest_id"),
                source_path=args.source,
                target_path=args.target,
            )
        )
        dump_json(result, args.output)
        return 0
    except (ValidationError, OSError, json.JSONDecodeError) as exc:
        dump_json(validation_result(status="blocked", errors=(str(exc),)), args.output)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "build_source_unit_manifest",
    "extract_visible_units",
    "fingerprint_bytes",
    "read_text_artifact",
    "validate_source_unit_manifest",
]
