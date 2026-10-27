"""Shared reader vocabulary and deterministic prose heuristics; no I/O or lifecycle state."""
from __future__ import annotations

import re

# Content dispositions select what may enter the writer prompt; hidden planner notes never become reader text.
FINAL_OWNERS = ("investigation", "academic-writing", "fiction-writing", "travel-guide")

ROUTE_SCHEMA = {
    "investigation": "investigation-composition.schema.json",
    "academic-writing": "academic-composition.schema.json",
    "fiction-writing": "fiction-composition.schema.json",
    "travel-guide": "travel-composition.schema.json",
}

ROUTE_PROFILE_FIELD = {
    "investigation": "profile",
    "academic-writing": "profile",
    "fiction-writing": "output_room",
    "travel-guide": "guide_kind",
}

PLACEHOLDER = re.compile(
    r"\b(?:TODO|TBD|FIXME|INSERT\s+(?:TEXT|CITATION|EVIDENCE)|LOREM IPSUM)\b|"
    r"\[(?:TODO|TBD|INSERT)[^\]]*\]",
    re.IGNORECASE,
)

WORKFLOW_LEAK = re.compile(
    r"\b(?:SourceGuard|LogicGuard|TraceGuard|FlowGuard|current_pass|"
    r"reader_intent_fingerprint|composition_plan_fingerprint|repair_request)\b|"
    r"(?:本段|本节|本章)(?:旨在|将会|负责)|(?:以下段落|下一节)(?:将会|负责)",
    re.IGNORECASE,
)

SENTENCE_END = re.compile(r"[.!?。！？](?:[\"'”’)\]]*)$")

SENTENCE_MARK = re.compile(r"[.!?。！？](?=\s|$|[\"'”’)\]])")

WRITER_INTERNAL = re.compile(
    r"\b(?:SourceGuard|LogicGuard|TraceGuard|FlowGuard|current_pass|closure|"
    r"reader_intent_fingerprint|composition_plan_fingerprint|model ledger|"
    r"human_review|repair_request|audit)\b", re.IGNORECASE
)

VISIBLE_CONTENT_DISPOSITIONS = {
    "consumed", "body", "note", "appendix", "merged", "implied_by_scope",
}

HIDDEN_CONTENT_DISPOSITIONS = {
    "omitted", "internal", "blocked", "deferred", "conflict",
}

BODY_UNIT_KINDS = {"paragraph", "list", "table", "quote", "scene", "code"}

CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")

LATIN = re.compile(r"[A-Za-z]")
