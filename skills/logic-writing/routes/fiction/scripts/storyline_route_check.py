#!/usr/bin/env python3
"""Compile one Storyline Design request through the current artifact taxonomy."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TAXONOMY_RELATIVE_PATH = Path("references") / "artifact-taxonomy.json"
REQUIRED_REQUEST_FIELDS = ("artifact_type", "prose_phase")
REQUIRED_DECISION_FIELDS = (
    "route_id",
    "depth_tier",
    "closure_level",
    "prose_phase",
    "required_surfaces",
)


@dataclass(frozen=True)
class RouteBlocked(ValueError):
    """A fail-closed route decision with a stable machine-readable code."""

    code: str
    message: str
    field: str = ""
    value: Any = None

    def __str__(self) -> str:
        return self.message

    def to_issue(self) -> dict[str, Any]:
        issue: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.field:
            issue["field"] = self.field
        if self.value is not None:
            issue["value"] = self.value
        return issue


def default_taxonomy_path() -> Path:
    return Path(__file__).resolve().parents[1] / TAXONOMY_RELATIVE_PATH


def _load_json_object(path: Path, *, kind: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RouteBlocked(
            f"missing_{kind}",
            f"{kind.replace('_', ' ')} file does not exist: {path}",
        ) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RouteBlocked(
            f"invalid_{kind}",
            f"{kind.replace('_', ' ')} file is not readable JSON: {path}: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise RouteBlocked(
            f"invalid_{kind}",
            f"{kind.replace('_', ' ')} must contain one JSON object: {path}",
        )
    return payload


def _load_request(payload: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(payload, Mapping):
        return dict(payload)
    if isinstance(payload, (str, Path)):
        return _load_json_object(Path(payload), kind="route_request")
    raise RouteBlocked(
        "invalid_route_request",
        "route request must be a mapping or a path to one JSON object",
        value=type(payload).__name__,
    )


def _load_taxonomy(taxonomy_path: str | Path | None) -> tuple[dict[str, Any], Path]:
    path = Path(taxonomy_path).resolve() if taxonomy_path is not None else default_taxonomy_path()
    taxonomy = _load_json_object(path, kind="artifact_taxonomy")
    if taxonomy.get("schema_version") != "storyline-design.artifact-taxonomy.v1":
        raise RouteBlocked(
            "unsupported_taxonomy_schema",
            "artifact taxonomy is not the sole current schema",
            field="schema_version",
            value=taxonomy.get("schema_version"),
        )
    return taxonomy, path


def _required_string(request: Mapping[str, Any], field: str) -> str:
    value = request.get(field)
    if not isinstance(value, str) or not value:
        raise RouteBlocked(
            "missing_route_field",
            f"route request requires non-empty string field {field!r}",
            field=field,
            value=value,
        )
    return value


def _string_list(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise RouteBlocked(
            "invalid_taxonomy_contract",
            f"taxonomy field {field!r} must be a list of non-empty strings",
            field=field,
        )
    return list(value)


def _deduplicate(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def compile_route_decision(
    payload: Mapping[str, Any] | str | Path,
    taxonomy_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compile a request into the one current route decision.

    The request must explicitly declare ``artifact_type`` and ``prose_phase``.
    Accepted spellings are exactly the canonical ids and aliases in the current
    taxonomy. Missing or unknown values block; there is no default route.
    """

    request = _load_request(payload)
    taxonomy, _resolved_taxonomy_path = _load_taxonomy(taxonomy_path)
    artifact_type = _required_string(request, "artifact_type")
    prose_phase = _required_string(request, "prose_phase")

    canonical_artifacts = taxonomy.get("canonical_artifacts")
    aliases = taxonomy.get("aliases")
    route_profiles = taxonomy.get("route_profiles")
    if not isinstance(canonical_artifacts, dict) or not isinstance(aliases, dict) or not isinstance(route_profiles, dict):
        raise RouteBlocked(
            "invalid_taxonomy_contract",
            "taxonomy requires canonical_artifacts, aliases, and route_profiles objects",
        )

    alias_used = False
    if artifact_type in canonical_artifacts:
        canonical_artifact = artifact_type
    elif artifact_type in aliases:
        canonical_artifact = aliases[artifact_type]
        alias_used = True
        if canonical_artifact not in canonical_artifacts:
            raise RouteBlocked(
                "invalid_taxonomy_contract",
                f"alias {artifact_type!r} points to unknown canonical artifact {canonical_artifact!r}",
                field="artifact_type",
                value=artifact_type,
            )
    else:
        raise RouteBlocked(
            "unknown_artifact",
            f"artifact type {artifact_type!r} is not canonical and has no explicit current alias",
            field="artifact_type",
            value=artifact_type,
        )

    artifact = canonical_artifacts.get(canonical_artifact)
    if not isinstance(artifact, dict):
        raise RouteBlocked(
            "invalid_taxonomy_contract",
            f"canonical artifact {canonical_artifact!r} must be an object",
        )
    allowed_phases = _string_list(
        artifact.get("allowed_prose_phases"),
        field=f"canonical_artifacts.{canonical_artifact}.allowed_prose_phases",
    )
    if prose_phase not in allowed_phases:
        raise RouteBlocked(
            "unsupported_prose_phase",
            f"artifact {canonical_artifact!r} does not support prose phase {prose_phase!r}",
            field="prose_phase",
            value=prose_phase,
        )

    route_profile_id = artifact.get("route_profile")
    route_profile = route_profiles.get(route_profile_id)
    if not isinstance(route_profile_id, str) or not isinstance(route_profile, dict):
        raise RouteBlocked(
            "invalid_taxonomy_contract",
            f"artifact {canonical_artifact!r} has no valid route profile",
        )
    phase_surfaces = route_profile.get("phase_required_surfaces")
    if not isinstance(phase_surfaces, dict) or prose_phase not in phase_surfaces:
        raise RouteBlocked(
            "invalid_taxonomy_contract",
            f"route profile {route_profile_id!r} does not define phase {prose_phase!r}",
        )
    base_surfaces = _string_list(
        route_profile.get("base_required_surfaces"),
        field=f"route_profiles.{route_profile_id}.base_required_surfaces",
    )
    current_phase_surfaces = _string_list(
        phase_surfaces.get(prose_phase),
        field=f"route_profiles.{route_profile_id}.phase_required_surfaces.{prose_phase}",
    )

    route_id = route_profile.get("route_id")
    base_depth_tier = artifact.get("base_depth_tier")
    closure_level = artifact.get("closure_level")
    if not all(isinstance(value, str) and value for value in (route_id, base_depth_tier, closure_level)):
        raise RouteBlocked(
            "invalid_taxonomy_contract",
            f"artifact {canonical_artifact!r} does not compile to route/depth/closure strings",
        )
    depth_tier = taxonomy.get("final_prose_depth_tier") if prose_phase == "final_prose" else base_depth_tier
    if not isinstance(depth_tier, str) or not depth_tier:
        raise RouteBlocked(
            "invalid_taxonomy_contract",
            "taxonomy does not define the current final-prose depth tier",
        )

    required_surfaces = _deduplicate(base_surfaces + current_phase_surfaces)
    decision = {
        "schema_version": "storyline-design.route-decision.v1",
        "status": "compiled",
        "requested_artifact": artifact_type,
        "canonical_artifact": canonical_artifact,
        "alias_used": alias_used,
        "route_id": route_id,
        "depth_tier": depth_tier,
        "closure_level": closure_level,
        "prose_phase": prose_phase,
        "required_surfaces": required_surfaces,
        "taxonomy_authority": taxonomy.get("authority"),
        "taxonomy_schema_version": taxonomy.get("schema_version"),
        "claim_boundary": taxonomy.get("claim_boundary"),
    }
    missing_decision_fields = [field for field in REQUIRED_DECISION_FIELDS if not decision.get(field)]
    if missing_decision_fields:
        raise RouteBlocked(
            "incomplete_route_decision",
            f"compiled route omitted required fields: {', '.join(missing_decision_fields)}",
        )
    return decision


def blocked_report(exc: RouteBlocked) -> dict[str, Any]:
    return {
        "schema_version": "storyline-design.route-decision.v1",
        "status": "blocked",
        "issues": [exc.to_issue()],
        "claim_boundary": "No route, depth, closure, phase, or required-surface claim is available.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile one Storyline Design route decision.")
    parser.add_argument("request", help="Path to a route-request JSON object.")
    parser.add_argument("--taxonomy", default="", help="Optional explicit current taxonomy path.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = compile_route_decision(args.request, args.taxonomy or None)
        exit_code = 0
    except RouteBlocked as exc:
        report = blocked_report(exc)
        exit_code = 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif exit_code == 0:
        print(
            f"Route compiled: {report['route_id']} / {report['depth_tier']} / "
            f"{report['closure_level']} / {report['prose_phase']}"
        )
    else:
        print(f"Route blocked: {report['issues'][0]['code']}: {report['issues'][0]['message']}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["RouteBlocked", "compile_route_decision", "default_taxonomy_path"]
