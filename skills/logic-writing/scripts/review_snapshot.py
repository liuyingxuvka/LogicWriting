"""The text a stamped review read, and the passages that changed since.

`--stamp-review` saves the exact text it stamped beside the judgment, sealed
with its own fingerprint. A later stamp compares that copy with the current
text: for every unit that changed (body, heading or title) the review must quote
the whole sentence that holds the change. The tool computes which words changed
and which sentence holds them; the reviewer does not declare it.

Without a saved copy there is nothing to compare. A review that was never
stamped is then declared a first review (`--first-review`). A review stamped
before (a stamp field, or an evidence excerpt fingerprint a stamp computed, is
still in it) is never a first review: its copy is saved again only when its own
sealed stamp names exactly the current text (basis `restored`); otherwise the
copy must be brought back. The record and the closure say which basis applies.
"""
from __future__ import annotations

import difflib
import hashlib
import re
from typing import Any, Mapping

from _common import ValidationError, fingerprint_text, own_fingerprint

RECORD_FIELDS = frozenset({"artifact_fingerprint", "text", "basis", "changed_units", "reviewed_text_fingerprint"})
BASES = ("first_review", "compared", "restored")
# What a stamp writes into the judgment; a review carrying any of them was stamped before.
STAMP_FIELDS = ("reader_intent_fingerprint", "reader_brief_fingerprint", "composition_plan_fingerprint",
                "artifact_map_fingerprint", "shared_writing_contract_fingerprint", "deterministic_audit_fingerprint",
                "route_audit_fingerprint", "artifact_fingerprint", "evaluation_profile_fingerprint", "judgment_fingerprint")
_TOKEN = re.compile(r"\s+|\w+|[^\w\s]")
_WORD = re.compile(r"\w+")
# A sentence ends after . ! ? (with closing quotes or brackets) before a space, after a CJK stop, or at a line end.
_SENTENCE_END = re.compile(r"[.!?][\"'\u201d\u2019)\]]*(?=\s|$)|[\u3002\uff01\uff1f]|\n")


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


def _sentences(text: str) -> list[tuple[int, int, int, int]]:
    """(start, end, first word start, last word end) of each sentence of a unit's text that holds a word."""
    cuts = [0, *(match.end() for match in _SENTENCE_END.finditer(text)), len(text)]
    spans = []
    for start, end in zip(cuts, cuts[1:]):
        words = list(_WORD.finditer(text, start, end))
        if words:
            spans.append((start, end, words[0].start(), words[-1].end()))
    return spans


def required_quote(change: tuple[int, int, str], unit: Mapping[str, Any]) -> tuple[int, int]:
    """The span of the current text a quote must cover to reread this change in this unit.

    That is the whole sentence (or sentences) holding the changed words, from its first word to its last, and
    the changed words themselves. A removal needs the sentence it sits in, else the sentence just before it (or
    after it, at the very start). A unit with no word at all needs the changed span only.
    """
    text, base = unit["text"], unit["start"]
    sentences = _sentences(text)
    first, last = max(change[0], base) - base, min(change[1], unit["end"]) - base
    if first < last:
        while first < last and text[first].isspace():
            first += 1
        while last > first and text[last - 1].isspace():
            last -= 1
        held = [span for span in sentences if span[0] < max(last, first + 1) and span[1] > first]
        if held:
            first, last = min(first, held[0][2]), max(last, held[-1][3])
        return base + first, base + last
    held = ([span for span in sentences if span[0] <= first < span[1] or span[2] <= first <= span[3]]
            or [span for span in sentences if span[1] <= first][-1:] or sentences[:1])
    return (base + held[0][2], base + held[0][3]) if held else (base + first, base + first)


def _quotes(judgment: Mapping[str, Any], amap: Mapping[str, Any]) -> dict[str, list[tuple[int, int]]]:
    """Where the review's evidence (reverse outline, defects, strengths) quotes each unit of the current text.

    The judgment has passed the stamp's validation, so every evidence row names a current unit and quotes it.
    """
    units = {row["artifact_unit_id"]: row for row in amap["units"]}
    quotes: dict[str, list[tuple[int, int]]] = {}
    for kind in ("reverse_outline", "defects", "strengths"):
        for row in judgment[kind]:
            unit, excerpt = units[row["evidence"]["artifact_unit_id"]], row["evidence"]["excerpt"]
            found = unit["text"].find(excerpt)
            while found >= 0:
                quotes.setdefault(unit["artifact_unit_id"], []).append((unit["start"] + found, unit["start"] + found + len(excerpt)))
                found = unit["text"].find(excerpt, found + 1)
    return quotes


def _short(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= 60 else text[:57] + "..."


def _earlier_stamp(judgment: Mapping[str, Any]) -> bool:
    """Whether a stamp has bound this review before: a stamp field, or an evidence excerpt fingerprint that matches its
    excerpt (a stamp computes it; nobody types a sha256), is still in the judgment."""
    if any(judgment.get(field) for field in STAMP_FIELDS):
        return True
    # The stamp has validated this review's evidence, so every row has its evidence and excerpt.
    rows = [row["evidence"] for kind in ("reverse_outline", "defects", "strengths") for row in judgment[kind]]
    return any(row.get("excerpt_fingerprint") == fingerprint_text(row["excerpt"]) for row in rows)


def _without_copy(judgment: Mapping[str, Any], amap: Mapping[str, Any], *, first_review: bool) -> dict[str, Any]:
    """A review stamped before whose saved copy is missing: saved again only on the text its sealed stamp names."""
    identity = judgment["judgment_id"]
    named = judgment.get("artifact_fingerprint")
    sealed = judgment.get("judgment_fingerprint") == own_fingerprint(dict(judgment), "judgment_fingerprint")
    if sealed and named == amap["artifact_fingerprint"]:
        if first_review:
            raise ValidationError(
                f"review_not_first:{identity} (this review was stamped before, so it is not a first review; the text "
                "is the one that stamp read, so stamp without that option and its copy is saved again)")
        return snapshot(amap, basis="restored", changed_units=[])
    if sealed:
        why = (f"it was stamped on other text ({named}), and closure-input.json keeps no copy of that text (it was "
               "stamped by LogicWriting 4.1 or earlier, or the copy was deleted), so what changed since cannot be computed")
        way = ("restore the reviewed_text that stamp wrote in closure-input.json (for example from version control), "
               f"or put back the text it was stamped on ({named}), stamp that, then make the edits again and stamp")
    else:
        why = ("the review was changed after that stamp and closure-input.json keeps no copy of the text it read, so "
               "neither that text nor what changed since can be known")
        way = "restore closure-input.json as that stamp wrote it (for example from version control)"
    if first_review:
        raise ValidationError(f"review_not_first:{identity} (this review was stamped before, so it is not a first "
                              f"review; {why}; {way}; otherwise this review cannot be stamped again)")
    raise ValidationError(f"review_text_unknown:{identity} ({why}; {way}; otherwise this review cannot be stamped again)")


def review_record(saved: Any, judgment: Mapping[str, Any], amap: Mapping[str, Any], *, first_review: bool) -> dict[str, Any]:
    """The saved copy a new stamp writes, or ValidationError naming why the review may not be stamped.

    `saved` is closure-input.json's reviewed_text (None when there is none) and `judgment` the review as it
    stands before this stamp. With a saved copy the tool compares it with the current text, and each changed
    unit must be quoted again across the whole sentence that holds the change. Without one nothing can be
    compared: a review never stamped may be stamped only as a declared first review, and a review stamped
    before only on the text its sealed stamp names.
    """
    identity = judgment["judgment_id"]
    if saved is None:
        if _earlier_stamp(judgment):
            return _without_copy(judgment, amap, first_review=first_review)
        if first_review:
            return snapshot(amap, basis="first_review", changed_units=[])
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
        if not changes:
            continue
        unread = [(change, required_quote(change, unit)) for change in changes]
        unread = [(change, need) for change, need in unread
                  if not any(start <= need[0] and end >= need[1] for start, end in quotes.get(unit["artifact_unit_id"], ()))]
        if not unread:
            continue
        (first, need) = unread[0]
        read = f', where it read "{_short(first[2])}"' if first[2].strip() else ""
        problems.append(f"review_not_reread:{unit['artifact_unit_id']} (this {unit['unit_kind']} changed after the review was "
                        f"stamped, at char:{first[0]}-{first[1]}{read}; reread it and quote the whole sentence that holds "
                        f"the change (char:{need[0]}-{need[1]}) in review evidence for this unit (its reverse_outline row; "
                        "a heading or the title may have its own row), then stamp again)")
    if problems:
        raise ValidationError("; ".join(problems))
    return snapshot(amap, basis="compared", changed_units=sorted(owners, key=lambda key: units[key]["start"]))


def basis_words(basis: Mapping[str, Any]) -> str:
    """How the stamped review covers the current text, in the words closure and run_chain print."""
    if basis["basis"] == "first_review":
        return "stamped as a first review"
    if basis["basis"] == "restored":
        return "re-stamped on the text its earlier stamp named"
    if basis["changed_units"]:
        return "re-stamped after quoting each changed unit again: " + ", ".join(basis["changed_units"])
    return "re-stamped after comparing the text with the copy the last stamp read"


__all__ = ["basis_words", "changed_spans", "changed_units", "required_quote", "review_record", "snapshot",
           "snapshot_problems", "text_fingerprint"]
