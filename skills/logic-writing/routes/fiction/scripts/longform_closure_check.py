#!/usr/bin/env python3
"""Compute long-form surface checks directly from a project's current model files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fiction_plan import load_context, member


_RETIRED = {'required_surfaces', 'decision', 'child_reports', 'deferred_items',
            'blocking_items', 'stale_items', 'status', 'passed'}


class Reporter:
    def __init__(self):
        self.issues = []

    def error(self, code, path, message):
        self.issues.append(dict(severity='error', code=code, path=path, message=message))


def _error_count(issues):
    return sum(row.get('severity', 'error') == 'error' for row in issues)


def _report(source_path, reporter, **extra):
    return dict(source_path=str(source_path), passed=_error_count(reporter.issues) == 0,
                summary=dict(error_count=_error_count(reporter.issues), issue_count=len(reporter.issues)),
                issues=reporter.issues, **extra)


def _retired_fields(payload, fields, reporter, path='$'):
    if isinstance(payload, dict):
        for name in sorted(fields & payload.keys()):
            reporter.error('retired_closure_field', f'{path}.{name}',
                           f'{name} is retired; results are computed from current surface checks.')


def reverse_outline_rows(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get('reverse_outlines'), list):
            return payload['reverse_outlines']
        bundle = payload.get('chapter_interface_bundle', {})
        if isinstance(bundle, dict) and isinstance(bundle.get('reverse_outlines'), list):
            return bundle['reverse_outlines']
    return []


def validate_reverse_outline_evidence(payload, source_path):
    reporter = Reporter()
    context = load_context(payload, source_path, reporter)
    rows = reverse_outline_rows(payload)
    if not rows:
        reporter.error('missing_reverse_outlines', 'reverse_outlines',
                       'Actual-prose reverse-outline rows are required.')
    for index, row in enumerate(rows):
        path = f'reverse_outlines[{index}]'
        if not isinstance(row, dict):
            reporter.error('invalid_row_type', path, 'Reverse-outline row must be an object.')
            continue
        _retired_fields(row, {'status', 'model_alignment'}, reporter, path)
        for field in ('id', 'planned_unit_id', 'source_draft_ref'):
            if not isinstance(row.get(field), str) or not row[field].strip():
                reporter.error('missing_required_field', f'{path}.{field}', f'{field} is required.')
        member(context, row.get('planned_unit_id'), 'reverse_outline',
               f'{path}.planned_unit_id', reporter)
        for field in ('observed_events', 'observed_reader_state_after',
                      'observed_promise_movements', 'observed_arc_movements'):
            if not isinstance(row.get(field), list) or not row[field]:
                reporter.error('empty_required_list', f'{path}.{field}',
                               'Reverse-outline evidence must name actual events and states.')
        if not isinstance(row.get('drift'), list):
            reporter.error('invalid_type', f'{path}.drift', 'drift must be a list.')
        elif row['drift']:
            reporter.error(f"reverse_outline_drift:{row.get('planned_unit_id', '?')}",
                           f'{path}.drift', 'The actual-prose reading declares unresolved drift.')
    return _report(source_path, reporter)


def _read_reference(reference, source_path, reporter, field):
    if not isinstance(reference, str) or not reference.strip():
        reporter.error('source_evidence_missing', field, 'A nonempty local evidence_ref is required.')
        return
    raw = reference.split(';', 1)[0].strip()
    if raw.startswith('file:'):
        raw = raw[5:]
    raw = raw.split('#', 1)[0]
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path(source_path).resolve().parent / path
    try:
        path.read_bytes()
    except (OSError, ValueError) as exc:
        reporter.error('source_evidence_unresolved', field, f'Cannot resolve {reference!r}: {exc}')


def validate_source_requirements_evidence(payload, source_path):
    """Resolve source pointers; satisfaction belongs to quoted route review."""
    reporter = Reporter()
    if not isinstance(payload, dict):
        reporter.error('invalid_source_requirements', '$', 'Source requirements must be an object.')
        return _report(source_path, reporter)
    _retired_fields(payload, {'decision', 'unmet_requirements', 'artifact_sha256'}, reporter)
    rows = payload.get('requirements')
    if not isinstance(rows, list) or not rows:
        reporter.error('missing_source_requirements', 'requirements', 'Structured requirements are required.')
        rows = []
    context = load_context(payload, str(source_path), reporter) if any(
        isinstance(row, dict) and row.get('planned_unit_ids') for row in rows) else None
    for index, row in enumerate(rows):
        field = f'requirements[{index}]'
        if not isinstance(row, dict):
            reporter.error('invalid_source_requirement', field, 'Requirement must be an object.')
            continue
        _retired_fields(row, {'status', 'decision'}, reporter, field)
        for key in ('id', 'requirement'):
            if not isinstance(row.get(key), str) or not row[key].strip():
                reporter.error('missing_required_field', f'{field}.{key}', f'{key} is required.')
        identifiers = row.get('planned_unit_ids', [])
        if not isinstance(identifiers, list) or any(not isinstance(item, str) for item in identifiers):
            reporter.error('invalid_type', f'{field}.planned_unit_ids', 'Expected planned-unit id strings.')
        else:
            for identifier in identifiers:
                member(context, identifier, 'source_requirements', f'{field}.planned_unit_ids', reporter)
        _read_reference(row.get('evidence_ref'), source_path, reporter, f'{field}.evidence_ref')
    return _report(source_path, reporter)


def _native_surface(kind, payload, source_path):
    if kind == 'novel_ledger':
        from novel_ledger_check import validate_ledger
        return validate_ledger(payload, source_path)
    if kind == 'chapter_interfaces':
        from chapter_interface_check import validate as check
        report = check(payload, source_path)
        reverse = validate_reverse_outline_evidence(payload, source_path)
        report['issues'] = [*report['issues'], *reverse['issues']]
        report['passed'] = bool(report['passed']) and reverse['passed']
        report['summary']['error_count'] = sum(row.get('severity') == 'error' for row in report['issues'])
        return report
    if kind == 'story_contribution':
        from story_contribution_check import validate as check
        return check(payload, source_path)
    if kind == 'promise_payoff':
        from promise_payoff_check import validate_promises
        return validate_promises(payload, source_path)
    if kind == 'voice_style':
        from voice_style_continuity_check import validate as check
        return check(payload, source_path)
    if kind == 'reverse_outline':
        return validate_reverse_outline_evidence(payload, source_path)
    if kind == 'source_requirements':
        return validate_source_requirements_evidence(payload, source_path)
    reporter = Reporter()
    if kind == 'composition_plan':
        load_context({'composition_plan': payload}, source_path, reporter)
    else:
        reporter.error('unknown_native_owner', f'surfaces.{kind}',
                       f'No native surface validator is registered for {kind!r}.')
    return _report(source_path, reporter)


def validate(payload: Any, source_path: str, repository_root: str | Path | None = None):
    """Read a project mesh and run each declared surface in this process."""
    reporter = Reporter()
    checks = {}
    payloads = {}
    if not isinstance(payload, dict):
        reporter.error('invalid_root_type', '$', 'Longform input must be a project mesh.')
        payload = {}
    _retired_fields(payload, _RETIRED, reporter)
    if payload.get('schema_version') != 'storyline-design.project_mesh.v1':
        reporter.error('invalid_schema_version', 'schema_version', 'Use the project-mesh input.')
    for name in ('project_id', 'model_revision'):
        if not isinstance(payload.get(name), str) or not payload[name].strip():
            reporter.error('missing_required_field', name, f'{name} is required.')
    surfaces = payload.get('surfaces')
    if not isinstance(surfaces, dict) or not surfaces:
        reporter.error('missing_surfaces', 'surfaces', 'The project must declare its current native surfaces.')
        surfaces = {}
    base = Path(source_path).resolve().parent
    # Pure graph/path helpers only: never call mesh's recursive native-owner driver.
    from storyline_project_mesh_check import contained, validate_graph
    for kind, relative in surfaces.items():
        local = Reporter()
        path = contained(base, relative, local, f'surfaces.{kind}')
        if path is not None:
            try:
                if kind == 'final_artifact':
                    path.read_bytes().decode('utf-8')
                    report = _report(path, local)
                else:
                    data = json.loads(path.read_text(encoding='utf-8'))
                    payloads[kind] = data
                    report = _native_surface(kind, data, str(path))
                    if kind != 'composition_plan' and isinstance(data, dict):
                        current = data.get('novel_ledger', data)
                        if not isinstance(current, dict):
                            current = {}
                        for field in ('project_id', 'model_revision'):
                            if current.get(field) != payload.get(field):
                                local.error('project_identity_mismatch', f'surfaces.{kind}.{field}',
                                            f'{field} must match the project mesh.')
                local.issues.extend(report['issues'])
                if not report['passed'] and _error_count(local.issues) == 0:
                    local.error('surface_not_passed', f'surfaces.{kind}', 'Native surface validation failed.')
            except (OSError, UnicodeError, ValueError) as exc:
                local.error('surface_read_error', f'surfaces.{kind}', str(exc))
        checks[kind] = _report(str(path or relative), local)
        reporter.issues.extend(dict(issue, surface=kind) for issue in local.issues)
    if 'composition_plan' not in payloads or checks['composition_plan']['passed']:
        graph = Reporter()
        validate_graph(payloads, payload, graph)
        checks['project_graph'] = _report(source_path, graph)
        reporter.issues.extend(dict(issue, surface='project_graph') for issue in graph.issues)
    result = _report(source_path, reporter, surface_checks=checks,
                     decision='passed' if _error_count(reporter.issues) == 0 else 'needs_repair')
    result['schema_version'] = 'storyline-design.longform_closure_check.report.v2'
    result['summary']['surface_count'] = len(surfaces)
    return result


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('--repo-root')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        report = validate(load_json(args.input), args.input, args.repo_root)
    except (OSError, UnicodeError, ValueError) as exc:
        reporter = Reporter()
        reporter.error('read_error', args.input, str(exc))
        report = _report(args.input, reporter, decision='needs_repair', surface_checks={})
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Longform closure check: {report['decision']}")
        for name, check in report['surface_checks'].items():
            codes = ', '.join(row['code'] for row in check['issues'])
            print(f"- {name}: {'passed' if check['passed'] else codes}")
        for issue in report['issues']:
            if 'surface' not in issue:
                print(f"- {issue['code']} at {issue['path']}: {issue['message']}")
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
