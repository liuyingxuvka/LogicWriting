"""Deterministic reader-facing text extent metrics."""

from __future__ import annotations

import re

from _common import ValidationError


WORD_PATTERN = re.compile(
    r"[^\W\d_]+(?:['’][^\W\d_]+)*|\d+(?:[.,]\d+)*", re.UNICODE
)
SENTENCE_PATTERN = re.compile(r"[.!?。！？](?=\s|$|[\"'”’)\]])")
HAN_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0002fa1f]")


def measure_text(text: str, unit: str, *, metric_id: str | None = None) -> int:
    if not isinstance(text, str):
        raise ValidationError("text extent input must be text")
    if unit == "characters":
        return sum(not char.isspace() for char in text)
    if unit == "words":
        return len(WORD_PATTERN.findall(text))
    if unit == "sentences":
        return len(SENTENCE_PATTERN.findall(text)) or (1 if text.strip() else 0)
    if unit == "user_defined":
        if metric_id == "han_characters":
            return len(HAN_PATTERN.findall(text))
        raise ValidationError(
            "ReaderIntent user_defined extent requires the executable han_characters metric"
        )
    raise ValidationError(f"unsupported ReaderIntent extent unit: {unit}")


__all__ = ["measure_text"]
