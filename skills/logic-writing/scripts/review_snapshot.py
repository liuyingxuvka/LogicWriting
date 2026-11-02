"""The text a stamped review read, and the passages that changed since.

`--stamp-review` saves the exact text it stamped beside the judgment, sealed
with its own fingerprint. A later stamp compares that copy with the current
text: every unit that changed (body, heading or title) must be quoted again in
the review at a changed passage. The tool computes which words changed; the
reviewer does not declare it. Without a saved copy there is nothing to compare,
so the stamp must be declared a first review (`--first-review`), and the record
and the closure say so.
"""
from __future__ import annotations

import difflib
import hashlib
import re
from typing import Any, Mapping

from _common import ValidationError, own_fingerprint

RECORD_FIELDS = frozenset({"artifact_fingerprint", "text", "basis", "changed_units", "reviewed_text_fingerprint"})
BASES = ("first_review", "compared")
_TOKEN = re.compile(r"\s+|\w+|[^\w\s]")


def text_fingerprint(text: str) -> str:
    """The artifact fingerprint of these exact bytes, as ArtifactMap computes it."""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def snapshot(amap: Mapping[str, Any], *, basis: str, changed_units: list[str]) -> dict[str, Any]:
    """The record a stamp saves: the whole current text, how this stamp was justified, and its own seal."""
    document = next(row for row in amap["units"] if row["unit_kind"] == "document")
    record = {"artifact_fingerprint": amap["artifact_fingerprint"], "text": document["text"],
              "basis": basis, "changed_units": list(changed_units)}
    record["reviewed_text_fingerprint"] = own_fingerprint(record, "reviewed_text_fingerprint")
    return record


def snapshot_problems(saved: Any, judgment: Mapping[str, Any] | None) -> list[str]:
    """A saved copy must be whole, sealed, match its own text and, for a stamped judgment, be the text it was stamped on."""
    if not isinstance(saved, Mapping) or set(saved) != RECORD_FIELDS or not isinstance(saved["text"], str):
        return ["reviewed_text_invalid:closure-input.json (reviewed_text must hold artifact_fingerprint, text, basis, "
                "changed_units and reviewed_text_fingerprint, as --stamp-review writes it)"]
    if saved["basis"] not in BASES or not isinstance(saved["changed_units"], list):
        return ["reviewed_text_invalid:closure-input.json (the saved copy names no known basis or changed units)"]
    if saved["reviewed_text_fingerprint"] != own_fingerprint(dict(saved), "reviewed_text_fingerprint"):
        return ["reviewed_text_invalid:closure-input.json (the saved copy was changed after --stamp-review wrote it)"]
    if text_fingerprint(saved["text"]) != saved["artifact_fingerprint"]:
        return ["reviewed_text_invalid:closure-input.json (the saved text does not match its own fingerprint)"]
    if judgment is not None and saved["artifact_fingerprint"] != judgment.get("artifact_fingerprint"):
        return ["reviewed_text_stale:closure-input.json (the saved text is not the text the judgment was stamped on)"]
    return []


def changed_spans(old: str, new: str) -> list[tuple[int, int, str]]:
    """(start, end, old wording) in the new text for each word-level change; a deletion has start == end.

    Changes that only move whitespace need no reread and are left out.
    """
    old_tokens = [match for match in _TOKEN.finditer(old)]
    new_tokens = [match for match in _TOKEN.finditer(new)]
    matcher = difflib.SequenceMatcher(None, [m.group() for m in old_tokens], [m.group() for m in new_tokens], autojunk=False)
    spans = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        before = old[old_tokens[i1].start():old_tokens[i2 - 1].end()] if i2 > i1 else ""
        after = new[new_tokens[j1].start():new_tokens[j2 - 1].end()] if j2 > j1 else ""
        if not before.strip() and not after.strip():
            continue
        if j2 > j1:
            start, end = new_tokens[j1].start(), new_tokens[j2 - 1].end()
        else:
            start = end = new_tokens[j1].start() if j1 < len(new_tokens) else len(new)
        spans.append((start, end, before))
    return spans


def _units(amap: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Every unit a reader reads: paragraphs, lists, tables, quotes, scenes, headings and the title."""
    return sorted((row for row in amap["units"] if row["unit_kind"] != "document"), key=lambda row: row["start"])


def changed_units(old: str, amap: Mapping[str, Any]) -> dict[str, list[tuple[int, int, str]]]:
    """For each unit, the changes since `old` that lie in it; a change crossing units belongs to each of them.

    A deletion belongs to the unit it sits in or at the edge of, else to the unit just before it (or after it,
    at the very start). Nothing outside units is skipped: the gaps between units hold only whitespace.
    """
    units = _units(amap)
    owners: dict[str, list[tuple[int, int, str]]] = {}
    for change in changed_spans(old, next(row for row in amap["units"] if row["unit_kind"] == "document")["text"]):
        start, end, _ = change
        if start < end:
            touched = [unit for unit in units if unit["start"] < end and unit["end"] > start]
        else:
            touched = [unit for unit in units if unit["start"] <= start <= unit["end"]]
        if not touched and units:
            before = [unit for unit in units if unit["end"] <= start]
            touched = [before[-1] if before else units[0]]
        for unit in touched:
            owners.setdefault(unit["artifact_unit_id"], []).append(change)
    return owners


def _touches(quote: tuple[int, int], change: tuple[int, int, str], unit: Mapping[str, Any]) -> bool:
    """A quote rereads a change when it overlaps the changed words inside the unit, or spans the place of a removal."""
    start, end = quote
    first, last = max(change[0], unit["start"]), min(change[1], unit["end"])
    if first < last:
        return start < last and end > first
    point = min(max(change[0], unit["start"]), unit["end"])
    return start < point < end or point == end == unit["end"] or point == start == unit["start"]


def _quotes(judgment: Mapping[str, Any], amap: Mapping[str, Any]) -> dict[str, list[tuple[int, int]]]:
    """Where the review's evidence (reverse outline, defects, strengths) quotes each unit of the current text."""
    units = {row["artifact_unit_id"]: row for row in amap["units"]}
    quotes: dict[str, list[tuple[int, int]]] = {}
    for kind in ("reverse_outline", "defects", "strengths"):
        for row in judgment.get(kind) or []:
            evidence = row.get("evidence") if isinstance(row, Mapping) else None
            if not isinstance(evidence, Mapping):
                continue
            unit, excerpt = units.get(evidence.get("artifact_unit_id")), evidence.get("excerpt")
            if unit is None or not isinstance(excerpt, str) or not excerpt:
                continue
            found = unit["text"].find(excerpt)
            while found >= 0:
                quotes.setdefault(unit["artifact_unit_id"], []).append((unit["start"] + found, unit["start"] + found + len(excerpt)))
                found = unit["text"].find(excerpt, found + 1)
    return quotes


def _short(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= 60 else text[:57] + "..."


def review_record(saved: Any, judgment: Mapping[str, Any], amap: Mapping[str, Any], *, first_review: bool) -> dict[str, Any]:
    """The saved copy a new stamp writes, or ValidationError naming why the review may not be stamped.

    `saved` is closure-input.json's reviewed_text (None when there is none) and `judgment` the review as it
    stands before this stamp. With a saved copy the tool compares it with the current text, and each changed
    unit must be quoted again at a changed passage. Without one nothing can be compared: only a declared
    first review may be stamped, and the record says so.
    """
    identity = judgment.get("judgment_id", "unknown")
    if saved is None:
        if first_review:
            return snapshot(amap, basis="first_review", changed_units=[])
        if judgment.get("artifact_fingerprint"):
            raise ValidationError(
                f"review_text_unknown:{identity} (this review was stamped without a saved copy of the text it read, by "
                "LogicWriting 4.1 or earlier or because its copy was deleted, so what changed since cannot be computed; "
                "reread the whole piece, update the reverse outline from that reading, then stamp with --stamp-review --first-review)")
        raise ValidationError(
            f"review_first_undeclared:{identity} (no saved copy of an earlier stamp of this piece, so nothing can be "
            "compared; if this is the piece's first review, read all of it and stamp with --stamp-review --first-review; "
            "if it was stamped before, restore the reviewed_text that stamp wrote in closure-input.json)")
    if first_review:
        raise ValidationError(
            f"review_copy_exists:{identity} (closure-input.json keeps the text the last stamp read, so the tool compares "
            "it with the current text; stamp without --first-review and quote each changed unit again)")
    problems = snapshot_problems(saved, judgment if judgment.get("artifact_fingerprint") else None)
    if problems:
        raise ValidationError("; ".join(problems))
    if saved["artifact_fingerprint"] == amap["artifact_fingerprint"]:
        return dict(saved)
    quotes = _quotes(judgment, amap)
    owners = changed_units(saved["text"], amap)
    units = {row["artifact_unit_id"]: row for row in amap["units"]}
    problems = []
    for unit in _units(amap):
        changes = owners.get(unit["artifact_unit_id"])
        if not changes or any(_touches(quote, change, unit) for quote in quotes.get(unit["artifact_unit_id"], ())
                              for change in changes):
            continue
        first = changes[0]
        read = f', where it read "{_short(first[2])}"' if first[2].strip() else ""
        problems.append(f"review_not_reread:{unit['artifact_unit_id']} (this {unit['unit_kind']} changed after the review was "
                        f"stamped, at char:{first[0]}-{first[1]}{read}; reread it and quote its new wording in review "
                        "evidence for this unit (its reverse_outline row; a heading or the title may have its own row), "
                        "then stamp again)")
    if problems:
        raise ValidationError("; ".join(problems))
    return snapshot(amap, basis="compared", changed_units=sorted(owners, key=lambda key: units[key]["start"]))


__all__ = ["changed_spans", "changed_units", "review_record", "snapshot", "snapshot_problems", "text_fingerprint"]
