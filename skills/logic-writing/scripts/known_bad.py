#!/usr/bin/env python3
"""Deterministic known-bad edits of a piece, checked by its existing reader chain."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re

from _common import ValidationError, dump_json, load_request, require_mapping, validation_result
from artifact_map import build_artifact_map_from_text, validate_artifact_map
from reader_fill import fill_check_fingerprints
from reader_binding import shared_writing_from_current
from reader_checks import build_reader_audit_from_current, route_review_from_current


# First named term in _common.contains_internal_language's existing glossary.
_INTERNAL_TERM = "SourceGuard"
_BODY_KINDS = {"paragraph", "list", "table", "quote", "scene", "code"}


def _first_body_end(amap):
    return next((row['end'] for row in amap['units'] if row['unit_kind'] == 'paragraph'),
                next((row['end'] for row in amap['units'] if row['unit_kind'] in _BODY_KINDS), 0))


def _without_sentence(text, excerpt):
    """Delete only the existing sentence(s) carrying the saved limitation quote."""
    start = text.find(excerpt)
    if start < 0:
        raise ValidationError('limitation excerpt is absent from the current text')
    end = start + len(excerpt)
    boundaries = [match.end() for match in re.finditer(r'''[.!?。！？]["'”’]*\s+''', text)]
    left = max([0, *(position for position in boundaries if position <= start)])
    right = next((position for position in boundaries if position >= end), len(text))
    remaining = text[:left] + text[right:]
    if right == len(text):
        # Preserve the original terminal newline while deleting the removed sentence's dangling space.
        newline = "\r\n" if text.endswith("\r\n") else "\n" if text.endswith("\n") else ""
        remaining = remaining.rstrip() + newline
    return remaining


def _safe(identity):
    return re.sub(r'[^A-Za-z0-9_.-]', '_', identity)


def _relation_variants(text, *, planned, boundaries, artifact_map, shared_writing, route_review):
    """Edits that break the plan's relations: sibling order, world references, live alternatives."""
    cases = []
    spans = {row['artifact_unit_id']: (row['start'], row['end']) for row in artifact_map['units']}
    bound = {}
    for binding in shared_writing['unit_bindings']:
        places = [spans[identity] for identity in binding.get('artifact_unit_ids', []) if identity in spans]
        if places:
            start, end = min(place[0] for place in places), max(place[1] for place in places)
            old = bound.get(binding['planned_unit_id'])
            bound[binding['planned_unit_id']] = (min(start, old[0]), max(end, old[1])) if old else (start, end)
    siblings = {}
    for unit in planned:
        siblings.setdefault(unit.get('parent_unit_id'), []).append(unit)
    pair = None
    for children in siblings.values():
        ordered = sorted(children, key=lambda unit: unit.get('order', 0))
        for first, second in zip(ordered, ordered[1:]):
            a, b = bound.get(first['planned_unit_id']), bound.get(second['planned_unit_id'])
            if a and b and a[1] <= b[0]:
                pair = (first, second, a, b)
                break
        if pair:
            break
    if pair:
        first, second, a, b = pair
        # Move the existing text of the two sibling units past each other; nothing else changes.
        swapped = text[:a[0]] + text[b[0]:b[1]] + text[a[1]:b[0]] + text[a[0]:a[1]] + text[b[1]:]
        cases.append(dict(kind='swap', name='swap', unit=second['planned_unit_id'], text=swapped))
    refs = {unit['planned_unit_id'] for unit in planned if unit.get('world_refs')}
    for check in route_review.get('world_ref_checks', []):
        unit = check.get('planned_unit_id')
        if unit not in refs or not check.get('evidence'):
            continue
        changed = text
        for evidence in check['evidence']:
            if evidence['excerpt'] in changed:
                changed = _without_sentence(changed, evidence['excerpt'])
        if changed != text and not any(case['name'] == 'noworld-' + _safe(unit) for case in cases):
            cases.append(dict(kind='noworld', name='noworld-' + _safe(unit), unit=unit, text=changed))
    for alternative in boundaries.get('alternatives', []):
        if alternative.get('status') != 'live':
            continue
        contents = set(alternative.get('content_unit_ids', []))
        excerpt = next((quote for binding in shared_writing['unit_bindings']
                        if contents & set(binding.get('content_unit_ids', []))
                        for quote in binding.get('anchor_excerpts') or [] if quote in text), None)
        if excerpt is None:
            unit_ids = [identity for binding in shared_writing['unit_bindings']
                        if contents & set(binding.get('content_unit_ids', [])) for identity in binding.get('artifact_unit_ids', [])]
            first = next((spans[identity] for identity in unit_ids if identity in spans), None)
            if first is not None:
                excerpt = re.split(r'(?<=[.!?。！？])\s+', text[first[0]:first[1]].strip(), maxsplit=1)[0]
        if excerpt:
            identity = alternative['alternative_id']
            cases.append(dict(kind='noalt', name='noalt-' + _safe(identity), unit=identity,
                              text=_without_sentence(text, excerpt)))
    return cases


def text_variants(text, *, reader_brief, artifact_map, shared_writing, route_review):
    """Only delete, move or truncate text, or insert phrases already in its plan/glossary."""
    boundaries = reader_brief['content_boundaries']
    end = _first_body_end(artifact_map)
    cases = [dict(kind='empty', name='empty', unit=None, text=''),
             dict(kind='leak', name='leak', unit=None,
                  text=text[:end] + ' ' + _INTERNAL_TERM + text[end:])]
    citations = boundaries.get('citation_duties', [])
    if citations:
        changed = text
        for citation in citations:
            changed = changed.replace(citation['marker'], '')
        cases.append(dict(kind='nocite', name='nocite', unit=None, text=changed))
    tokens = boundaries.get('must_preserve_tokens', [])
    if tokens:
        token = tokens[0]
        cases.append(dict(kind='token', name='token', unit=token['token_id'],
                          text=text.replace(token['token'], '')))
    overclaims = boundaries.get('prohibited_overclaims', [])
    if overclaims:
        overclaim = overclaims[0]
        cases.append(dict(kind='overclaim', name='overclaim', unit=overclaim['overclaim_id'],
                          text=text[:end] + ' ' + overclaim['forbidden_meaning'] + text[end:]))
    applicable_limits = {row['limitation_id'] for row in reader_brief['composition_plan'].get(
        'limitation_dispositions', []) if row['disposition'] in {'body', 'note'}}
    for limitation in route_review.get('limitation_checks', []):
        if limitation['limitation_id'] not in applicable_limits or not limitation.get('evidence'):
            continue
        changed = text
        for evidence in limitation['evidence']:
            if evidence['excerpt'] not in text:
                raise ValidationError('limitation excerpt is absent from the current text')
            if evidence['excerpt'] in changed:
                changed = _without_sentence(changed, evidence['excerpt'])
        identity = limitation['limitation_id']
        cases.append(dict(kind='nolim', name='nolim-' + _safe(identity), unit=identity, text=changed))
    planned = reader_brief['composition_plan']['planned_units']
    cases.extend(_relation_variants(text, planned=planned, boundaries=boundaries, artifact_map=artifact_map,
                                    shared_writing=shared_writing, route_review=route_review))
    if len(planned) > 1:
        first_id = planned[0]['planned_unit_id']
        ids = {identity for binding in shared_writing['unit_bindings']
               if binding['planned_unit_id'] == first_id for identity in binding['artifact_unit_ids']}
        cutoff = max((row['end'] for row in artifact_map['units']
                      if row['artifact_unit_id'] in ids), default=end)
        cases.append(dict(kind='short', name='short', unit=first_id, text=text[:cutoff]))
    names = [case['name'] for case in cases]
    if len(names) != len(set(names)):
        raise ValidationError('known-bad variant filenames must be unique')
    return cases


def _clear_derived(contract, review):
    """Keep authored quotes; rebuild only derived current-byte references."""
    for key in ('contract_fingerprint', 'artifact_map_fingerprint', 'artifact_fingerprint'):
        contract.pop(key, None)
    for binding in contract.get('unit_bindings', []):
        if binding.get('anchor_excerpts') is not None:
            binding.pop('artifact_unit_ids', None)
            binding.pop('artifact_spans', None)
        else:
            for span in binding.get('artifact_spans', []):
                span.pop('locator', None)
                span.pop('content_fingerprint', None)
    for key in ('review_fingerprint', 'artifact_map_fingerprint', 'artifact_fingerprint'):
        review.pop(key, None)
    for row in [*review.get('dimensions', []), *review.get('limitation_checks', []),
                *review.get('overclaim_checks', []), *review.get('world_ref_checks', [])]:
        for evidence in row.get('evidence', []):
            evidence.pop('locator', None)
            evidence.pop('excerpt_fingerprint', None)
    for finding in review.get('findings', []):
        evidence = finding.get('evidence', {})
        evidence.pop('locator', None)
        evidence.pop('excerpt_fingerprint', None)


def _first_rejection(text, request):
    original = request['artifact_map']
    brief = request['reader_brief']
    contract = deepcopy(request['shared_writing'])
    review = deepcopy(request['route_review'])
    _clear_derived(contract, review)
    step = 'map'
    try:
        amap = build_artifact_map_from_text(text, artifact_path=original['artifact_path'],
            map_id=original['map_id'], language=original['language'],
            artifact_format=original['artifact_format'])
        step = 'shared_writing'
        envelope = fill_check_fingerprints(dict(artifact_map=amap, reader_brief=brief, contract=contract))
        shared = shared_writing_from_current(envelope['contract'], amap=amap, reader_brief=brief)
        step = 'audit'
        old_audit = request.get('deterministic_audit', {})
        audit = build_reader_audit_from_current(audit_id=old_audit.get('audit_id', 'known-bad'),
            amap=amap, brief=brief, contract=shared, audited_at=old_audit.get('audited_at'))
        if audit['status'] != 'passed':
            finding = audit['findings'][0]
            return dict(caught=True, step=step, code=finding['code'])
        step = 'review'
        envelope = fill_check_fingerprints(dict(artifact_map=amap, reader_brief=brief,
            shared_writing=shared, route_composition=brief['route_extension'], review=review))
        # Constant lookup only: never call closure or any provider recursively.
        from derive_closure import REQUIRED_DIMENSIONS
        checked = route_review_from_current(envelope['review'], owner=brief['final_owner'],
            route=brief['route_extension'], amap=amap,
            required_dimensions=REQUIRED_DIMENSIONS[brief['final_owner']],
            review_obligations=request.get('review_obligations'), brief=brief, shared=shared)
        if checked['status'] != 'passed':
            return dict(caught=True, step=step, error='route review requires repair')
    except ValidationError as exc:
        return dict(caught=True, step=step, error=str(exc))
    return dict(caught=False, step=None)


def _write_catalog(directory, cases, reports):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    expected = {}
    for case, report in zip(cases, reports):
        filename = case['name'] + '.md'
        (directory / filename).write_bytes(case['text'].encode('utf-8'))
        expected[filename] = ({key: report[key] for key in ('step', 'code', 'error') if key in report}
                              if report['caught'] else dict(step='uncaught', error='uncaught'))
    previous = directory / 'expected.json'
    if previous.exists():
        old = json.loads(previous.read_text(encoding='utf-8'))
        for name in old.keys() - expected.keys():
            if Path(name).name != name or not name.endswith('.md'):
                raise ValidationError('catalog contains an unsafe old filename')
            (directory / name).unlink(missing_ok=True)
    previous.write_text(json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def check_known_bad(value, *, write_catalog=None, _baseline_result=None):
    """Evaluate mutations against the real current chain, without writing the piece."""
    request = deepcopy(require_mapping(value, 'known-bad input'))
    original = validate_artifact_map(request['artifact_map'])
    text = Path(original['artifact_path']).read_bytes().decode('utf-8')
    # A broken baseline must not be reported as a collection of caught mutations.
    baseline = _first_rejection(text, request) if _baseline_result is None else _baseline_result
    if baseline['caught']:
        return dict(status='baseline_not_passed', baseline=baseline, variants=[])
    cases = text_variants(text, reader_brief=request['reader_brief'], artifact_map=original,
        shared_writing=request['shared_writing'], route_review=request['route_review'])
    reports = [dict(kind=case['kind'], name=case['name'], unit=case['unit'],
                    **_first_rejection(case['text'], request)) for case in cases]
    if write_catalog is not None:
        _write_catalog(write_catalog, cases, reports)
    return dict(status='passed' if all(row['caught'] for row in reports) else 'needs_repair',
                variants=reports)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--write-catalog')
    args = parser.parse_args()
    try:
        from derive_closure import CLOSURE_INPUT_FILES
        result = check_known_bad(load_request(args.input, defaults=CLOSURE_INPUT_FILES), write_catalog=args.write_catalog)
    except (OSError, ValueError, ValidationError) as exc:
        dump_json(validation_result(status='blocked', errors=[str(exc)]))
        return 2
    if result['status'] == 'baseline_not_passed':
        dump_json(result)
        return 2
    if args.json:
        dump_json(result)
    else:
        for row in result['variants']:
            detail = row.get('code') or row.get('error', '')
            print(f"{row['name']}: caught {row['step']} {detail}" if row['caught']
                  else f"{row['name']}: uncaught")
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())


__all__ = ['check_known_bad', 'text_variants']
