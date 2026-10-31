"""Assemble and validate ReaderBrief v2 from current route-owned inputs."""

from __future__ import annotations

from _common import cli_validate, require_mapping, validation_result
from reader_plan import build_reader_brief as _build_reader_brief
from reader_fill import fill_brief_fingerprints


def build_reader_brief(
    *,
    route_decision,
    content_boundaries,
    composition_plan,
    route_composition,
    brief_id,
    request=None,
    research_folder=None,
    research_status=None,
):
    return _build_reader_brief(
        route_decision=route_decision,
        content_boundaries=content_boundaries,
        composition_plan=composition_plan,
        route_composition=route_composition,
        brief_id=brief_id,
        request=request,
        research_folder=research_folder,
        research_status=research_status,
    )


def validate_request(value):
    request = fill_brief_fingerprints(require_mapping(value, "ReaderBrief build request"))
    brief = build_reader_brief(
        route_decision=request.get("route_decision"),
        content_boundaries=request.get("content_boundaries"),
        composition_plan=request.get("composition_plan"),
        route_composition=request.get("route_composition"),
        brief_id=request.get("brief_id"),
        request=request.get('request'),
        research_folder=request.get("research_folder"),
        research_status=request.get("research_status"),
    )
    return validation_result(
        status="current_pass",
        reader_brief=brief,
        reader_brief_fingerprint=brief["brief_fingerprint"],
        composition_plan=request["composition_plan"],
        route_composition=request["route_composition"],
    )


if __name__ == "__main__":
    raise SystemExit(cli_validate(validate_request, __doc__))


__all__ = ["build_reader_brief"]
