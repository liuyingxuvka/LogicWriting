#!/usr/bin/env python3
"""Draw the plan's argument as a Mermaid picture computed from the checked plan; never write.

Boxes are the planned units of reader-brief.json. A solid arrow means the later unit builds on the earlier one
(the earlier unit's downstream_unit_ids); a dotted arrow means it only comes next in reading order. An arrow
between neighbours is labelled with the later unit's relation_to_previous. Problems the tool computes are red:
a unit nothing later builds on, a unit that builds on nothing earlier, a conclusion no chain of links reaches,
a live or qualified alternative no unit answers, a researched claim with no supporting anchor or one that shares
no word with what its anchors say, and the audit or review findings on a unit.

The tool chooses the density: every unit while the picture stays at the readable size (12 boxes), the plan's
top-level parts beyond that, and otherwise a list of the parts to draw one at a time. With --focus a unit is
drawn with its neighbours and with the anchors, limitations and alternatives it carries. Whatever is left out is
named under "Not drawn".
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from reader_plan import claim_anchor_gaps, is_researched, validate_evidence_boundaries
from reader_plan_core import _canonical_plan_order
from show_plan import _load_view_input, _records, plan_view

READABLE_BOXES = 12
READABLE_ARROWS = 20
ANSWERED_STATUSES = ('live', 'qualified')
_ARROWS = {'builds_on': '-->', 'order': '-.->', 'answers': '-.->', 'support': '-->', 'limit': '-.->',
           'context': '-.->', 'counter': '--x', 'limits': '-.->'}


def _short(text, size=60):
    text = ' '.join(str(text).split())
    return text if len(text) <= size else text[:size - 3].rstrip() + '...'


def _wrap(text, lines=3, width=56):
    """Break text at spaces into at most `lines` lines; the last line is shortened when the text goes on."""
    words, rows = ' '.join(str(text).split()).split(' '), ['']
    for word in words:
        if rows[-1] and len(rows[-1]) + 1 + len(word) > width:
            if len(rows) == lines:
                rows[-1] = _short(rows[-1] + ' ' + word + ' ...', width)
                break
            rows.append(word)
        else:
            rows[-1] = (rows[-1] + ' ' + word).strip()
    return rows


def _escape(text):
    return text.replace('#', '#35;').replace('"', '#quot;').replace('<', '#lt;').replace('>', '#gt;')


def _lines(*parts):
    return '<br/>'.join(_escape(part) for part in parts if part)


def _plural(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


class _Plan:
    """The plan's tree, reading order and declared links, as the picture and its checks read them."""

    def __init__(self, brief):
        self.brief = brief
        self.plan = brief['composition_plan']
        boundaries = brief['content_boundaries']
        self.units = {row['planned_unit_id']: row for row in self.plan['planned_units']}
        self.order = _canonical_plan_order(self.plan['planned_units'])
        self.children = {}
        for identity in self.order:
            self.children.setdefault(self.units[identity].get('parent_unit_id'), []).append(identity)
        self.roots = list(self.children.get(None, []))
        self.numbers = {}
        for index, root in enumerate(self.roots):
            self._number(root, str(index + 1))
        self.leaves = [identity for identity in self.order if identity not in self.children]
        self.content = {row['content_unit_id']: row for row in boundaries.get('content_units', [])}
        self.anchors = {row['anchor_id']: row for row in boundaries.get('evidence_anchors', [])}
        self.limitations = {row['limitation_id']: row for row in boundaries.get('limitations', [])}
        self.alternatives = list(boundaries.get('alternatives', []))
        links = []
        for identity in self.order:
            for target in self.units[identity].get('downstream_unit_ids', []):
                pair = (self._edge_leaf(identity, -1), self._edge_leaf(target, 0))
                if pair[0] != pair[1]:
                    links.append(pair)
        self.links = list(dict.fromkeys(links))
        self.answered_in = {}
        for alternative in self.alternatives:
            identity = alternative['alternative_id']
            concerned = set(alternative.get('content_unit_ids', []))
            self.answered_in[identity] = [
                unit for unit in self.order
                if any(cu in concerned or identity in self.content.get(cu, {}).get('alternative_ids', [])
                       for cu in self.units[unit].get('content_unit_ids', []))]

    def _number(self, identity, number):
        self.numbers[identity] = number
        for index, child in enumerate(self.children.get(identity, [])):
            self._number(child, f'{number}.{index + 1}')

    def _edge_leaf(self, identity, end):
        """A link from a part leaves at its last unit; a link into a part enters at its first."""
        while identity in self.children:
            identity = self.children[identity][end]
        return identity

    def leaves_under(self, identity):
        if identity not in self.children:
            return [identity]
        return [leaf for child in self.children[identity] for leaf in self.leaves_under(child)]

    def label(self, identity):
        return f"{self.numbers[identity]}. {self.units[identity].get('title', identity)}"

    def claims(self, identity):
        return [self.content[cu]['safe_meaning'] for cu in self.units[identity].get('content_unit_ids', [])
                if cu in self.content]

    def first_unit_with(self, content_unit_id):
        return next((unit for unit in self.order if content_unit_id in self.units[unit].get('content_unit_ids', [])), None)


def _problem(code, unit, message, alternative=None):
    return dict(code=code, unit=unit, alternative=alternative, message=message)


def _graph_problems(plan):
    if not plan.links or not plan.leaves:
        return []
    start = plan.leaves[0]
    conclusions = [identity for identity in plan.order if plan.units[identity].get('unit_kind') == 'conclusion']
    end = plan._edge_leaf(conclusions[-1], -1) if conclusions else plan.leaves[-1]
    outgoing = {source for source, _ in plan.links}
    incoming = {target for _, target in plan.links}
    problems = []
    for leaf in plan.leaves:
        if leaf != end and leaf not in outgoing:
            problems.append(_problem('leads_nowhere:' + leaf, leaf,
                                     f'nothing later builds on {plan.label(leaf)}, and it is not the conclusion'))
        if leaf != start and leaf not in incoming:
            problems.append(_problem('builds_on_nothing:' + leaf, leaf,
                                     f'no earlier unit lists {plan.label(leaf)} in its downstream_unit_ids'))
    reached, frontier = {start}, [start]
    while frontier:
        current = frontier.pop()
        for source, target in plan.links:
            if source == current and target not in reached:
                reached.add(target)
                frontier.append(target)
    if end not in reached:
        problems.append(_problem('conclusion_not_reached:' + end, end,
                                 f'no chain of downstream_unit_ids leads from {plan.label(start)} to {plan.label(end)}'))
    return problems


def _support_problems(plan):
    problems = []
    for row in validate_evidence_boundaries(plan.brief):
        content_unit = row['defect_id'].split(':', 1)[1]
        problems.append(_problem(row['defect_id'], plan.first_unit_with(content_unit),
                                 f"no anchor supports this claim: {row['reason']}"))
    for row in claim_anchor_gaps(plan.brief):
        content_unit = row['defect_id'].split(':', 1)[1]
        problems.append(_problem(row['defect_id'], plan.first_unit_with(content_unit), row['reason']))
    return problems


def _alternative_problems(plan):
    return [_problem('alternative_unanswered:' + row['alternative_id'], None,
                     f"no planned unit answers this {row['status']} alternative: {_short(row['safe_meaning'], 80)}",
                     alternative=row['alternative_id'])
            for row in plan.alternatives
            if row.get('status') in ANSWERED_STATUSES and not plan.answered_in[row['alternative_id']]]


def _state_problems(plan, state, document):
    problems = [_problem(f"audit:{row['code']}", None, row.get('message', '')) for row in document]
    if not state:
        return problems
    for identity in plan.order:
        for row in state.get(identity, {}).get('findings', []):
            problems.append(_problem(f"{row.get('source', 'check')}:{row['code']}", identity, row.get('message', '')))
    if any(row.get('bound') for row in state.values()):
        problems += [_problem('not_in_text:' + leaf, leaf, 'no passage of the current text is bound to this unit')
                     for leaf in plan.leaves
                     if plan.units[leaf].get('content_unit_ids') and not state.get(leaf, {}).get('bound')]
    return problems


def _choose(plan, focus):
    """Which units become boxes, which leaf each box stands for, and what the extras are."""
    if focus is not None:
        if focus not in plan.units:
            raise ValueError(f'unknown planned unit {focus}; the plan has: {", ".join(plan.order)}')
        centre = plan.leaves_under(focus)
        if len(centre) > READABLE_BOXES:
            return 'too_large', [], {}, centre, plan.children[focus]
        near = set()
        for leaf in centre:
            index = plan.leaves.index(leaf)
            near.update(plan.leaves[max(index - 1, 0):index + 2])
            near.update(source for source, target in plan.links if target == leaf)
            near.update(target for source, target in plan.links if source == leaf)
        drawn = list(centre)
        for leaf in plan.leaves:
            if leaf in near and leaf not in drawn and len(drawn) < READABLE_BOXES:
                drawn.append(leaf)
        drawn = [leaf for leaf in plan.leaves if leaf in drawn]
        return 'focus', drawn, {leaf: leaf for leaf in drawn}, centre, []
    if len(plan.leaves) <= READABLE_BOXES:
        return 'units', list(plan.leaves), {leaf: leaf for leaf in plan.leaves}, [], []
    if len(plan.roots) <= READABLE_BOXES:
        return 'parts', list(plan.roots), {leaf: root for root in plan.roots for leaf in plan.leaves_under(root)}, [], []
    return 'too_large', [], {}, [], plan.roots


def draw(brief, state=None, *, focus=None, summary='', document=()):
    """The picture as data: Mermaid text, what it draws, the computed problems and what it leaves out.

    `state` maps planned unit ids to show_plan's readback rows (bound text and findings); `document` holds the
    audit findings on the whole piece.
    """
    plan = _Plan(brief)
    problems = (_graph_problems(plan) + _support_problems(plan) + _alternative_problems(plan)
                + _state_problems(plan, state, document))
    level, drawn, represent, centre, views = _choose(plan, focus)
    title = f"Argument of {plan.plan.get('plan_id', 'the plan')}" + (f" around {focus} ({plan.label(focus)})" if focus else '')
    picture = dict(title=title, question=plan.plan.get('central_question', ''), summary=summary, level=level,
                   mermaid='', boxes=0, arrows=0, drawn_units=drawn, drawn_anchors=[], drawn_limitations=[],
                   drawn_alternatives=[], edges=[], problems=problems, not_drawn=[], not_computed=[], views=[])
    if not plan.links:
        picture['not_computed'].append('whether the argument reaches its conclusion: the plan declares no '
                                       'downstream_unit_ids, so the arrows follow the reading order only')
    if not is_researched(brief):
        picture['not_computed'].append(f"claim support: a {brief['final_owner']} piece without research_folder "
                                       'is not checked against evidence anchors')
    if state is None:
        picture['not_computed'].append('text bindings and audit or review findings: not read')
    if level == 'too_large':
        picture['views'] = [f"--focus {identity} ({plan.units[identity].get('title', identity)}, "
                            f"{_plural(len(plan.leaves_under(identity)), 'unit')})" for identity in views]
        for row in problems:
            row['drawn'] = False
        return picture

    boxes = len(drawn)
    centre_set = set(centre)
    if level == 'focus':
        alternatives = [row['alternative_id'] for row in plan.alternatives
                        if set(plan.answered_in[row['alternative_id']]) & centre_set]
        anchors = list(dict.fromkeys(anchor for unit in centre for cu in plan.units[unit].get('content_unit_ids', [])
                                     for anchor in plan.content.get(cu, {}).get('evidence_anchor_ids', [])
                                     if anchor in plan.anchors))
        limitations = list(dict.fromkeys(limitation for unit in centre
                                         for limitation in plan.units[unit].get('limitation_ids', [])
                                         if limitation in plan.limitations))
    else:
        alternatives = [row['alternative_id'] for row in plan.alternatives]
        anchors, limitations = [], []
    for key, candidates in (('drawn_alternatives', alternatives), ('drawn_anchors', anchors),
                            ('drawn_limitations', limitations)):
        for identity in candidates:
            if boxes < READABLE_BOXES:
                picture[key].append(identity)
                boxes += 1

    edges = []
    if level == 'parts':
        sequence = list(drawn)
    else:
        sequence = [leaf for leaf in plan.leaves if leaf in represent]
    builds = list(dict.fromkeys((represent[source], represent[target]) for source, target in plan.links
                                if source in represent and target in represent
                                and represent[source] != represent[target]))
    neighbours = [(earlier, later) for earlier, later in zip(sequence, sequence[1:])
                  if level != 'focus' or plan.leaves.index(later) == plan.leaves.index(earlier) + 1]
    for earlier, later in neighbours:
        edges.append(dict(source=earlier, target=later, kind='builds_on' if (earlier, later) in builds else 'order',
                          label=plan.units[later].get('relation_to_previous', '')))
    edges += [dict(source=source, target=target, kind='builds_on', label='')
              for source, target in builds if (source, target) not in neighbours]
    for identity in picture['drawn_alternatives']:
        for unit in dict.fromkeys(represent[leaf] for answer in plan.answered_in[identity]
                                  for leaf in plan.leaves_under(answer) if leaf in represent):
            edges.append(dict(source=identity, target=unit, kind='answers', label='answered in'))
    drawn_anchors = set(picture['drawn_anchors'])
    for unit in centre:
        content_units = plan.units[unit].get('content_unit_ids', [])
        for cu in content_units:
            for anchor in plan.content.get(cu, {}).get('evidence_anchor_ids', []):
                if anchor in drawn_anchors:
                    relation = plan.anchors[anchor].get('relation', '')
                    edges.append(dict(source=anchor, target=unit, kind=relation,
                                      label=relation + (f' · {cu}' if len(content_units) > 1 else '')))
        for limitation in plan.units[unit].get('limitation_ids', []):
            if limitation in picture['drawn_limitations']:
                edges.append(dict(source=limitation, target=unit, kind='limits', label='limits'))
    picture['edges'] = edges

    names = {}
    for prefix, identities in (('n', drawn), ('x', picture['drawn_alternatives']), ('a', picture['drawn_anchors']),
                               ('l', picture['drawn_limitations'])):
        for index, identity in enumerate(identities):
            names[(prefix, identity)] = f'{prefix}{index}'
    node = {identity: names[('n', identity)] for identity in drawn}
    node.update({identity: names[('x', identity)] for identity in picture['drawn_alternatives']})
    node.update({identity: names[('a', identity)] for identity in picture['drawn_anchors']})
    node.update({identity: names[('l', identity)] for identity in picture['drawn_limitations']})

    def unit_box(identity):
        if level == 'parts' and identity in plan.children:
            return f'{node[identity]}["{_lines(plan.label(identity), _plural(len(plan.leaves_under(identity)), "unit"))}"]'
        claims = plan.claims(identity)
        if identity in centre_set:
            text = _lines(plan.label(identity), *(row for claim in claims for row in _wrap(claim)))
        else:
            more = f' (+{len(claims) - 1} more)' if len(claims) > 1 else ''
            text = _lines(plan.label(identity), _short(claims[0]) + more if claims else '')
        return f'{node[identity]}["{text}"]'

    lines = ['flowchart TD',
             f"  %% argument flow of {plan.plan.get('plan_id', 'the plan')}"
             f"{' around ' + focus if focus else ''}, computed from reader-brief.json: planned units, "
             'downstream_unit_ids, relation_to_previous, content units, anchors, limitations, alternatives']
    group_names = {}

    def emit(parent, indent):
        for child in plan.children.get(parent, []):
            if child in drawn:
                lines.append(indent + unit_box(child))
            elif child in plan.children and any(leaf in drawn for leaf in plan.leaves_under(child)):
                group_names[child] = f'g{len(group_names)}'
                lines.append(f'{indent}subgraph {group_names[child]}["{_lines(plan.label(child))}"]')
                emit(child, indent + '  ')
                lines.append(indent + 'end')
    if level == 'parts':
        lines += ['  ' + unit_box(identity) for identity in drawn]
    else:
        emit(None, '  ')
    for identity in picture['drawn_alternatives']:
        row = next(row for row in plan.alternatives if row['alternative_id'] == identity)
        lines.append(f"  {node[identity]}{{{{\"{_lines(identity + ' · ' + row['status'], _short(row['safe_meaning']))}\"}}}}")
    for identity in picture['drawn_anchors']:
        row = plan.anchors[identity]
        lines.append(f"  {node[identity]}[/\"{_lines(identity + ' · ' + row.get('relation', ''), *_wrap(row.get('observed_summary', ''), 2))}\"/]")
    for identity in picture['drawn_limitations']:
        lines.append(f"  {node[identity]}>\"{_lines(identity, *_wrap(plan.limitations[identity].get('safe_meaning', ''), 2))}\"]")
    for row in edges:
        arrow = _ARROWS.get(row['kind'], '-->')
        label = f'|"{_escape(row["label"])}"|' if row['label'] else ''
        lines.append(f"  {node[row['source']]} {arrow}{label} {node[row['target']]}")

    not_drawn, counts = picture['not_drawn'], []
    if level == 'parts':
        not_drawn.append(f'{len(plan.leaves)} units folded into their {len(plan.roots)} parts; '
                         'draw one part with --focus PART')
        counts.append(f'{len(plan.leaves)} units folded')
    else:
        hidden = [identity for identity in plan.leaves if identity not in represent]
        if hidden:
            not_drawn.append('units: ' + ', '.join(f'{identity} ({plan.label(identity)})' for identity in hidden))
            counts.append(_plural(len(hidden), 'unit'))
    if level == 'focus':
        cited = {}
        for unit in plan.order:
            for cu in plan.units[unit].get('content_unit_ids', []):
                for anchor in plan.content.get(cu, {}).get('evidence_anchor_ids', []):
                    cited.setdefault(anchor, unit)
        left = [identity for identity in plan.anchors if identity not in drawn_anchors]
        if left:
            not_drawn.append('anchors: ' + ', '.join(f"{identity} ({cited.get(identity, 'cited by no unit')})"
                                                     for identity in left))
            counts.append(_plural(len(left), 'anchor'))
        placed = {}
        for unit in plan.order:
            for limitation in plan.units[unit].get('limitation_ids', []):
                placed.setdefault(limitation, unit)
        left = [identity for identity in plan.limitations if identity not in picture['drawn_limitations']]
        if left:
            not_drawn.append('limitations: ' + ', '.join(f"{identity} ({placed.get(identity, 'placed in no unit')})"
                                                         for identity in left))
            counts.append(_plural(len(left), 'limitation'))
    else:
        if plan.anchors:
            not_drawn.append(f"{_plural(len(plan.anchors), 'evidence anchor')} (draw a unit's anchors with --focus UNIT)")
            counts.append(_plural(len(plan.anchors), 'anchor'))
        if plan.limitations:
            not_drawn.append(f"{_plural(len(plan.limitations), 'limitation')} (draw a unit's limitations with --focus UNIT)")
            counts.append(_plural(len(plan.limitations), 'limitation'))
    left = [row['alternative_id'] for row in plan.alternatives if row['alternative_id'] not in picture['drawn_alternatives']]
    if left:
        not_drawn.append('alternatives: ' + ', '.join(
            f"{identity} (answered in {', '.join(plan.answered_in[identity]) or 'no unit'})" for identity in left))
        counts.append(_plural(len(left), 'alternative'))
    placed_content = {cu for unit in plan.order for cu in plan.units[unit].get('content_unit_ids', [])}
    kept_out = [row for row in plan.plan.get('content_dispositions', []) if row.get('content_unit_id') not in placed_content]
    if kept_out:
        not_drawn.append('content kept out of the text: ' + ', '.join(
            f"{row['content_unit_id']} ({row.get('disposition', 'no disposition')})" for row in kept_out))
        counts.append(_plural(len(kept_out), 'content unit') + ' kept out')
    if counts:
        lines.append(f'  n_omitted["{_escape("not drawn: " + ", ".join(counts))}"]')
        lines += ['  classDef omitted stroke-dasharray: 4 3,fill:none', '  class n_omitted omitted']
    if focus is not None:
        centre_nodes = [node[identity] for identity in centre if identity in node]
        lines += ['  classDef focus stroke-width:3px', f"  class {','.join(centre_nodes)} focus"]
    red = []
    for row in problems:
        if row['alternative']:
            target = node.get(row['alternative'])
        elif row['unit']:
            target = node.get(represent.get(row['unit']) or represent.get(plan._edge_leaf(row['unit'], 0)))
        else:
            target = None
        row['drawn'] = target is not None
        if target and target not in red:
            red.append(target)
    if red:
        lines += ['  classDef problem fill:#f8d7da,stroke:#b02a37', f"  class {','.join(red)} problem"]
    picture.update(mermaid='\n'.join(lines), boxes=boxes, arrows=len(edges))
    return picture


def render(picture):
    """The picture as Markdown: title, question, chain state, the Mermaid block and the lists around it."""
    lines = [f"**{picture['title']}**", '']
    if picture['question']:
        lines += [f"Q: {picture['question']}", '']
    if picture['summary']:
        lines += [picture['summary'], '']
    if picture['level'] == 'too_large':
        lines += [f'Too large to read at once (readable size {READABLE_BOXES} boxes). Draw one part:', '']
        lines += [f'- {row}' for row in picture['views']]
    else:
        lines += ['```mermaid', picture['mermaid'], '```', '',
                  f"Drawn: {picture['boxes']} {'box' if picture['boxes'] == 1 else 'boxes'} and "
                  f"{_plural(picture['arrows'], 'arrow')} (readable size {READABLE_BOXES} "
                  f'boxes, {READABLE_ARROWS} arrows), computed from reader-brief.json.',
                  'Solid arrow: the later unit builds on the earlier one (downstream_unit_ids); dotted: it only comes '
                  'next in reading order; the label is the later unit\'s relation_to_previous. Anchors point at the '
                  'unit that cites them (dotted for limit or context, crossed for counter). Red: a problem below.']
    lines += ['', '**Problems**', '']
    lines += [f"- {row['code']} ({row['message']})"
              + ('' if row.get('drawn') else ' [not drawn]' if row['unit'] or row['alternative'] else ' [the whole piece]')
              for row in picture['problems']] or ['- none found']
    if picture['not_drawn']:
        lines += ['', '**Not drawn**', ''] + [f'- {row}' for row in picture['not_drawn']]
    if picture['not_computed']:
        lines += ['', '**Not computed**', ''] + [f'- {row}' for row in picture['not_computed']]
    return '\n'.join(lines)


def picture_for(path, *, focus=None):
    """Read a chain folder's reader-brief.json (or any chain file) with its bindings and results, and draw it."""
    path = Path(path)
    if path.is_dir():
        source = path / 'reader-brief.json'
        if not source.is_file():
            raise ValueError(f'no reader-brief.json in {path}; build it with python scripts/run_chain.py {path} --until brief')
    else:
        source = path
    request = _load_view_input(source)
    view = plan_view(request, input_path=source)
    brief = _records(request, source)[0]
    state = {row['planned_unit_id']: row for row in view['planned_units']}
    return draw(brief, state, focus=focus, summary=view['summary'], document=view['document'])


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0])
    parser.add_argument('path', help='a chain folder (its reader-brief.json is read) or any chain file')
    parser.add_argument('--focus', help='a planned unit: draw it with its neighbours and what it rests on')
    parser.add_argument('--json', action='store_true', help='print the picture as data')
    args = parser.parse_args()
    try:
        picture = picture_for(args.path, focus=args.focus)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f'show_argument: {type(exc).__name__}: {exc}')
        return 2
    print(json.dumps(picture, ensure_ascii=False, indent=2) if args.json else render(picture))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
