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


def describe_extent(unit: str, metric_id: str | None = None) -> str:
    """Return the one human-readable description of an executable metric.

    This is intentionally a pure description helper.  It does not count text
    and therefore cannot drift from :func:`measure_text` by maintaining a
    second counter.  Unsupported ReaderIntent units are rejected rather than
    being presented as if the audit layer could measure them.
    """

    if unit == "characters":
        return "非空白字符"
    if unit == "words":
        return "按项目现有词法计数器统计的词项"
    if unit == "sentences":
        return "句子"
    if unit == "user_defined" and metric_id == "han_characters":
        return "纯汉字"
    raise ValidationError(
        f"unsupported ReaderIntent extent metric: unit={unit!r}, metric_id={metric_id!r}"
    )


__all__ = ["measure_text", "describe_extent"]
