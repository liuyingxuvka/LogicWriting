"""Bind route composition identity to its actual domain input bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from _common import ValidationError, fingerprint, fingerprint_without


def _input_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except (OSError, ValueError) as exc:
        raise ValidationError(f"{label} cannot be read: {path}: {exc}") from exc


def route_extension_fingerprint(composition: dict[str, Any], base_dir: str | Path | None = None) -> str:
    """Preserve ordinary route identity; travel also binds its trip and saved reports."""
    if composition.get("final_owner") != "travel-guide":
        return fingerprint_without(composition, "extension_fingerprint")
    reference = composition.get("trip_plan")
    if not isinstance(reference, str) or not reference.strip():
        raise ValidationError("travel composition requires a nonempty trip_plan path")
    try:
        trip_path = ((Path(base_dir) if base_dir is not None else Path.cwd()) / reference).resolve()
    except (OSError, ValueError, RuntimeError) as exc:
        raise ValidationError(f"travel trip_plan path is invalid: {reference}: {exc}") from exc
    trip_bytes = _input_bytes(trip_path, "travel trip_plan")
    try:
        trip = json.loads(trip_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"travel trip_plan is not valid UTF-8 JSON: {trip_path}: {exc}") from exc
    if not isinstance(trip, dict):
        raise ValidationError(f"travel trip_plan must contain an object: {trip_path}")
    feasibility = trip.get("world_feasibility")
    checks = feasibility.get("checks") if isinstance(feasibility, dict) else None
    if not isinstance(checks, list) or not checks:
        raise ValidationError(f"travel trip_plan requires world_feasibility.checks: {trip_path}")
    reports = []
    contents = {}
    for position, check in enumerate(checks):
        report_ref = check.get("worldguard_report") if isinstance(check, dict) else None
        if not isinstance(report_ref, str) or not report_ref.strip():
            raise ValidationError(f"travel world check {position} requires worldguard_report: {trip_path}")
        try:
            report_path = (trip_path.parent / report_ref).resolve()
        except (OSError, ValueError, RuntimeError) as exc:
            raise ValidationError(f"saved WorldGuard report path is invalid: {report_ref}: {exc}") from exc
        if report_path not in contents:
            contents[report_path] = hashlib.sha256(_input_bytes(report_path, "saved WorldGuard report")).hexdigest()
        reports.append({"reference": report_ref, "bytes_sha256": contents[report_path]})
    return fingerprint({
        "composition": {key: value for key, value in composition.items() if key != "extension_fingerprint"},
        "trip_plan_bytes_sha256": hashlib.sha256(trip_bytes).hexdigest(),
        "worldguard_report_bytes": reports,
    })
