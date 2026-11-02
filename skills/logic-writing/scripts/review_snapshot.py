"""The text a stamped review read, and the passages that changed since.

`--stamp-review` saves the exact text it stamped beside the judgment. A later
stamp compares that copy with the current text: every body unit that changed
must be quoted again in the review at a changed passage. Re-stamping edited
text without rereading it is refused; the tool computes which words changed,
the reviewer does not declare it.
"""
from __future__ import annotations

import difflib
import hashlib
import re
from typing import Any, Mapping

from _common import ValidationError

BODY_UNIT_KINDS = frozenset({"paragraph", "list", "table", "quote", "scene"})
_TOKEN = re.compile(r"\s+|\w+|[^\w\s]")


def text_fingerprint(text: str) -> str:
    """The artifact fingerprint of these exact bytes, as ArtifactMap computes it."""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def snapshot(amap: Mapping[str, Any]) -> dict[str, str]:
    """The record a stamp saves: the whole current text and its fingerprint."""
    document = next(row for row in amap["units"] if row["unit_kind"] == "document")
    return {"artifact_fingerprint": amap["artifact_fingerprint"], "text": document["text"]}


def snapshot_problems(saved: Any, judgment: Mapping[str, Any] | None) -> list[str]:
    """A saved copy must match its own fingerprint and, for a stamped judgment, be the text it was stamped on."""
    if not isinstance(saved, Mapping) or set(saved) != {"artifact_fingerprint", "text"} or not isinstance(saved["text"], str):
        return ["reviewed_text_invalid (closure-input.json reviewed_text must hold artifact_fingerprint and text)"]
    if text_fingerprint(saved["text"]) != saved["artifact_fingerprint"]:
        return ["reviewed_text_invalid (the saved text does not match its own fingerprint)"]
    if judgment is not None and saved["artifact_fingerprint"] != judgment.get("artifact_fingerprint"):
        return ["reviewed_text_stale (the saved text is not the text the judgment was stamped on)"]
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


def _touches(start: int, end: int, change: tuple[int, int, str], unit: Mapping[str, Any]) -> bool:
    first, last, _ = change
    if first == last:  # a deletion: the quote spans the place where the words were, or reaches it at the unit's edge
        return start < first < end or first == end == unit["end"] or first == start == unit["start"]
    return start < last and end > first


def _short(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= 60 else text[:57] + "..."


def reread_problems(saved: Any, judgment: Mapping[str, Any], amap: Mapping[str, Any], *, stamped: bool) -> list[str]:
    """Why a new stamp would certify changed text the review has not quoted again; [] when it may stamp.

    `saved` is the copy the earlier stamp kept (None before the first stamp). `stamped` says whether the
    judgment already carries a stamp, so a review stamped before copies were kept is recognised.
    """
    current = amap["artifact_fingerprint"]
    if saved is None:
        if stamped and judgment.get("artifact_fingerprint") != current:
            return [f"review_text_unknown:{judgment.get('judgment_id', 'unknown')} (this review was stamped without a saved copy "
                    "of the text it read, and the text has changed, so the changed passages cannot be found; reread the whole "
                    "piece, write its reverse outline again, remove the judgment's *_fingerprint fields and stamp it as a new review)"]
        return []
    problems = snapshot_problems(saved, judgment if stamped else None)
    if problems:
        return problems
    if saved["artifact_fingerprint"] == current:
        return []
    spans = changed_spans(saved["text"], snapshot(amap)["text"])
    quotes: dict[str, list[tuple[int, int]]] = {}
    units = {row["artifact_unit_id"]: row for row in amap["units"]}
    for row in judgment.get("reverse_outline") or []:
        evidence = row.get("evidence") if isinstance(row, Mapping) else None
        unit = units.get(row.get("artifact_unit_id")) if isinstance(row, Mapping) else None
        excerpt = evidence.get("excerpt") if isinstance(evidence, Mapping) else None
        if unit is None or not isinstance(excerpt, str) or not excerpt:
            continue
        found = unit["text"].find(excerpt)
        while found >= 0:
            quotes.setdefault(unit["artifact_unit_id"], []).append((unit["start"] + found, unit["start"] + found + len(excerpt)))
            found = unit["text"].find(excerpt, found + 1)
    problems = []
    for unit in sorted((row for row in amap["units"] if row["unit_kind"] in BODY_UNIT_KINDS), key=lambda row: row["start"]):
        changes = [change for change in spans if unit["start"] <= change[0] <= unit["end"] and change[1] <= unit["end"]
                   and (change[0] < unit["end"] or change[0] == change[1])]
        if not changes or any(_touches(start, end, change, unit) for start, end in quotes.get(unit["artifact_unit_id"], ())
                              for change in changes):
            continue
        first = changes[0]
        read = f', where it read "{_short(first[2])}"' if first[2].strip() else ""
        problems.append(f"review_not_reread:{unit['artifact_unit_id']} (this unit changed after the review was stamped, "
                        f"at char:{first[0]}-{first[1]}{read}; reread the unit and quote its new wording in this unit's "
                        "reverse_outline evidence excerpt, then stamp again)")
    return problems


def require_reread(saved: Any, judgment: Mapping[str, Any], amap: Mapping[str, Any], *, stamped: bool) -> None:
    problems = reread_problems(saved, judgment, amap, stamped=stamped)
    if problems:
        raise ValidationError("; ".join(problems))


__all__ = ["changed_spans", "reread_problems", "require_reread", "snapshot", "snapshot_problems", "text_fingerprint"]
