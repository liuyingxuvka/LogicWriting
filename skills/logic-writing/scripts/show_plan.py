#!/usr/bin/env python3
"""Read the plan and available text bindings at any reader-chain step; never write."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re

from _common import load_request
from artifact_map import validate_artifact_map
from reader_fill import fill_check_fingerprints
from reader_binding import _shared_writing_from_current
from world_refs import planned_world_refs

# Result files of the same chain, read beside the input like reader-brief.json and artifact-map.json.
RESULTS = (('audit', 'audit.json', 'findings', ('reader_audit', 'deterministic_audit')),
           ('review', 'route-review-result.json', 'review_fingerprint', ('route_review',)),
           ('closure', 'closure.json', 'closure_fingerprint', ('closure',)))


def _find_record(value, marker, wrappers):
    if not isinstance(value, dict):
        return None
    for name in wrappers:
        child = value.get(name)
        if isinstance(child, dict) and marker in child:
            return child
    if marker in value:
        return value
    return None


def _records(request, input_path=None):
    brief = _find_record(request, 'composition_plan', ('reader_brief',))
    if brief is None and input_path is not None:
        sibling = Path(input_path).resolve().parent / 'reader-brief.json'
        if sibling.is_file() and sibling != Path(input_path).resolve():
            brief = _find_record(load_request(sibling), 'composition_plan', ('reader_brief',))
    if brief is None:
        raise ValueError('no composition plan; supply a brief request/result or a chain file beside reader-brief.json')
    plan = brief.get('composition_plan')
    if not isinstance(plan, dict) or not isinstance(plan.get('planned_units'), list):
        raise ValueError('the input has no readable composition_plan.planned_units')
    if any(not isinstance(row, dict) for row in plan['planned_units']):
        raise ValueError('planned_units must contain readable unit records')
    shared = _find_record(request, 'unit_bindings', ('shared_writing', 'contract'))
    amap = _find_record(request, 'units', ('artifact_map',))
    if shared is not None and amap is None and input_path is not None:
        sibling = Path(input_path).resolve().parent / 'artifact-map.json'
        if sibling.is_file():
            amap = _find_record(load_request(sibling), 'units', ('artifact_map',))
    return brief, plan, shared or {}, amap or {}


def _results(request, input_path, amap):
    """The chain's audit, review and closure records; `stale` when not made from the current bytes."""
    found = {}
    for name, filename, marker, wrappers in RESULTS:
        record = _find_record(request, marker, wrappers)
        if record is None and input_path is not None:
            sibling = Path(input_path).resolve().parent / filename
            if sibling.is_file() and sibling != Path(input_path).resolve():
                try:
                    record = _find_record(json.loads(sibling.read_text(encoding='utf-8')), marker, wrappers)
                except (OSError, UnicodeError, ValueError):
                    record = None
        if record is None or not amap:
            found[name] = None
        elif record.get('artifact_fingerprint') != amap.get('artifact_fingerprint'):
            found[name] = 'stale'
        else:
            found[name] = record
    return found


def _excerpt(text):
    text = ' '.join(str(text).split())
    return text if len(text) <= 80 else text[:77] + '...'


def _unit_findings(ids, results):
    """Audit and review findings and quoted checks that land on these artifact units."""
    rows = []
    audit, review = results['audit'], results['review']
    if isinstance(audit, dict):
        rows += [dict(code=row['code'], message=row['message'], source='audit')
                 for row in audit.get('findings', []) if set(row.get('affected_unit_ids', [])) & ids]
    if isinstance(review, dict):
        for row in review.get('findings', []):
            evidence = row.get('evidence') or {}
            if evidence.get('artifact_unit_id') in ids:
                rows.append(dict(code=row.get('dimension_id', ''), message=row.get('observation', ''),
                                 excerpt=_excerpt(evidence.get('excerpt', '')), source='review'))
        for key, identity in (('limitation_checks', 'limitation_id'), ('overclaim_checks', 'overclaim_id'),
                              ('world_ref_checks', 'world_ref')):
            for row in review.get(key, []):
                for evidence in row.get('evidence', []):
                    if evidence.get('artifact_unit_id') in ids:
                        rows.append(dict(code=f"{key[:-7]} {row.get(identity, '')}", message=row.get('status', 'quoted'),
                                         excerpt=_excerpt(evidence.get('excerpt', '')), source='review'))
    return rows


def _status(record, findings=None):
    if record is None:
        return 'not_run'
    if record == 'stale':
        return 'stale'
    status = record.get('status', 'unknown')
    return f"{status} ({len(record.get('findings', []))} findings)" if findings else status


def _summary(view, results):
    units = view['planned_units']
    bound = sum(1 for unit in units if unit['bound'])
    closure = results['closure']
    if isinstance(closure, dict):
        uncaught = sum(1 for row in closure.get('residual_risk', []) if str(row.get('defect_id', '')).startswith('toothless:'))
        known_bad = f'{uncaught} uncaught'
    else:
        known_bad = _status(closure)
    return (f"units: {len(units)} ({bound} bound, {len(units) - bound} unbound); "
            f"audit: {_status(results['audit'], True)}; review: {_status(results['review'])}; "
            f"closure: {_status(closure)}; known-bad: {known_bad}")


def _tree_order(rows):
    children = {}
    identities = {row.get('planned_unit_id') for row in rows}
    for row in sorted(rows, key=lambda item: item.get('order', 0)):
        parent = row.get('parent_unit_id')
        children.setdefault(parent if parent in identities else None, []).append(row)
    ordered, seen = [], set()

    def visit(row, depth):
        identity = row.get('planned_unit_id')
        if identity in seen:
            return
        seen.add(identity)
        ordered.append((row, depth))
        for child in children.get(identity, []):
            visit(child, depth + 1)
    for row in children.get(None, []):
        visit(row, 0)
    for row in rows:
        if row.get('planned_unit_id') not in seen:
            visit(row, 0)
    return ordered


def plan_view(request, *, input_path=None):
    brief, plan, shared, amap = _records(request, input_path)
    if shared.get('unit_bindings') and amap:
        current_map = validate_artifact_map(amap)
        envelope = fill_check_fingerprints(deepcopy(dict(
            reader_brief=brief, artifact_map=current_map, contract=shared)))
        shared = _shared_writing_from_current(envelope['contract'],
            amap=current_map, reader_brief=brief)
        amap = current_map
    else:
        # A plan alone (or an as-yet unbound draft) makes no text-binding claim.
        shared = {}
    units = {row['artifact_unit_id']: row for row in amap.get('units', [])}
    boundaries = brief.get('content_boundaries') or {}
    if not isinstance(boundaries, dict):
        raise ValueError('content_boundaries is not a readable record')
    content = {row['content_unit_id']: row['safe_meaning'] for row in boundaries.get('content_units', [])}
    content_anchors = {row['content_unit_id']: row.get('evidence_anchor_ids', []) for row in boundaries.get('content_units', [])}
    relations = {row['anchor_id']: row.get('relation', '') for row in boundaries.get('evidence_anchors', [])}
    world = planned_world_refs(plan)
    results = _results(request, input_path, amap)
    provenance = _find_record(request, 'unit_treatments', ('revision_provenance', 'provenance')) or {}
    treatments = provenance.get('unit_treatments') or []
    limitations = {row['limitation_id']: row['safe_meaning'] for row in boundaries.get('limitations', [])}
    result = dict(central_question=plan.get('central_question', ''),
                  central_throughline=plan.get('central_throughline', ''), planned_units=[])
    for unit, depth in _tree_order(plan['planned_units']):
        bindings = [row for row in shared.get('unit_bindings', [])
                    if row.get('planned_unit_id') == unit['planned_unit_id']]
        ids = list(dict.fromkeys(identity for row in bindings for identity in row.get('artifact_unit_ids', [])))
        texts = [units[identity]['text'] for identity in ids]
        texts = [re.split(r'(?<=[.!?。！？])\s+', text, maxsplit=1)[0][:110] for text in texts]
        result['planned_units'].append(dict(order=unit.get('order'),
            planned_unit_id=unit['planned_unit_id'], parent_unit_id=unit.get('parent_unit_id'), depth=depth,
            title=unit.get('title', unit['planned_unit_id']), bound_unit_ids=ids,
            bound=bool(bindings), reader_job=unit.get('reader_job', ''),
            incoming_reader_state=unit.get('incoming_reader_state', ''),
            outgoing_reader_state=unit.get('outgoing_reader_state', ''),
            content=[content.get(identity, identity) for identity in unit.get('content_unit_ids', [])],
            limitations=[limitations.get(identity, identity) for identity in unit.get('limitation_ids', [])], text=texts,
            findings=_unit_findings(set(ids), results),
            anchors=[dict(anchor_id=anchor, relation=relations.get(anchor, ''))
                     for identity in unit.get('content_unit_ids', []) for anchor in content_anchors.get(identity, [])],
            world_refs=list(world.get(unit['planned_unit_id'], ())),
            **{'from': [dict(source_unit_id=row.get('source_unit_id'), treatment=row.get('treatment'))
                        for row in treatments if unit['planned_unit_id'] in row.get('target_unit_ids', [])]}))
    audit = results['audit']
    result['document'] = ([dict(code=row['code'], message=row['message']) for row in audit.get('findings', [])
                           if 'artifact:document' in row.get('affected_unit_ids', [])] if isinstance(audit, dict) else [])
    result['summary'] = _summary(result, results)
    return result


def render_plan(view):
    lines = [view['summary']]
    lines += [f"document: {row['code']}: {row['message']}" for row in view['document']]
    lines += [f"Q: {view['central_question']}", f"Throughline: {view['central_throughline']}"]
    for unit in view['planned_units']:
        padding = '  ' * unit['depth']
        where = ', '.join(unit['bound_unit_ids']) or ('BOUND' if unit['bound'] else 'UNBOUND')
        lines += ['', f"{padding}{unit['order']}. {unit['title']} [{where}]",
                  f"{padding}   job: {unit['reader_job']}",
                  f"{padding}   reader: {unit['incoming_reader_state']} -> {unit['outgoing_reader_state']}"]
        for key, label in (('content', 'says'), ('limitations', 'limit'), ('text', 'text')):
            lines += [f'{padding}   {label}: {text}' for text in unit[key]]
        for row in unit['findings']:
            quote = f' "{row["excerpt"]}"' if row.get('excerpt') else ''
            lines.append(f"{padding}   findings: {row['code']}: {row['message']}{quote}")
        if unit['anchors']:
            lines.append(f"{padding}   anchors: " + ', '.join(f"{row['anchor_id']} ({row['relation']})" for row in unit['anchors']))
        if unit['world_refs']:
            lines.append(f"{padding}   world: " + ', '.join(unit['world_refs']))
        if unit['from']:
            lines.append(f"{padding}   from: " + ', '.join(f"{row['source_unit_id']} ({row['treatment']})" for row in unit['from']))
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    try:
        view = plan_view(load_request(args.input), input_path=args.input)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f'show_plan: {exc}')
        return 2
    print(json.dumps(view, ensure_ascii=False, indent=2) if args.json else render_plan(view))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
