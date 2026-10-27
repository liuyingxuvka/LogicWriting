"""Exact UTF-8 artifact partitions, from current files or explicit in-memory text."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from _common import (ValidationError, fingerprint, fingerprint_text,
                     require_mapping, require_schema, require_exact_fingerprint, unique_ids)



LIST_LINE = re.compile(
    r"^\s*(?:[-*+•◦▪‣]\s+|\d+[.)、]\s*|[一二三四五六七八九十]+、\s*|"
    r"[（(][一二三四五六七八九十\d]+[）)]\s*|\*\*[^*]{1,30}\*\*[：:])"
)



def _classify_block(text: str) -> tuple[str, str, int]:
    stripped = text.strip()
    first = stripped.splitlines()[0] if stripped else ""
    heading = re.match(r"^(#{1,6})\s+(.+)$", first)
    if heading:
        return "heading", "other", len(heading.group(1))
    if first.startswith("```"):
        return "code", "other", 0
    if all(line.lstrip().startswith(">") for line in stripped.splitlines() if line.strip()):
        return "quote", "prose", 0
    lines = [line for line in stripped.splitlines() if line.strip()]
    if lines and (all(LIST_LINE.match(line) for line in lines)
                  or len(lines) > 1 and all(LIST_LINE.match(line) for line in lines[1:])):
        return "list", "functional_list", 0
    if len(lines) >= 2 and all("|" in line for line in lines):
        return "table", "table", 0
    return "paragraph", "prose", 0



def classify_text_blocks(text: str) -> list[dict[str, Any]]:
    """Expose the artifact map's block classification to route validators."""
    blocks = []
    for text_block in re.split(r"\n\s*\n", text.strip()):
        if not text_block.strip():
            continue
        kind, zone, level = _classify_block(text_block)
        blocks.append({"text": text_block, "kind": kind, "zone": zone,
                       "heading_level": level,
                       "list_items": sum(bool(LIST_LINE.match(line)) for line in text_block.splitlines())
                       if kind == "list" else 0})
    return blocks



def _unmapped_ranges_for_units(text: str, units: Iterable[Mapping[str, Any]]) -> list[dict[str, int]]:
    """Compute the exact gaps left by non-document units.

    Blank lines and leading/trailing whitespace are allowed gaps.  A caller
    cannot use this field to hide prose: validation rejects any gap containing
    a non-whitespace character.
    """
    spans = sorted(
        (int(row["start"]), int(row["end"]))
        for row in units
        if row.get("unit_kind") != "document"
    )
    gaps: list[dict[str, int]] = []
    cursor = 0
    for start, end in spans:
        if start > cursor:
            gaps.append({"start": cursor, "end": start})
        cursor = max(cursor, end)
    if cursor < len(text):
        gaps.append({"start": cursor, "end": len(text)})
    return gaps



def build_artifact_map(artifact_path: str | Path, *, map_id: str, language: str,
                       artifact_format: str | None = None) -> dict[str, Any]:
    path = Path(artifact_path).expanduser().resolve()
    if not path.is_file():
        raise ValidationError(f"artifact_path does not identify a current file: {path}")
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("ArtifactMap currently requires UTF-8 text or Markdown") from exc
    return build_artifact_map_from_text(text, artifact_path=path, map_id=map_id,
                                        language=language, artifact_format=artifact_format)



def build_artifact_map_from_text(text: str, *, artifact_path: str | Path,
                                 map_id: str, language: str,
                                 artifact_format: str | None = None) -> dict[str, Any]:
    """Partition these explicit bytes without replacing or reading the source file."""
    path = Path(artifact_path).expanduser().resolve()
    data = text.encode("utf-8")
    fmt = artifact_format or ("markdown" if path.suffix.lower() in {".md", ".markdown"} else "text")
    if fmt not in {"text", "markdown"}:
        raise ValidationError("ArtifactMap supports only text and markdown")
    artifact_fp = "sha256:" + __import__("hashlib").sha256(data).hexdigest()
    units: list[dict[str, Any]] = [
        {
            "artifact_unit_id": "artifact:document",
            "parent_unit_id": None,
            "unit_kind": "document",
            "zone": "other",
            "order": 1,
            "heading_level": 0,
            "locator": f"char:0-{len(text)}",
            "start": 0,
            "end": len(text),
            "text": text,
            "content_fingerprint": fingerprint_text(text),
        }
    ]
    heading_stack: list[tuple[int, str]] = []
    order = 2
    block_start: int | None = None
    offset = 0
    blocks: list[tuple[int, int, str]] = []
    pending: list[tuple[int, str]] = []
    pending_kind: str | None = None
    pending_start: int | None = None
    for line in text.splitlines(keepends=True):
        if line.strip():
            if block_start is None:
                block_start = offset
            line_kind = "heading" if re.match(r"^\s*#{1,6}\s+", line) else ("list" if LIST_LINE.match(line) else "paragraph")
            if pending_kind is None:
                pending_kind, pending_start = line_kind, offset
            elif line_kind != pending_kind:
                raw = text[pending_start:offset].rstrip("\r\n")
                blocks.append((pending_start, offset - (len(text[pending_start:offset]) - len(raw)), raw))
                pending_kind, pending_start = line_kind, offset
        elif block_start is not None:
            if pending_kind is not None and pending_start is not None:
                raw = text[pending_start:offset].rstrip("\r\n")
                blocks.append((pending_start, offset - (len(text[pending_start:offset]) - len(raw)), raw))
            pending_kind, pending_start = None, None
            block_start = None
        offset += len(line)
    if pending_kind is not None and pending_start is not None:
        raw = text[pending_start:len(text)].rstrip("\r\n")
        blocks.append((pending_start, len(text) - (len(text[pending_start:]) - len(raw)), raw))
    if not blocks and text:
        blocks.append((0, len(text), text))

    for index, (start, raw_end, block_text) in enumerate(blocks, start=1):
        end = start + len(block_text)
        kind, zone, heading_level = _classify_block(block_text)
        if kind == "heading":
            while heading_stack and heading_stack[-1][0] >= heading_level:
                heading_stack.pop()
            parent_id = heading_stack[-1][1] if heading_stack else "artifact:document"
            unit_id = f"artifact:heading:{index:04d}"
            heading_stack.append((heading_level, unit_id))
            lowered = block_text.casefold()
            if re.search(r"\bappendix\b|附录", lowered):
                zone = "operational_appendix"
            elif re.search(r"\bsources?\b|evidence boundary|来源|资料边界", lowered):
                zone = "source_boundary"
            elif re.search(r"\brecheck\b|复核|出发前", lowered):
                zone = "recheck"
        else:
            parent_id = heading_stack[-1][1] if heading_stack else "artifact:document"
            unit_id = f"artifact:{kind}:{index:04d}"
            parent_zone = next(
                (row["zone"] for row in reversed(units) if row["artifact_unit_id"] == parent_id),
                "other",
            )
            if parent_zone in {"operational_appendix", "source_boundary", "recheck"}:
                zone = parent_zone
        units.append(
            {
                "artifact_unit_id": unit_id,
                "parent_unit_id": parent_id,
                "unit_kind": kind,
                "zone": zone,
                "order": order,
                "heading_level": heading_level,
                "locator": f"char:{start}-{end}",
                "start": start,
                "end": end,
                "text": block_text,
                "content_fingerprint": fingerprint_text(block_text),
            }
        )
        order += 1
    artifact_map = {
        "schema_version": "2.0",
        "map_id": map_id,
        "artifact_path": str(path),
        "artifact_format": fmt,
        "artifact_fingerprint": artifact_fp,
        "language": language,
        "units": units,
        "unmapped_ranges": _unmapped_ranges_for_units(text, units),
    }
    artifact_map["map_fingerprint"] = fingerprint(artifact_map)
    require_schema("artifact-map.schema.json", artifact_map, label="ArtifactMap")
    validate_artifact_map_from_text(artifact_map, text)
    return artifact_map



def validate_artifact_map(value: Any) -> dict[str, Any]:
    artifact_map = require_mapping(value, "ArtifactMap")
    require_schema("artifact-map.schema.json", artifact_map, label="ArtifactMap")
    require_exact_fingerprint(artifact_map, "map_fingerprint")
    path = Path(artifact_map["artifact_path"]).expanduser().resolve()
    if not path.is_file():
        raise ValidationError("ArtifactMap artifact is missing")
    data = path.read_bytes()
    actual_fp = "sha256:" + __import__("hashlib").sha256(data).hexdigest()
    if actual_fp != artifact_map["artifact_fingerprint"]:
        raise ValidationError("ArtifactMap is stale for the current bytes")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("ArtifactMap artifact is not valid UTF-8") from exc
    return validate_artifact_map_from_text(artifact_map, text)


def validate_artifact_map_from_text(value: Any, text: str) -> dict[str, Any]:
    """Apply the same partition/fingerprint checks to an explicit text snapshot."""
    artifact_map = require_mapping(value, "ArtifactMap")
    require_schema("artifact-map.schema.json", artifact_map, label="ArtifactMap")
    require_exact_fingerprint(artifact_map, "map_fingerprint")
    actual_fp = "sha256:" + __import__("hashlib").sha256(text.encode("utf-8")).hexdigest()
    if actual_fp != artifact_map["artifact_fingerprint"]:
        raise ValidationError("ArtifactMap is stale for the current bytes")
    units = list(artifact_map["units"])
    unit_ids = set(unique_ids(units, "artifact_unit_id", "artifact unit"))
    documents = [row for row in units if row["unit_kind"] == "document"]
    if len(documents) != 1:
        raise ValidationError("ArtifactMap must contain exactly one document overview unit")
    document = documents[0]
    if document["start"] != 0 or document["end"] != len(text) or document["text"] != text:
        raise ValidationError("ArtifactMap document overview does not cover current bytes")
    if document["locator"] != f"char:0-{len(text)}":
        raise ValidationError("ArtifactMap document locator is stale")

    non_document = sorted(
        (row for row in units if row["unit_kind"] != "document"),
        key=lambda row: (row["start"], row["end"], row["artifact_unit_id"]),
    )
    last_end = 0
    for unit in units:
        start, end = unit["start"], unit["end"]
        if end <= start and unit["unit_kind"] != "document":
            raise ValidationError(f"ArtifactMap unit {unit['artifact_unit_id']} is empty")
        if end < start or end > len(text):
            raise ValidationError(f"ArtifactMap unit {unit['artifact_unit_id']} is out of bounds")
        if unit["text"] != text[start:end]:
            raise ValidationError(f"ArtifactMap unit {unit['artifact_unit_id']} does not match current text")
        if unit["content_fingerprint"] != fingerprint_text(unit["text"]):
            raise ValidationError(f"ArtifactMap unit {unit['artifact_unit_id']} fingerprint is stale")
        if unit["locator"] != f"char:{start}-{end}":
            raise ValidationError(f"ArtifactMap unit {unit['artifact_unit_id']} locator is stale")
        parent = unit["parent_unit_id"]
        if parent is not None and parent not in unit_ids:
            raise ValidationError(f"ArtifactMap unit {unit['artifact_unit_id']} has an unknown parent")
    for unit in non_document:
        if unit["start"] < last_end:
            raise ValidationError("non-document ArtifactMap units overlap")
        last_end = unit["end"]

    # Every non-whitespace character must belong to exactly one real body or
    # structural unit.  The document node is only a summary and is excluded
    # from this coverage calculation.
    expected_gaps = _unmapped_ranges_for_units(text, non_document)
    supplied_gaps = [
        {"start": int(row["start"]), "end": int(row["end"])}
        for row in artifact_map["unmapped_ranges"]
    ]
    if supplied_gaps != expected_gaps:
        raise ValidationError("ArtifactMap unmapped_ranges do not match the current unit partition")
    for gap in supplied_gaps:
        if gap["end"] <= gap["start"]:
            raise ValidationError("ArtifactMap unmapped range must be non-empty")
        if text[gap["start"]:gap["end"]].strip():
            raise ValidationError("ArtifactMap leaves non-whitespace bytes unmapped")

    # Parent links form a rooted tree/forest over the current map.  A forged
    # parent cycle otherwise passes span checks while making reader review
    # unable to establish a stable hierarchy.
    parent_of = {str(row["artifact_unit_id"]): row["parent_unit_id"] for row in units}
    for unit_id in parent_of:
        seen: set[str] = set()
        current: str | None = unit_id
        while current is not None:
            if current in seen:
                raise ValidationError("ArtifactMap parent graph contains a cycle")
            seen.add(current)
            current = parent_of.get(current)
    return artifact_map



__all__ = ["build_artifact_map", "build_artifact_map_from_text", "classify_text_blocks",
           "validate_artifact_map", "validate_artifact_map_from_text"]
