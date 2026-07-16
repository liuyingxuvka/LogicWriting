from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from fixture_mutation import MutationError, apply_mutations


FORBIDDEN_TERMS = (
    "候选池",
    "路线追踪",
    "SourceGuard",
    "TraceGuard",
    "WorldGuard",
    "Guard Mesh",
    "技能测试",
    "candidate pool",
    "route trace",
    "validation id",
    "model evidence",
)

LOCAL_TEXTURE_PATTERNS = (
    r"\btakoyaki\b",
    r"\bokonomiyaki\b",
    r"\bsushi\b",
    r"\bnoodle",
    r"\bcafe\b",
    r"\bcoffee\b",
    r"\bmarket\b",
    r"\bbistro\b",
    r"\bbakery\b",
    r"\brestaurant\b",
    r"\bdish\b",
    r"\bsouvenir",
    r"\bshop",
    r"\bshopping",
    r"\bhotel",
    r"\brest\b",
    r"\bquiet\b",
)

RISK_SPECIFICITY_PATTERNS = (
    r"\bif\b",
    r"\bwhen\b",
    r"\btrigger\b",
    r"\bfallback\b",
    r"\bswitch\b",
    r"\binstead\b",
    r"\bnearby\b",
    r"\breserve\b",
)

WEATHER_PATTERNS = (
    r"\bweather\b",
    r"\brain\b",
    r"\bwind\b",
    r"\bheat\b",
    r"\bhumid",
    r"\bforecast\b",
    r"\bhistorical\b",
    r"\barchive\b",
    r"\bclimate\b",
    r"\balert\b",
    r"\badvisory\b",
    r"\btyphoon\b",
    r"\bstorm\b",
    r"\bthunderstorm\b",
    r"\bair quality\b",
    r"天气",
    r"下雨",
    r"降雨",
    r"高温",
    r"闷热",
    r"风",
    r"雨季",
    r"台风",
    r"雷暴",
    r"预警",
    r"空气质量",
)

DAY_HEADING_PATTERNS = (
    r"^(#{1,6}\s*)?day\s*\d+\b",
    r"^(#{1,6}\s*)?day\s+(one|two|three|four|five|six|seven|eight|nine|ten)\b",
    r"^(#{1,6}\s*)?(arrival|departure)\s+(day|afternoon|morning)\b",
    r"^(#{1,6}\s*)?full\s+city\s+day\b",
    r"^(#{1,6}\s*)?june\s+\d{1,2}\b",
    r"^(#{1,6}\s*)?july\s+\d{1,2}\b",
    r"^(#{1,6}\s*)?第[一二三四五六七八九十0-9]+天\b",
    r"^(#{1,6}\s*)?\d{1,2}月\d{1,2}日\b",
)

VALID_WEATHER_CLAIM_STATUSES = {"checked", "partial", "downgraded", "missing_with_boundary", "not_applicable"}
VALID_WEATHER_SOURCE_MODES = {"forecast", "forecast_alert", "historical_observed", "historical", "archive", "climate", "alert", "mixed", "missing"}


def issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def count_patterns(text: str, patterns: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(len(re.findall(pattern, lowered)) for pattern in patterns)


def nonempty(value: Any) -> bool:
    return value not in ("", [], None)


def observed_day_count(review: dict[str, Any] | None) -> int:
    if not review:
        return 0
    days = review.get("observed_days")
    return len(days) if isinstance(days, list) else 0


def count_day_headings(text: str) -> int:
    count = 0
    for line in text.splitlines():
        stripped = line.strip().lower()
        if any(re.search(pattern, stripped) for pattern in DAY_HEADING_PATTERNS):
            count += 1
    return count


def validate_text(text: str, review: dict[str, Any] | None = None) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    lowered = text.lower()

    leaked = [term for term in FORBIDDEN_TERMS if term.lower() in lowered]
    if leaked:
        issues.append(issue("text.internal_jargon", "Traveler-facing text leaks internal terms: " + ", ".join(leaked)))

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    bullet_lines = [line for line in lines if re.match(r"^(-|\*|\d+\.|[A-Z]\d{2}\b|P\d{2}\b)", line)]
    prose_paragraphs = [
        line
        for line in lines
        if len(line) >= 100 and not line.startswith("#") and not re.match(r"^(-|\*|\d+\.)", line)
    ]
    if len(prose_paragraphs) < 2 or (lines and len(bullet_lines) / len(lines) > 0.55):
        issues.append(issue("text.bullet_list_only", "Traveler-facing text reads like a bullet list rather than guide prose."))

    local_texture_count = count_patterns(text, LOCAL_TEXTURE_PATTERNS)
    if local_texture_count < 7:
        issues.append(issue("text.local_texture.too_thin", f"Local food, shop, hotel, rest, and souvenir texture is too thin: {local_texture_count}."))

    if review:
        named_risks = review.get("observed_risks")
        named_fallbacks = review.get("observed_fallbacks")
        has_named_risk = isinstance(named_risks, list) and any(str(value).lower() in lowered for value in named_risks)
        has_named_fallback = isinstance(named_fallbacks, list) and any(str(value).lower() in lowered for value in named_fallbacks)
        if not has_named_risk or not has_named_fallback:
            issues.append(issue("text.generic_risk", "Risk notes need an artifact-observed risk and named fallback."))
    else:
        risk_count = lowered.count("risk") + lowered.count("pitfall") + lowered.count("avoid")
        specificity_count = count_patterns(text, RISK_SPECIFICITY_PATTERNS)
        if risk_count < 1 or specificity_count < 4:
            issues.append(issue("text.generic_risk", "Risk notes need concrete triggers, mitigations, and named fallback behavior."))

    weather_mentions = count_patterns(text, WEATHER_PATTERNS)
    if weather_mentions:
        weather_evidence = review.get("observed_weather_evidence") if review else None
        weather_status = review.get("weather_claim_status") if review else None
        weather_source_mode = review.get("observed_weather_source_mode") if review else None
        checked_hazards = review.get("observed_weather_checked_hazards") if review else None
        missing_hazards = review.get("observed_weather_missing_or_downgraded_hazards") if review else None
        if not nonempty(weather_evidence) or weather_status not in VALID_WEATHER_CLAIM_STATUSES:
            issues.append(issue("text.weather_evidence_missing", "Dated or weather-sensitive guide mentions weather without checked, partial, downgraded, or bounded weather evidence."))
        if weather_source_mode not in VALID_WEATHER_SOURCE_MODES:
            issues.append(issue("text.weather_source_mode_missing", "Weather-sensitive guide needs observed_weather_source_mode: forecast, historical_observed, climate, alert, mixed, or missing."))
        if not nonempty(checked_hazards):
            issues.append(issue("text.weather_hazards_missing", "Weather-sensitive guide needs checked hazard coverage such as precipitation, heat, wind, storm, typhoon, air_quality, or alert."))
        if missing_hazards is None or missing_hazards == "":
            issues.append(issue("text.weather_hazard_boundary_missing", "Weather-sensitive guide needs missing or downgraded weather hazards, even when the value is an empty list."))

    days = observed_day_count(review)
    if days > 1:
        heading_count = count_day_headings(text)
        if heading_count != days:
            issues.append(issue("text.day_headings_missing", "Traveler-facing text needs exactly one recognizable day/date heading per observed day."))
        if heading_count == 0 and len(prose_paragraphs) >= 2:
            issues.append(issue("text.structure_too_flat", "Multi-day traveler-facing text is too flat; preserve light day/date structure while keeping prose."))

    if review:
        headings = review.get("observed_day_headings")
        if not isinstance(headings, list) or len(headings) != days or any(str(value).lower() not in lowered for value in headings):
            issues.append(issue("text.reverse_review.day_heading_mismatch", "Reverse review day headings must exactly cover headings visible in the artifact."))
        for field in ("observed_local_food_details", "observed_shopping_details", "observed_rest_nodes"):
            values = review.get(field)
            if not isinstance(values, list) or not values or any(str(value).lower() not in lowered for value in values):
                issues.append(issue("text.reverse_review.observation_mismatch", f"Reverse review {field} contains a detail not present in the artifact."))
        for field in ("observed_risks", "observed_fallbacks"):
            values = review.get(field)
            if not isinstance(values, list) or not values or not any(str(value).lower() in lowered for value in values):
                issues.append(issue("text.reverse_review.observation_mismatch", f"Reverse review {field} has no named observation present in the artifact."))

    return issues


def validate_review(review: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    required = (
        "final_artifact_ref",
        "final_artifact_path",
        "final_artifact_sha256",
        "observed_days",
        "observed_day_headings",
        "observed_local_food_details",
        "observed_shopping_details",
        "observed_rest_nodes",
        "observed_weather_evidence",
        "observed_weather_source_type",
        "observed_weather_source_mode",
        "observed_weather_checked_hazards",
        "weather_claim_status",
        "weather_route_adjustments",
        "observed_risks",
        "observed_fallbacks",
        "internal_label_leakage",
        "promise_alignment_status",
        "continuity_status",
        "status",
    )
    for field in required:
        if field not in review or review.get(field) in ("", [], None):
            issues.append(issue("text.reverse_review.missing", f"Reverse guide review is missing {field}."))
    if "observed_weather_missing_or_downgraded_hazards" not in review or review.get("observed_weather_missing_or_downgraded_hazards") in ("", None):
        issues.append(issue("text.reverse_review.missing", "Reverse guide review is missing observed_weather_missing_or_downgraded_hazards."))
    if review.get("status") != "pass":
        issues.append(issue("text.reverse_review.status", "Reverse guide review status must be pass."))
    if review.get("internal_label_leakage") not in (False, [], "none"):
        issues.append(issue("text.reverse_review.internal_jargon", "Reverse guide review found internal label leakage."))
    if review.get("weather_claim_status") not in VALID_WEATHER_CLAIM_STATUSES:
        issues.append(issue("text.reverse_review.weather_status", "weather_claim_status must be checked, partial, downgraded, missing_with_boundary, or not_applicable."))
    if review.get("observed_weather_source_mode") not in VALID_WEATHER_SOURCE_MODES:
        issues.append(issue("text.reverse_review.weather_source_mode", "observed_weather_source_mode must be forecast, forecast_alert, historical_observed, historical, archive, climate, alert, mixed, or missing."))
    return issues


def validate_good_dir(good_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for path in sorted(good_dir.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        issues: list[dict[str, str]] = []
        review_path = path.with_suffix(".review.json")
        if not review_path.exists():
            issues.append(issue("text.reverse_review.missing", f"Missing reverse review sidecar for {path.name}."))
            issues.extend(validate_text(text))
        else:
            loaded = json.loads(review_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                issues.append(issue("text.reverse_review.invalid", f"{review_path.name} must contain a JSON object."))
                issues.extend(validate_text(text))
            else:
                actual_hash = hashlib.sha256(path.read_bytes()).hexdigest().upper()
                if loaded.get("final_artifact_ref") != path.name or loaded.get("final_artifact_path") != path.name:
                    issues.append(issue("text.reverse_review.artifact_path_mismatch", "Good-text reverse review must bind the exact sibling artifact name."))
                if str(loaded.get("final_artifact_sha256", "")).upper() != actual_hash:
                    issues.append(issue("text.reverse_review.artifact_hash_mismatch", "Good-text reverse review must bind the current artifact bytes."))
                issues.extend(validate_text(text, loaded))
                issues.extend(validate_review(loaded))
        results.append({"case": str(path), "expected": "pass", "issues": issues, "ok": not issues})
    if not results:
        results.append({"case": str(good_dir), "expected": "at_least_one_good_text", "issues": [issue("text.good_cases.missing", "No good text outputs found.")], "ok": False})
    return results


def validate_failure_dir(failure_dir: Path, repository_root: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for path in sorted(failure_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        expected = data.get("expected_issue_codes")
        if data.get("schema_version") != "travel-story-planner.text-failure-case.v3" or not isinstance(expected, list) or not expected:
            results.append({"case": str(path), "expected_issue_codes": expected, "issue_codes": ["text.failure_case.schema_invalid"], "ok": False})
            continue
        text_path = (repository_root / str(data.get("base_text", ""))).resolve()
        review_path = (repository_root / str(data.get("base_review", ""))).resolve()
        try:
            text = text_path.read_bytes().decode("utf-8")
            review = json.loads(review_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            results.append({"case": str(path), "expected_issue_codes": expected, "issue_codes": [f"text.failure_case.base_invalid:{exc}"], "ok": False})
            continue
        if not isinstance(review, dict) or validate_text(text, review) or validate_review(review):
            results.append({"case": str(path), "expected_issue_codes": expected, "issue_codes": ["text.failure_case.base_not_current"], "ok": False})
            continue
        mutation_failed = False
        for position, mutation in enumerate(data.get("text_mutations", [])):
            if not isinstance(mutation, dict):
                results.append({"case": str(path), "expected_issue_codes": expected, "issue_codes": [f"text.failure_case.text_mutation_invalid:{position}"], "ok": False})
                mutation_failed = True
                break
            if mutation.get("op") == "set":
                text = str(mutation.get("value", ""))
            elif mutation.get("op") == "replace":
                old = str(mutation.get("old", ""))
                count = int(mutation.get("count", 1))
                if not old or text.count(old) != count:
                    results.append({"case": str(path), "expected_issue_codes": expected, "issue_codes": [f"text.failure_case.text_mutation_invalid:{position}"], "ok": False})
                    mutation_failed = True
                    break
                text = text.replace(old, str(mutation.get("new", "")), count)
            else:
                results.append({"case": str(path), "expected_issue_codes": expected, "issue_codes": [f"text.failure_case.text_mutation_invalid:{position}"], "ok": False})
                mutation_failed = True
                break
        if mutation_failed:
            continue
        try:
            review = apply_mutations(review, data.get("review_mutations", []))
        except MutationError as exc:
            results.append({"case": str(path), "expected_issue_codes": expected, "issue_codes": [f"text.failure_case.review_mutation_invalid:{exc}"], "ok": False})
            continue
        if data.get("drop_review") is True:
            review = None
        issues = validate_text(text, review)
        if isinstance(review, dict):
            actual_hash = hashlib.sha256(text.encode("utf-8")).hexdigest().upper()
            if review.get("final_artifact_ref") != text_path.name or review.get("final_artifact_path") != text_path.name:
                issues.append(issue("text.reverse_review.artifact_path_mismatch", "Failure mutation review must remain bound to the base artifact identity."))
            if str(review.get("final_artifact_sha256", "")).upper() != actual_hash:
                issues.append(issue("text.reverse_review.artifact_hash_mismatch", "Failure mutation changed text without a matching reverse-review hash."))
            issues.extend(validate_review(review))
        else:
            issues.append(issue("text.reverse_review.missing", "Failure fixture has no reverse review."))
        codes = sorted({item["code"] for item in issues})
        expected_codes = sorted(set(expected))
        results.append({"case": str(path), "expected_issue_codes": expected_codes, "issue_codes": codes, "ok": bool(issues) and codes == expected_codes})
    if not results:
        results.append({"case": str(failure_dir), "expected_issue": "text.failure_cases.missing", "issue_codes": ["text.failure_cases.missing"], "ok": False})
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--good-dir", required=True)
    parser.add_argument("--failure-dir", required=True)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    good_results = validate_good_dir(Path(args.good_dir))
    failure_results = validate_failure_dir(Path(args.failure_dir), Path(args.repository_root).resolve())
    results = good_results + failure_results
    ok = all(row["ok"] for row in results)
    payload = {"ok": ok, "results": results}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("PASS" if ok else "FAIL")
        for row in results:
            print(f"- {row['case']}: {row['ok']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
