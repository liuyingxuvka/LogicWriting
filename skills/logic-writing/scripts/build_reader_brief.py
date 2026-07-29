"""Assemble and validate ReaderBrief v2 from current route-owned inputs."""

from __future__ import annotations

from _common import cli_validate, require_mapping, validation_result
from reader_pipeline import build_reader_brief as _build_reader_brief


def build_reader_brief(
    *,
    route_decision,
    content_boundaries,
    composition_plan,
    route_composition,
    native_dependency_receipt_fingerprints,
    content_authority_fingerprints,
    brief_id,
):
    return _build_reader_brief(
        route_decision=route_decision,
        content_boundaries=content_boundaries,
        composition_plan=composition_plan,
        route_composition=route_composition,
        native_dependency_receipt_fingerprints=native_dependency_receipt_fingerprints,
        content_authority_fingerprints=content_authority_fingerprints,
        brief_id=brief_id,
    )


def validate_request(value):
    request = require_mapping(value, "ReaderBrief build request")
    brief = build_reader_brief(
        route_decision=request.get("route_decision"),
        content_boundaries=request.get("content_boundaries"),
        composition_plan=request.get("composition_plan"),
        route_composition=request.get("route_composition"),
        native_dependency_receipt_fingerprints=request.get(
            "native_dependency_receipt_fingerprints", []
        ),
        content_authority_fingerprints=request.get(
            "content_authority_fingerprints", {}
        ),
        brief_id=request.get("brief_id"),
    )
    return validation_result(
        status="current_pass",
        reader_brief=brief,
        reader_brief_fingerprint=brief["brief_fingerprint"],
    )


if __name__ == "__main__":
    raise SystemExit(cli_validate(validate_request, __doc__))


__all__ = ["build_reader_brief"]
