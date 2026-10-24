"""Shared primitive checks; native fiction reporters keep their own context."""
from __future__ import annotations

from typing import Any

PLACEHOLDER_VALUES = {"tbd", "todo", "n/a", "na", "none", "unknown", "placeholder", "fill later", "fix later", "..."}


def type_name(expected):
    return " or ".join(t.__name__ for t in expected) if isinstance(expected, tuple) else expected.__name__


def normalize_text(value):
    return " ".join(value.strip().lower().split()) if isinstance(value, str) else ""


def is_blank_or_placeholder(value):
    normalized = normalize_text(value)
    return (not normalized or normalized in PLACEHOLDER_VALUES or normalized.startswith(("todo", "tbd"))
            or (normalized.startswith("[") and normalized.endswith("]")))


def check_type(value, expected, path, reporter, *context):
    if isinstance(value, expected):
        return True
    reporter.error("invalid_type", path, f"Expected {type_name(expected)}, got {type(value).__name__}.", *context)
    return False


def check_enum(value, allowed, path, reporter, *context, code="invalid_enum"):
    if isinstance(value, str) and value in allowed:
        return
    reporter.error(code, path, f"Value {value!r} is not one of: {', '.join(sorted(allowed))}.", *context)
