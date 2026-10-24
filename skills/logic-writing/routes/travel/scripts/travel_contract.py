from __future__ import annotations

import json
import copy
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from _common import read_worldguard_report


SCHEMA_VERSION = "travel-story-planner.plan.v2"
CLAIM_LEVELS = ("initial_plan", "bookable", "day_of")
DATE_RELATIONS = {"past", "near_future", "day_of", "far_future", "undated"}
WEATHER_SOURCE_CLASSES = {"weather_forecast", "weather_historical", "weather_climate", "weather_alert"}
WEATHER_MODES_BY_DATE = {
    "past": {"historical_observed", "archive"},
    "near_future": {"forecast", "forecast_alert", "mixed"},
    "day_of": {"forecast_alert", "mixed"},
    "far_future": {"climate"},
    "undated": {"climate"},
}
REQUIRED_SOURCE_CLASSES = {
    "official_facts",
    "transport_map",
    "booking_price",
    "traveler_experience",
    "negative_experience",
    "accessibility_safety",
    "fallback_source",
}
REQUIRED_FIT_DIMENSIONS = {
    "age",
    "stamina",
    "companions",
    "interests",
    "pace",
    "rest",
    "budget",
    "safety",
    "weather_resilience",
    "fallback_fit",
    "food_fit",
}
CANDIDATE_STATUSES = {"candidate", "usable", "partial", "gap", "rejected", "fallback_only"}
ROUTE_STATUSES = {"pass", "partial", "gap", "fail", "stale", "blocked"}
FIT_STATUSES = {"pass", "downgraded", "revise", "human_review", "blocked"}


def issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def nonempty(value: Any) -> bool:
    return value not in (None, "", [])


def require_fields(
    row: dict[str, Any],
    fields: Iterable[str],
    prefix: str,
    label: str,
    issues: list[dict[str, str]],
) -> None:
    for field in fields:
        if field not in row or not nonempty(row.get(field)):
            issues.append(issue(f"{prefix}.{field}.missing", f"{label} is missing {field}."))


def index_rows(
    rows: list[Any],
    key: str,
    prefix: str,
    issues: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for position, raw in enumerate(rows):
        if not isinstance(raw, dict):
            issues.append(issue(f"{prefix}.row.invalid", f"{prefix} row {position} must be an object."))
            continue
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            issues.append(issue(f"{prefix}.{key}.missing", f"{prefix} row {position} is missing {key}."))
            continue
        if value in index:
            issues.append(issue(f"{prefix}.{key}.duplicate", f"Duplicate {key} {value}."))
            continue
        index[value] = raw
    return index


def _parse_iso_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _claim_rank(level: str) -> int:
    return {"initial_plan": 0, "bookable": 1, "day_of": 2}.get(level, -1)


def validate_trip_context(data: dict[str, Any], issues: list[dict[str, str]]) -> dict[str, Any]:
    context = as_dict(data.get("trip_context"))
    if not context:
        issues.append(issue("trip_context.missing", "trip_context is required."))
        return {}
    require_fields(
        context,
        (
            "trip_id",
            "destination",
            "planning_as_of",
            "timezone",
            "date_relation",
            "trip_days",
            "overnight",
            "nights",
            "requested_claim_level",
            "evaluation_mode",
        ),
        "trip_context",
        "trip_context",
        issues,
    )
    planning_as_of = _parse_iso_datetime(context.get("planning_as_of"))
    if planning_as_of is None:
        issues.append(issue("trip_context.planning_as_of.invalid", "planning_as_of must be an ISO-8601 timestamp."))
    relation = context.get("date_relation")
    if relation not in DATE_RELATIONS:
        issues.append(issue("trip_context.date_relation.invalid", "date_relation is invalid."))
    requested = context.get("requested_claim_level")
    if requested not in CLAIM_LEVELS:
        issues.append(issue("trip_context.requested_claim_level.invalid", "requested_claim_level is invalid."))
    days = context.get("trip_days")
    nights = context.get("nights")
    if not isinstance(days, int) or days < 1:
        issues.append(issue("trip_context.trip_days.invalid", "trip_days must be a positive integer."))
    if not isinstance(nights, int) or nights < 0:
        issues.append(issue("trip_context.nights.invalid", "nights must be a non-negative integer."))
    if isinstance(days, int) and isinstance(nights, int):
        if bool(context.get("overnight")) != (nights > 0):
            issues.append(issue("trip_context.overnight.inconsistent", "overnight must agree with nights."))
        if nights > max(days - 1, 0):
            issues.append(issue("trip_context.nights.inconsistent", "nights cannot exceed trip_days - 1."))
    start = _parse_iso_date(context.get("start_date"))
    end = _parse_iso_date(context.get("end_date"))
    if relation not in {"undated"}:
        if start is None or end is None:
            issues.append(issue("trip_context.dates.missing", "Dated trip contexts require valid start_date and end_date."))
        elif end < start:
            issues.append(issue("trip_context.dates.order", "end_date precedes start_date."))
        elif isinstance(days, int) and (end - start).days + 1 != days:
            issues.append(issue("trip_context.trip_days.date_mismatch", "trip_days does not match start/end dates."))
        if start is not None and end is not None and planning_as_of is not None:
            as_of_date = planning_as_of.date()
            expected_relation = (
                "past"
                if end < as_of_date
                else "day_of"
                if start <= as_of_date <= end
                else "far_future"
                if start > as_of_date + timedelta(days=30)
                else "near_future"
            )
            if relation != expected_relation:
                issues.append(issue("trip_context.date_relation.mismatch", f"date_relation must be {expected_relation} for the declared planning timestamp and dates."))
    elif context.get("start_date") or context.get("end_date"):
        issues.append(issue("trip_context.undated.has_dates", "Undated context cannot carry start/end dates."))
    day_ids = as_list(context.get("day_ids"))
    if not isinstance(days, int) or len(day_ids) != days or len(set(day_ids)) != len(day_ids):
        issues.append(issue("trip_context.day_ids.invalid", "day_ids must uniquely cover every trip day."))
    return context


def validate_traveler_profile(data: dict[str, Any], issues: list[dict[str, str]]) -> dict[str, Any]:
    profile = as_dict(data.get("traveler_profile"))
    if not profile:
        issues.append(issue("traveler_profile.missing", "traveler_profile is required."))
        return {}
    require_fields(
        profile,
        (
            "traveler_count",
            "ages",
            "companions",
            "stamina",
            "walking_tolerance_km",
            "stairs_or_hills_tolerance",
            "transit_tolerance",
            "budget_level",
            "interests",
            "must_avoid",
            "food_constraints",
            "accessibility_needs",
            "safety_constraints",
            "pace",
            "style",
        ),
        "traveler_profile",
        "traveler_profile",
        issues,
    )
    count = profile.get("traveler_count")
    ages = as_list(profile.get("ages"))
    if not isinstance(count, int) or count < 1 or len(ages) != count:
        issues.append(issue("traveler_profile.ages.count_mismatch", "ages must contain one entry per traveler."))
    if any(not isinstance(age, int) or isinstance(age, bool) or age < 0 or age > 120 for age in ages):
        issues.append(issue("traveler_profile.ages.invalid", "Every traveler age must be an integer from 0 through 120."))
    tolerance = profile.get("walking_tolerance_km")
    if not isinstance(tolerance, (int, float)) or tolerance < 0:
        issues.append(issue("traveler_profile.walking_tolerance_km.invalid", "walking_tolerance_km must be non-negative."))
    return profile


def validate_source_portfolio(
    data: dict[str, Any],
    context: dict[str, Any],
    issues: list[dict[str, str]],
) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]]]:
    portfolio = as_dict(data.get("source_portfolio"))
    if not portfolio:
        issues.append(issue("source_portfolio.missing", "source_portfolio is required."))
        return {}, {}
    legacy_keys = sorted(key for key in portfolio if key != "sources")
    if legacy_keys:
        issues.append(issue("source_portfolio.former_shape", "Former class-array source authority is forbidden: " + ", ".join(legacy_keys)))
    sources = as_list(portfolio.get("sources"))
    source_index = index_rows(sources, "source_id", "source_portfolio", issues)
    classes: dict[str, set[str]] = {}
    for source_id, row in source_index.items():
        require_fields(
            row,
            (
                "source_class",
                "source_date",
                "coverage_period",
                "locator",
                "content_sha256",
                "can_support",
                "cannot_support",
                "checked_on",
                "next_action",
            ),
            "source_portfolio.source",
            f"Source {source_id}",
            issues,
        )
        source_class = row.get("source_class")
        if isinstance(source_class, str):
            classes.setdefault(source_class, set()).add(source_id)
        checked = _parse_iso_date(row.get("checked_on"))
        planning = _parse_iso_datetime(context.get("planning_as_of"))
        if checked is None or planning is not None and checked > planning.date():
            issues.append(issue("source_portfolio.checked_on.invalid", f"Source {source_id} needs a valid check date no later than planning_as_of."))
        if not as_list(row.get("can_support")) or not as_list(row.get("cannot_support")):
            issues.append(issue("source_portfolio.support_boundary.missing", f"Source {source_id} needs positive and negative support boundaries."))
    required = set(REQUIRED_SOURCE_CLASSES)
    if context.get("overnight"):
        required.add("hotel_lodging")
    missing = sorted(required - set(classes))
    if missing:
        issues.append(issue("source_portfolio.missing_classes", "Missing source classes: " + ", ".join(missing)))
    if not (WEATHER_SOURCE_CLASSES & set(classes)):
        issues.append(issue("source_portfolio.weather_class.missing", "A current weather source class is required."))
    return source_index, classes


def validate_candidates(
    data: dict[str, Any],
    context: dict[str, Any],
    source_index: dict[str, dict[str, Any]],
    issues: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    pool = as_dict(data.get("experience_candidate_pool"))
    candidates = as_list(pool.get("candidates"))
    candidate_index = index_rows(candidates, "candidate_id", "experience_candidate_pool", issues)
    classes = {str(row.get("class")) for row in candidate_index.values() if row.get("class")}
    required = {"attraction", "restaurant", "transport", "fallback"}
    if context.get("overnight"):
        required.add("hotel")
    if int(context.get("trip_days", 1) or 1) > 1:
        required |= {"shop", "rest"}
    missing = sorted(required - classes)
    if missing:
        issues.append(issue("experience_candidate_pool.missing_class", "Missing candidate classes: " + ", ".join(missing)))
    for candidate_id, row in candidate_index.items():
        require_fields(
            row,
            (
                "class",
                "name_or_area",
                "trip_role",
                "why_worth_considering",
                "why_may_be_bad_fit",
                "best_for",
                "avoid_when",
                "source_ids",
                "source_roles",
                "negative_signal_ids",
                "world_check_id",
                "freshness",
                "candidate_status",
                "next_action",
            ),
            "experience_candidate_pool.candidate",
            f"Candidate {candidate_id}",
            issues,
        )
        source_ids = [str(value) for value in as_list(row.get("source_ids"))]
        unknown_sources = sorted(set(source_ids) - set(source_index))
        if unknown_sources:
            issues.append(issue("experience_candidate_pool.source.unknown", f"Candidate {candidate_id} references unknown sources: {', '.join(unknown_sources)}"))
        actual_roles = {str(source_index[source_id].get("source_class")) for source_id in source_ids if source_id in source_index}
        declared_roles = {str(value) for value in as_list(row.get("source_roles"))}
        if actual_roles != declared_roles:
            issues.append(issue("experience_candidate_pool.source_roles.mismatch", f"Candidate {candidate_id} source_roles do not match referenced source classes."))
        if row.get("candidate_status") not in CANDIDATE_STATUSES:
            issues.append(issue("experience_candidate_pool.status.invalid", f"Candidate {candidate_id} has invalid status."))
    return candidate_index


def _world_check_covers(check, kind, identity, context):
    return bool(check) and ((check.get("target_type") == kind and check.get("target_id") == identity)
        or (check.get("target_type") == "trip" and check.get("target_id") == context.get("trip_id")))


def validate_world_checks(
    data: dict[str, Any],
    candidate_index: dict[str, dict[str, Any]],
    issues: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    checks = as_list(as_dict(data.get("world_feasibility")).get("checks"))
    world_index = index_rows(checks, "world_check_id", "world_feasibility", issues)
    for check_id, row in world_index.items():
        require_fields(
            row,
            ("target_type", "target_id", "guards_checked", "worldguard_report", "missing_slots", "counterexamples", "boundary", "next_action"),
            "world_feasibility.check",
            f"World check {check_id}",
            issues,
        )
        if row.get("target_type") == "candidate" and row.get("target_id") not in candidate_index:
            issues.append(issue("world_feasibility.candidate_target.unknown", f"World check {check_id} targets an unknown candidate."))
    for candidate_id, candidate in candidate_index.items():
        check_id = candidate.get("world_check_id")
        check = world_index.get(str(check_id))
        if check is None:
            issues.append(issue("experience_candidate_pool.world_check.missing", f"Candidate {candidate_id} has no current World check."))
            continue
        if not _world_check_covers(check, "candidate", candidate_id, as_dict(data.get("trip_context"))):
            issues.append(issue("experience_candidate_pool.world_check.target_mismatch", f"Candidate {candidate_id} cites a World check owned by another target."))
        if candidate.get("candidate_status") == "usable" and check.get("status") != "pass":
            issues.append(issue("experience_candidate_pool.status.overclaim", f"Candidate {candidate_id} is usable over a non-pass World check."))
    return world_index


def validate_negative_evidence(
    data: dict[str, Any],
    source_index: dict[str, dict[str, Any]],
    candidate_index: dict[str, dict[str, Any]],
    issues: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    rows = as_list(data.get("negative_evidence"))
    pit_index = index_rows(rows, "pit_id", "negative_evidence", issues)
    for pit_id, row in pit_index.items():
        require_fields(
            row,
            ("node_id", "issue", "affected_traveler", "source_ids", "severity", "trigger_condition", "mitigation", "fallback_ids", "status"),
            "negative_evidence.pitfall",
            f"Pitfall {pit_id}",
            issues,
        )
        unknown_sources = sorted(set(map(str, as_list(row.get("source_ids")))) - set(source_index))
        if unknown_sources:
            issues.append(issue("negative_evidence.source.unknown", f"Pitfall {pit_id} references unknown sources: {', '.join(unknown_sources)}"))
        if row.get("node_id") not in candidate_index:
            issues.append(issue("negative_evidence.node.unknown", f"Pitfall {pit_id} references an unknown candidate node."))
    for candidate_id, candidate in candidate_index.items():
        missing = sorted(set(map(str, as_list(candidate.get("negative_signal_ids")))) - set(pit_index))
        if missing:
            issues.append(issue("experience_candidate_pool.negative_signal.unknown", f"Candidate {candidate_id} references unknown pitfalls: {', '.join(missing)}"))
    return pit_index


def validate_routes(
    data: dict[str, Any],
    context: dict[str, Any],
    profile: dict[str, Any],
    candidate_index: dict[str, dict[str, Any]],
    world_index: dict[str, dict[str, Any]],
    pit_index: dict[str, dict[str, Any]],
    issues: list[dict[str, str]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], float]:
    routes = as_list(as_dict(data.get("route_mesh")).get("routes"))
    route_index = index_rows(routes, "trace_id", "route_mesh", issues)
    if not route_index:
        issues.append(issue("route_mesh.too_few_routes", "At least one current route is required."))
    route_types = {str(row.get("route_type")) for row in route_index.values()}
    if "primary" not in route_types:
        issues.append(issue("route_mesh.primary.missing", "A primary route is required."))
    if context.get("requested_claim_level") in {"bookable", "day_of"} and "comfort" not in route_types:
        issues.append(issue("route_mesh.comfort.missing", "Bookable/day-of requests need a comfort route."))
    node_index: dict[str, dict[str, Any]] = {}
    max_walking = 0.0
    route_walking: dict[str, float] = {}
    for trace_id, route in route_index.items():
        require_fields(
            route,
            ("route_type", "title", "day_ids", "story_arc", "route_nodes", "movement_edges", "operational_steps", "world_check_ids", "weakest_links", "fallback_ids", "evidence_boundary", "downgrade_reason"),
            "route_mesh.route",
            f"Route {trace_id}",
            issues,
        )
        if route.get("feasibility_status") not in ROUTE_STATUSES:
            issues.append(issue("route_mesh.feasibility_status.invalid", f"Route {trace_id} has invalid feasibility_status."))
        day_ids = set(map(str, as_list(context.get("day_ids"))))
        unknown_days = sorted(set(map(str, as_list(route.get("day_ids")))) - day_ids)
        if unknown_days:
            issues.append(issue("route_mesh.day.unknown", f"Route {trace_id} references unknown days: {', '.join(unknown_days)}"))
        nodes = as_list(route.get("route_nodes"))
        local_node_ids: list[str] = []
        for position, node in enumerate(nodes):
            if not isinstance(node, dict):
                issues.append(issue("route_mesh.node.invalid", f"Route {trace_id} node {position} must be an object."))
                continue
            node_id = node.get("route_node_id")
            if not isinstance(node_id, str) or not node_id:
                issues.append(issue("route_mesh.node.route_node_id.missing", f"Route {trace_id} node {position} lacks route_node_id."))
                continue
            if node_id in node_index:
                issues.append(issue("route_mesh.node.route_node_id.duplicate", f"Duplicate route node id {node_id}."))
            node_index[node_id] = node
            local_node_ids.append(node_id)
            require_fields(
                node,
                ("trace_id", "day_id", "candidate_id", "time_window", "role_in_day", "source_ids", "world_check_id", "fallback_ids", "risk_ids", "status"),
                "route_mesh.node",
                f"Route node {node_id}",
                issues,
            )
            if node.get("trace_id") != trace_id:
                issues.append(issue("route_mesh.node.trace_mismatch", f"Route node {node_id} does not bind its owner trace."))
            if node.get("day_id") not in day_ids:
                issues.append(issue("route_mesh.node.day_unknown", f"Route node {node_id} references an unknown day."))
            candidate_id = str(node.get("candidate_id"))
            if candidate_id not in candidate_index:
                issues.append(issue("route_mesh.node.candidate_unknown", f"Route node {node_id} references an unknown candidate."))
            world = world_index.get(str(node.get("world_check_id")))
            if world is None:
                issues.append(issue("route_mesh.node.world_check_missing", f"Route node {node_id} lacks a current World check."))
            elif not _world_check_covers(world, "candidate", candidate_id, context):
                issues.append(issue("route_mesh.node.world_check.target_mismatch", f"Route node {node_id} uses a World check for another target."))
            unknown_risks = sorted(set(map(str, as_list(node.get("risk_ids")))) - set(pit_index))
            if unknown_risks:
                issues.append(issue("route_mesh.node.risk_unknown", f"Route node {node_id} references unknown risks: {', '.join(unknown_risks)}"))
        movement_edges = as_list(route.get("movement_edges"))
        edge_ids: set[str] = set()
        actual_pairs: list[tuple[Any, Any]] = []
        for edge in movement_edges:
            if not isinstance(edge, dict):
                issues.append(issue("route_mesh.edge.invalid", f"Route {trace_id} contains a non-object movement edge."))
                continue
            require_fields(edge, ("edge_id", "from_node_id", "to_node_id", "travel_minutes", "mode", "status"), "route_mesh.edge", f"Route {trace_id} edge", issues)
            edge_id = edge.get("edge_id")
            if not isinstance(edge_id, str) or not edge_id or edge_id in edge_ids:
                issues.append(issue("route_mesh.edge.edge_id.invalid", f"Route {trace_id} has a missing or duplicate movement edge id."))
            else:
                edge_ids.add(edge_id)
            if edge.get("from_node_id") not in local_node_ids or edge.get("to_node_id") not in local_node_ids:
                issues.append(issue("route_mesh.edge.node_unknown", f"Route {trace_id} edge references a node outside the route."))
            actual_pairs.append((edge.get("from_node_id"), edge.get("to_node_id")))
        expected_pairs = list(zip(local_node_ids[:-1], local_node_ids[1:]))
        if actual_pairs != expected_pairs:
            issues.append(issue("route_mesh.edge.chain_mismatch", f"Route {trace_id} movement edges must form the exact declared node chain."))
        for world_id in map(str, as_list(route.get("world_check_ids"))):
            world = world_index.get(world_id)
            if world is None:
                issues.append(issue("route_mesh.world_check.missing", f"Route {trace_id} references missing World check {world_id}."))
            elif not _world_check_covers(world, "route", trace_id, context):
                issues.append(issue("route_mesh.world_check.target_mismatch", f"Route {trace_id} cites a World check for another target."))
            elif route.get("feasibility_status") == "pass" and world.get("status") != "pass":
                issues.append(issue("route_mesh.feasibility_status.overclaim", f"Route {trace_id} passes over a non-pass World check."))
        walking = route.get("walking_km", 0)
        if not isinstance(walking, (int, float)) or walking < 0:
            issues.append(issue("route_mesh.walking_km.invalid", f"Route {trace_id} walking_km is invalid."))
        else:
            route_walking[str(route.get("route_type"))] = float(walking)
            max_walking = max(max_walking, float(walking))
    if "primary" in route_walking and "comfort" in route_walking and route_walking["comfort"] > route_walking["primary"]:
        issues.append(issue("route_mesh.comfort.walking_over_primary", "Comfort route walks more than the primary route."))
    tolerance = profile.get("walking_tolerance_km")
    if isinstance(tolerance, (int, float)) and max_walking > float(tolerance):
        issues.append(issue("route_mesh.walking_tolerance.exceeded", "A route exceeds the traveler's walking tolerance."))
    return route_index, node_index, max_walking


def validate_fallbacks(
    data: dict[str, Any],
    source_index: dict[str, dict[str, Any]],
    candidate_index: dict[str, dict[str, Any]],
    world_index: dict[str, dict[str, Any]],
    pit_index: dict[str, dict[str, Any]],
    route_index: dict[str, dict[str, Any]],
    node_index: dict[str, dict[str, Any]],
    issues: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    rows = as_list(data.get("fallback_options"))
    fallback_index = index_rows(rows, "fallback_id", "fallback_options", issues)
    if not fallback_index:
        issues.append(issue("fallback_options.too_few", "At least one named fallback option is required."))
    node_owner = {
        str(node.get("route_node_id")): trace_id
        for trace_id, route in route_index.items()
        for node in as_list(route.get("route_nodes"))
        if isinstance(node, dict) and node.get("route_node_id")
    }
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_index}
    for route in route_index.values():
        for edge in as_list(route.get("movement_edges")):
            if isinstance(edge, dict) and edge.get("from_node_id") in adjacency:
                adjacency[str(edge.get("from_node_id"))].add(str(edge.get("to_node_id")))

    def reaches(start_node: str, target_node: str) -> bool:
        pending = [start_node]
        seen: set[str] = set()
        while pending:
            current = pending.pop()
            if current == target_node:
                return True
            if current in seen:
                continue
            seen.add(current)
            pending.extend(sorted(adjacency.get(current, set()) - seen))
        return False

    for fallback_id, row in fallback_index.items():
        require_fields(
            row,
            ("candidate_id", "replaces_route_node_ids", "reachable_from_route_node_ids", "trigger", "travel_time_delta_minutes", "cost_delta", "fit_notes", "source_ids", "world_check_id", "status", "boundary"),
            "fallback_options.fallback",
            f"Fallback {fallback_id}",
            issues,
        )
        if row.get("candidate_id") not in candidate_index:
            issues.append(issue("fallback_options.candidate_unknown", f"Fallback {fallback_id} references an unknown candidate."))
        for field, code in (
            ("replaces_route_node_ids", "fallback_options.replacement_node.unknown"),
            ("reachable_from_route_node_ids", "fallback_options.reachable_node.unknown"),
        ):
            unknown = sorted(set(map(str, as_list(row.get(field)))) - set(node_index))
            if unknown:
                issues.append(issue(code, f"Fallback {fallback_id} references unknown route nodes: {', '.join(unknown)}"))
        replacement_nodes = [str(value) for value in as_list(row.get("replaces_route_node_ids")) if str(value) in node_index]
        reachable_nodes = [str(value) for value in as_list(row.get("reachable_from_route_node_ids")) if str(value) in node_index]
        for replacement_node in replacement_nodes:
            same_route_sources = [source for source in reachable_nodes if node_owner.get(source) == node_owner.get(replacement_node)]
            if not any(reaches(source, replacement_node) for source in same_route_sources):
                issues.append(issue("fallback_options.reachability.unproven", f"Fallback {fallback_id} has no declared reachable predecessor for replacement node {replacement_node}."))
        unknown_sources = sorted(set(map(str, as_list(row.get("source_ids")))) - set(source_index))
        if unknown_sources:
            issues.append(issue("fallback_options.source.unknown", f"Fallback {fallback_id} references unknown sources."))
        world = world_index.get(str(row.get("world_check_id")))
        if not _world_check_covers(world, "candidate", row.get("candidate_id"), as_dict(data.get("trip_context"))):
            issues.append(issue("fallback_options.world_check.target_mismatch", f"Fallback {fallback_id} lacks the exact candidate World check."))
    for pit_id, pit in pit_index.items():
        unknown = sorted(set(map(str, as_list(pit.get("fallback_ids")))) - set(fallback_index))
        if unknown:
            issues.append(issue("negative_evidence.fallback.unknown", f"Pitfall {pit_id} references unknown fallbacks: {', '.join(unknown)}"))
    for trace_id, route in route_index.items():
        unknown = sorted(set(map(str, as_list(route.get("fallback_ids")))) - set(fallback_index))
        if unknown:
            issues.append(issue("route_mesh.fallback.unknown", f"Route {trace_id} references unknown fallbacks: {', '.join(unknown)}"))
    for node_id, node in node_index.items():
        unknown = sorted(set(map(str, as_list(node.get("fallback_ids")))) - set(fallback_index))
        if unknown:
            issues.append(issue("route_mesh.node.fallback_unknown", f"Route node {node_id} references unknown fallbacks: {', '.join(unknown)}"))
    return fallback_index


def validate_lodging(
    data: dict[str, Any],
    context: dict[str, Any],
    candidate_index: dict[str, dict[str, Any]],
    world_index: dict[str, dict[str, Any]],
    route_index: dict[str, dict[str, Any]],
    issues: list[dict[str, str]],
) -> None:
    lodging = as_dict(data.get("lodging_strategy"))
    if not context.get("overnight"):
        if lodging:
            require_fields(lodging, ("strategy_id", "status", "boundary"), "lodging_strategy", "lodging_strategy", issues)
        return
    if not lodging:
        issues.append(issue("lodging_strategy.missing", "Overnight plans require lodging_strategy."))
        return
    require_fields(
        lodging,
        ("strategy_id", "hotel_candidate_ids", "world_check_ids", "affected_trace_ids", "check_in_window", "check_out_window", "luggage_plan", "late_return_plan", "status", "boundary"),
        "lodging_strategy",
        "lodging_strategy",
        issues,
    )
    for candidate_id in map(str, as_list(lodging.get("hotel_candidate_ids"))):
        candidate = candidate_index.get(candidate_id)
        if candidate is None or candidate.get("class") != "hotel":
            issues.append(issue("lodging_strategy.hotel_candidate.invalid", "lodging_strategy references a missing or non-hotel candidate."))
    for check_id in map(str, as_list(lodging.get("world_check_ids"))):
        check = world_index.get(check_id)
        if check is None or check.get("target_type") != "hotel_strategy" or check.get("target_id") != lodging.get("strategy_id"):
            issues.append(issue("lodging_strategy.world_check.target_mismatch", "lodging_strategy lacks its exact hotel_strategy World check."))
    unknown_traces = sorted(set(map(str, as_list(lodging.get("affected_trace_ids")))) - set(route_index))
    if unknown_traces:
        issues.append(issue("lodging_strategy.trace.unknown", "lodging_strategy references unknown routes."))


def validate_trip_fit(
    data: dict[str, Any],
    context: dict[str, Any],
    profile: dict[str, Any],
    route_index: dict[str, dict[str, Any]],
    issues: list[dict[str, str]],
) -> dict[str, Any]:
    fit = as_dict(data.get("trip_fit_review"))
    if not fit:
        issues.append(issue("trip_fit_review.missing", "trip_fit_review is required."))
        return {}
    require_fields(fit, ("dimension_rows", "boundary"), "trip_fit_review", "trip_fit_review", issues)
    rows = as_list(fit.get("dimension_rows"))
    dimensions = index_rows(rows, "dimension", "trip_fit_review.dimension", issues)
    required = set(REQUIRED_FIT_DIMENSIONS)
    if context.get("overnight"):
        required.add("hotel_lodging_fit")
    ages = as_list(profile.get("ages"))
    if any(isinstance(age, int) and (age < 12 or age > 70) for age in ages):
        required.add("child_or_elderly_protection")
    if as_list(profile.get("accessibility_needs")) not in ([], ["none declared"]):
        required.add("accessibility")
    missing = sorted(required - set(dimensions))
    if missing:
        issues.append(issue("trip_fit_review.dimension.missing", "Missing fit dimensions: " + ", ".join(missing)))
    nonpass = False
    input_owners: dict[str, tuple[str, Any]] = {
        "age": ("traveler_profile.ages", profile.get("ages")),
        "stamina": ("traveler_profile.stamina", profile.get("stamina")),
        "companions": ("traveler_profile.companions", profile.get("companions")),
        "interests": ("traveler_profile.interests", profile.get("interests")),
        "pace": ("traveler_profile.pace", profile.get("pace")),
        "rest": ("traveler_profile.stamina", profile.get("stamina")),
        "budget": ("traveler_profile.budget_level", profile.get("budget_level")),
        "safety": ("traveler_profile.safety_constraints", profile.get("safety_constraints")),
        "weather_resilience": ("traveler_profile.safety_constraints", profile.get("safety_constraints")),
        "fallback_fit": ("traveler_profile.must_avoid", profile.get("must_avoid")),
        "food_fit": ("traveler_profile.food_constraints", profile.get("food_constraints")),
        "hotel_lodging_fit": ("trip_context.overnight", context.get("overnight")),
        "child_or_elderly_protection": ("traveler_profile.ages", profile.get("ages")),
        "accessibility": ("traveler_profile.accessibility_needs", profile.get("accessibility_needs")),
    }
    for dimension, row in dimensions.items():
        require_fields(row, ("status", "affected_trace_ids", "evidence_ids", "mitigation_ids", "input_field", "input_values"), "trip_fit_review.dimension", f"Fit dimension {dimension}", issues)
        expected = input_owners.get(dimension)
        if expected is None:
            issues.append(issue("trip_fit_review.dimension.owner_unknown", f"Fit dimension {dimension} has no declared traveler/context input owner."))
        else:
            expected_field, raw_values = expected
            expected_values = raw_values if isinstance(raw_values, list) else [raw_values]
            if row.get("input_field") != expected_field or row.get("input_values") != expected_values:
                issues.append(issue("trip_fit_review.dimension.input_mismatch", f"Fit dimension {dimension} does not bind the current {expected_field} value."))
        if row.get("status") not in FIT_STATUSES:
            issues.append(issue("trip_fit_review.dimension.status.invalid", f"Fit dimension {dimension} has invalid status."))
        if row.get("status") != "pass":
            nonpass = True
        unknown = sorted(set(map(str, as_list(row.get("affected_trace_ids")))) - set(route_index))
        if unknown:
            issues.append(issue("trip_fit_review.dimension.trace_unknown", f"Fit dimension {dimension} references unknown routes."))
    fit["status"] = "pass" if not nonpass and not missing else "blocked"
    return fit


def validate_recommendation(
    data: dict[str, Any],
    candidate_index: dict[str, dict[str, Any]],
    route_index: dict[str, dict[str, Any]],
    world_index: dict[str, dict[str, Any]],
    fit: dict[str, Any],
    issues: list[dict[str, str]],
) -> dict[str, Any]:
    recommendation = as_dict(data.get("recommendation_support"))
    if not recommendation:
        issues.append(issue("recommendation_support.missing", "recommendation_support is required."))
        return {}
    require_fields(recommendation, ("candidate_ids", "route_ids", "world_check_ids", "boundary", "next_action"), "recommendation_support", "recommendation_support", issues)
    candidate_ids = set(map(str, as_list(recommendation.get("candidate_ids"))))
    route_ids = set(map(str, as_list(recommendation.get("route_ids"))))
    world_ids = set(map(str, as_list(recommendation.get("world_check_ids"))))
    if candidate_ids - set(candidate_index):
        issues.append(issue("recommendation_support.candidate.unknown", "Recommendation references unknown candidates."))
    if route_ids - set(route_index):
        issues.append(issue("recommendation_support.route.unknown", "Recommendation references unknown routes."))
    if world_ids - set(world_index):
        issues.append(issue("recommendation_support.world_check.unknown", "Recommendation references unknown World checks."))
    passed = (bool(candidate_ids and route_ids and world_ids)
        and candidate_ids <= set(candidate_index) and route_ids <= set(route_index) and world_ids <= set(world_index)
        and all(candidate_index[item].get("candidate_status") == "usable" for item in candidate_ids if item in candidate_index)
        and all(route_index[item].get("feasibility_status") == "pass" for item in route_ids if item in route_index)
        and all(world_index[item].get("status") == "pass" for item in world_ids if item in world_index)
        and fit.get("status") == "pass")
    recommendation["status"] = "pass" if passed else "blocked"
    return recommendation




def validate_weather_evidence(
    context: dict[str, Any],
    source_index: dict[str, dict[str, Any]],
    fallback_index: dict[str, dict[str, Any]],
    issues: list[dict[str, str]],
) -> dict[str, Any]:
    weather = as_dict(context.get("weather_evidence_summary"))
    if not weather:
        issues.append(issue("trip_context.weather_summary.missing", "weather_evidence_summary is required."))
        return {}
    require_fields(
        weather,
        ("weather_summary_id", "date_relation", "source_type", "weather_source_mode", "source_ids", "covered_dates", "checked_hazards", "affected_day_ids", "route_adjustments", "fallback_ids", "claim_status", "recheck_note"),
        "trip_context.weather_summary",
        "weather_evidence_summary",
        issues,
    )
    if "missing_or_downgraded_hazards" not in weather or not isinstance(weather.get("missing_or_downgraded_hazards"), list):
        issues.append(issue("trip_context.weather_summary.missing_or_downgraded_hazards.missing", "weather_evidence_summary needs an explicit missing_or_downgraded_hazards list."))
    relation = context.get("date_relation")
    mode = weather.get("weather_source_mode")
    if weather.get("date_relation") != relation:
        issues.append(issue("trip_context.weather_summary.date_relation.mismatch", "Weather summary date relation differs from trip_context."))
    if mode not in WEATHER_MODES_BY_DATE.get(str(relation), set()):
        issues.append(issue("trip_context.weather_summary.chronology_mismatch", "Weather source mode does not support this trip chronology."))
    source_ids = set(map(str, as_list(weather.get("source_ids"))))
    unknown = sorted(source_ids - set(source_index))
    if unknown:
        issues.append(issue("trip_context.weather_summary.source_unknown", "Weather summary references unknown sources."))
    weather_classes = {source_index[source_id].get("source_class") for source_id in source_ids if source_id in source_index}
    required_classes = {
        "forecast": {"weather_forecast"},
        "forecast_alert": {"weather_forecast", "weather_alert"},
        "mixed": {"weather_forecast", "weather_alert"},
        "historical_observed": {"weather_historical"},
        "archive": {"weather_historical"},
        "climate": {"weather_climate"},
    }.get(str(mode), set())
    if not required_classes <= weather_classes:
        issues.append(issue("trip_context.weather_summary.source_class.mismatch", "Weather summary lacks source classes required by its mode."))
    if set(map(str, as_list(weather.get("fallback_ids")))) - set(fallback_index):
        issues.append(issue("trip_context.weather_summary.fallback_unknown", "Weather summary references unknown fallbacks."))
    return weather




def derive_allowed_claim_level(
    context: dict[str, Any],
    source_index: dict[str, dict[str, Any]],
    world_index: dict[str, dict[str, Any]],
    route_index: dict[str, dict[str, Any]],
    fit: dict[str, Any],
    recommendation: dict[str, Any],
) -> tuple[str, str]:
    relation = str(context.get("date_relation"))
    weather = as_dict(context.get("weather_evidence_summary"))
    mode = str(weather.get("weather_source_mode"))
    # Currency means checked on the planning date, never a caller-authored freshness label.
    # No invented expiry window: later dates are invalid; earlier checks cannot authorize booking/day-of claims.
    planning = _parse_iso_datetime(context.get("planning_as_of"))
    all_sources_current = bool(source_index) and planning is not None and all(
        _parse_iso_date(row.get("checked_on")) == planning.date() for row in source_index.values())
    all_world_pass = bool(world_index) and all(row.get("status") == "pass" for row in world_index.values())
    all_routes_pass = bool(route_index) and all(row.get("feasibility_status") == "pass" for row in route_index.values())
    all_domain_pass = all_world_pass and all_routes_pass and fit.get("status") == "pass" and recommendation.get("status") == "pass"
    if not all_domain_pass:
        return "initial_plan", "upstream_nonpass"
    if relation == "day_of" and mode in {"forecast_alert", "mixed"} and all_sources_current:
        return "day_of", "day_of_current"
    if relation == "near_future" and mode in {"forecast", "forecast_alert", "mixed"} and all_sources_current:
        return "bookable", "near_future_current"
    if relation in {"past", "far_future", "undated"}:
        return "initial_plan", f"{relation}_planning_boundary"
    return "initial_plan", "current_fact_or_weather_gap"


def review_plan(
    data: dict[str, Any],
    *,
    plan_path: Path | None = None,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if data.get("schema_version") != SCHEMA_VERSION:
        return {"allowed_claim_level": "initial_plan", "allowed_claim_reason": "invalid_plan", "issues": [issue("schema_version.invalid", f"Only {SCHEMA_VERSION} is current; no former plan reader exists.")]}
    data = _derive_inputs(data, plan_path, issues)
    context = validate_trip_context(data, issues)
    profile = validate_traveler_profile(data, issues)
    source_index, _source_classes = validate_source_portfolio(data, context, issues)
    candidate_index = validate_candidates(data, context, source_index, issues)
    world_index = validate_world_checks(data, candidate_index, issues)
    pit_index = validate_negative_evidence(data, source_index, candidate_index, issues)
    route_index, node_index, _max_walking = validate_routes(data, context, profile, candidate_index, world_index, pit_index, issues)
    fallback_index = validate_fallbacks(data, source_index, candidate_index, world_index, pit_index, route_index, node_index, issues)
    validate_lodging(data, context, candidate_index, world_index, route_index, issues)
    fit = validate_trip_fit(data, context, profile, route_index, issues)
    recommendation = validate_recommendation(data, candidate_index, route_index, world_index, fit, issues)
    validate_weather_evidence(context, source_index, fallback_index, issues)
    derived_level, derived_reason = derive_allowed_claim_level(context, source_index, world_index, route_index, fit, recommendation)
    if issues and derived_level != "initial_plan":
        derived_level, derived_reason = "initial_plan", "invalid_trip_inputs"
    requested = context.get("requested_claim_level")
    if requested in CLAIM_LEVELS and _claim_rank(requested) > _claim_rank(derived_level):
        issues.append(issue("trip_context.requested_claim_level.overreach", f"Requested {requested}, but saved reports and check dates support only {derived_level} ({derived_reason})."))
    return {"allowed_claim_level": derived_level, "allowed_claim_reason": derived_reason, "issues": issues,
            "derived": {"world_checks": {key: row.get("status") for key, row in world_index.items()},
                        "routes": {key: row.get("feasibility_status") for key, row in route_index.items()},
                        "trip_fit": fit.get("status", "blocked"),
                        "recommendation": recommendation.get("status", "blocked")}}


def validate_plan(data: dict[str, Any], *, plan_path: Path | None = None,
                  repository_root: Path | None = None) -> list[dict[str, str]]:
    return review_plan(data, plan_path=plan_path, repository_root=repository_root)["issues"]


def _derive_inputs(original: dict[str, Any], plan_path: Path | None, issues: list[dict[str, str]]) -> dict[str, Any]:
    data = copy.deepcopy(original)
    def retired(row, key, label):
        if key in row:
            issues.append(issue(f"{label}.{key}.retired", f"{label}.{key} is retired; use the trip model inputs and saved WorldGuard reports."))
            row.pop(key)
    for key in ("reader_projection", "traveler_native_guide"):
        retired(data, key, "trip_plan")
    context = as_dict(data.get("trip_context"))
    retired(context, "allowed_claim_level", "trip_context")
    for row in as_list(as_dict(data.get("source_portfolio")).get("sources")):
        if isinstance(row, dict):
            for key in ("freshness_status", "access_status"):
                retired(row, key, "source_portfolio")
    for row in as_list(as_dict(data.get("experience_candidate_pool")).get("candidates")):
        if isinstance(row, dict):
            for key in ("access_status", "freshness_status"):
                retired(row, key, "experience_candidate_pool")
    report_statuses = {}
    for row in as_list(as_dict(data.get("world_feasibility")).get("checks")):
        if not isinstance(row, dict):
            continue
        retired(row, "status", "world_feasibility")
        reference = row.get("worldguard_report")
        status = "unreadable"
        if isinstance(reference, str) and reference:
            report_path = ((plan_path.parent if plan_path else Path.cwd()) / reference).resolve()
            if report_path not in report_statuses:
                report_statuses[report_path] = read_worldguard_report(report_path)
            status = report_statuses[report_path]
        row["status"] = status.lower()
        if status == "unreadable":
            issues.append(issue("world_feasibility.report.unreadable", f"WorldGuard report could not be read: {reference}"))
    world_index = {row.get("world_check_id"): row for row in as_list(as_dict(data.get("world_feasibility")).get("checks")) if isinstance(row, dict)}
    for row in as_list(as_dict(data.get("route_mesh")).get("routes")):
        if not isinstance(row, dict):
            continue
        retired(row, "feasibility_status", "route_mesh")
        refs = as_list(row.get("world_check_ids"))
        row["feasibility_status"] = "pass" if refs and all(world_index.get(ref, {}).get("status") == "pass" for ref in refs) else "blocked"
    retired(as_dict(data.get("trip_fit_review")), "status", "trip_fit_review")
    recommendation = as_dict(data.get("recommendation_support"))
    for key in ("status", "fit_status", "trace_ids"):
        retired(recommendation, key, "recommendation_support")
    return data


def validate_composition_refs(plan: dict[str, Any], composition: dict[str, Any]) -> list[dict[str, str]]:
    """Check that a v2 travel composition names routes, nodes, risks and fallbacks that exist in the trip plan."""
    issues: list[dict[str, str]] = []
    routes = [row for row in as_list(as_dict(plan.get("route_mesh")).get("routes")) if isinstance(row, dict)]
    trace_ids = {row.get("trace_id") for row in routes}
    node_ids = {node.get("route_node_id") for row in routes for node in as_list(row.get("route_nodes")) if isinstance(node, dict)}
    fallback_ids = {row.get("fallback_id") for row in as_list(plan.get("fallback_options")) if isinstance(row, dict)}
    risk_ids = {row.get("pit_id") for row in as_list(plan.get("negative_evidence")) if isinstance(row, dict)}
    candidate_ids = {row.get("candidate_id") for row in as_list(as_dict(plan.get("experience_candidate_pool")).get("candidates")) if isinstance(row, dict)}
    fit_ids = {as_dict(plan.get("trip_fit_review")).get("fit_id")} - {None}
    for section in as_list(composition.get("body_sections")):
        section = as_dict(section)
        for ref in as_list(section.get("route_refs")):
            if ref not in trace_ids | node_ids:
                issues.append(issue("travel_composition.route_ref.unknown", f"Section {section.get('section_id')} names route {ref}, which is not in the trip plan."))
        for ref in as_list(section.get("traveler_fit_refs")):
            if ref not in fit_ids:
                issues.append(issue("travel_composition.traveler_fit_ref.unknown", f"Unknown trip fit review: {ref}"))
        for ref in as_list(section.get("local_texture_refs")):
            if ref not in candidate_ids:
                issues.append(issue("travel_composition.local_texture_ref.unknown", f"Unknown local candidate: {ref}"))
    for local in as_list(composition.get("local_texture_candidates")):
        if as_dict(local).get("candidate_id") not in candidate_ids:
            issues.append(issue("travel_composition.local_texture_ref.unknown", "Composition local texture must identify a candidate in the trip plan."))
    for binding in as_list(composition.get("risk_fallback_bindings")):
        binding = as_dict(binding)
        if binding.get("fallback_id") not in fallback_ids:
            issues.append(issue("travel_composition.fallback.unknown", f"Binding {binding.get('binding_id')} names fallback {binding.get('fallback_id')}, which is not in the trip plan."))
        if binding.get("risk_id") not in risk_ids:
            issues.append(issue("travel_composition.risk.unknown", f"Binding {binding.get('binding_id')} names risk {binding.get('risk_id')}, which is not in the trip plan."))
        if set(as_list(binding.get("reachable_from_route_node_ids"))) - node_ids:
            issues.append(issue("travel_composition.route_node.unknown", f"Binding {binding.get('binding_id')} names route nodes that are not in the trip plan."))
    return issues


def review_plan_file(plan_path: Path, *, repository_root: Path | None = None) -> dict[str, Any]:
    plan_path = Path(plan_path)
    try:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        issues = [issue("plan.file.missing", f"Plan file does not exist: {plan_path}")]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        issues = [issue("plan.file.invalid", f"Plan file is not valid UTF-8 JSON: {exc}")]
    else:
        if isinstance(payload, dict):
            return review_plan(payload, plan_path=plan_path, repository_root=repository_root)
        issues = [issue("plan.root.invalid", "Plan root must be a JSON object.")]
    return {"allowed_claim_level": "initial_plan", "allowed_claim_reason": "unavailable_plan", "issues": issues}


def validate_plan_file(plan_path: Path, *, repository_root: Path | None = None) -> list[dict[str, str]]:
    return review_plan_file(plan_path, repository_root=repository_root)["issues"]


__all__ = ["review_plan_file", "review_plan", "derive_allowed_claim_level", "SCHEMA_VERSION", "issue", "validate_composition_refs", "validate_plan", "validate_plan_file"]
