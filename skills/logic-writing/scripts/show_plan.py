#!/usr/bin/env python3
"""Print the supplied plan beside its declared text bindings; no validation or writes."""
import argparse
import json
import re
from _common import load_request


def plan_view(request):
    brief, amap, shared = (request[key] for key in ('reader_brief', 'artifact_map', 'shared_writing'))
    plan = brief['composition_plan']
    units = {u['artifact_unit_id']: u for u in amap['units']}
    content = {c['content_unit_id']: c['safe_meaning'] for c in brief['content_boundaries']['content_units']}
    limitations = {l['limitation_id']: l['safe_meaning'] for l in brief['content_boundaries']['limitations']}
    result = dict(central_question=plan['central_question'], central_throughline=plan['central_throughline'], planned_units=[])
    for unit in sorted(plan['planned_units'], key=lambda u: u['order']):
        ids = list(dict.fromkeys(i for b in shared['unit_bindings'] if b['planned_unit_id'] == unit['planned_unit_id']
                                for i in b['artifact_unit_ids']))
        texts = [re.split(r'(?<=[.!?。！？])\s+', units[i]['text'], maxsplit=1)[0][:110] for i in ids if i in units]
        result['planned_units'].append(dict(order=unit['order'], planned_unit_id=unit['planned_unit_id'], title=unit['title'],
            bound_unit_ids=ids, reader_job=unit['reader_job'], incoming_reader_state=unit['incoming_reader_state'],
            outgoing_reader_state=unit['outgoing_reader_state'], content=[content.get(i, i) for i in unit['content_unit_ids']],
            limitations=[limitations.get(i, i) for i in unit['limitation_ids']], text=texts))
    return result


def render_plan(view):
    lines = [f"Q: {view['central_question']}", f"Throughline: {view['central_throughline']}"]
    for unit in view['planned_units']:
        where = ', '.join(unit['bound_unit_ids']) or 'UNBOUND'
        lines += ['', f"{unit['order']}. {unit['title']} [{where}]", f"   job: {unit['reader_job']}",
                  f"   reader: {unit['incoming_reader_state']} -> {unit['outgoing_reader_state']}"]
        lines += ['   says: ' + text for text in unit['content']]
        lines += ['   limit: ' + text for text in unit['limitations']]
        lines += ['   text: ' + text for text in unit['text']]
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    view = plan_view(load_request(args.input))
    print(json.dumps(view, ensure_ascii=False, indent=2) if args.json else render_plan(view))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
