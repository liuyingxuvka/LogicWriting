"""Shared primitive checks; native fiction reporters keep their own context."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
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


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def check_duplicate_ids(rows, reporter, subject):
    observed = {}
    for path, row in rows:
        identifier = row.get("id")
        if not isinstance(identifier, str) or is_blank_or_placeholder(identifier):
            continue
        if identifier in observed:
            reporter.error(f"duplicate_{subject}_id", f"{path}.id" if path else "id",
                           f"{subject.title()} id {identifier!r} duplicates {observed[identifier]}.", identifier, "id")
        else:
            observed[identifier] = path


def print_text_report(report, title, subject):
    print(f"{title}: {'passed' if report['passed'] else 'failed'}")
    print(f"Source: {report['source_path']}")
    print(f"Collection: {report['collection_path']}")
    print("Issues: " f"{report['summary']['error_count']} error(s), "
          f"{report['summary']['warning_count']} warning(s)")
    for issue in report["issues"]:
        key = f"{subject}_id"
        suffix = f" {subject}={issue[key]}" if key in issue else ""
        field_suffix = f" field={issue['field']}" if "field" in issue else ""
        print(f"- [{issue['severity']}] {issue['code']} at {issue['path']}{suffix}{field_suffix}: {issue['message']}")


def json_check_cli(argv, *, description, input_help, load, validate, error_report, print_report):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("input", help=input_help)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON report.")
    args = parser.parse_args(argv)
    path = Path(args.input)
    try:
        payload = load(path)
    except OSError as exc:
        report = error_report(str(path), "read_error", str(exc))
    except json.JSONDecodeError as exc:
        report = error_report(str(path), "json_decode_error", f"{exc.msg} at line {exc.lineno}, column {exc.colno}")
    else:
        report = validate(payload, str(path))
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_report(report)
    return 0 if report["passed"] else 1
