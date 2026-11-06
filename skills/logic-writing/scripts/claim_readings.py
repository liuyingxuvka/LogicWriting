"""Compare explicit readings in a plan or artifact with bound saved originals.

Presence is a bounded signal: equal numbers do not establish semantic entailment.
No source capture is grey; an AI-written summary never becomes an original.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from functools import lru_cache
from pathlib import Path

from _common import ValidationError


@lru_cache(maxsize=1)
def _unit_reader():
    if importlib.util.find_spec('physicsguard') is None:
        return None
    from physicsguard.core.units import read_unit
    return read_unit


def read_unit(label):
    reader = _unit_reader()
    return reader(label) if reader is not None else None

MONTHS = {m: i + 1 for i, m in enumerate("January February March April May June July August September October "
                                         "November December".split())}
MONTHS.update({m[:3]: n for m, n in list(MONTHS.items())})
MONTHS["Sept"] = 9
MONTH = "|".join(sorted(MONTHS, key=len, reverse=True))
SMALL = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                    "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}
NUMWORD = re.compile(r"(?i)\b(?:(" + "|".join(TENS) + r")(?:[- ](" + "|".join(list(SMALL)[1:10]) + r"))?|("
                     + "|".join(sorted(SMALL, key=len, reverse=True)) + r"))(?:\s+(hundred|thousand))?\b")
HOURW = "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
DIGITS = re.compile(r"(?<![\w/.:])([+−-]?(?:\d{1,3}(?:[,   ]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?))(?!\d)")
PERCENT = re.compile(r"(?i)\s?%|\s*(?:per\s?cent|percent)\b")
UNIT_WORDS = re.compile(r"(\s*)([A-Za-z°ºµ][^\s]*(?:\s[A-Za-z°ºµ][^\s]*){0,3})")
# Unit-looking symbols the table cannot read: a number written with one of them is refused, not ignored.
UNIT_LIKE = re.compile(r"^(?:[kMGT]?Wh|[kMG]?J|k?cal|mph|psi|ft|lbs?|gal|hp|Btu|BTU|kn|knots?|[kMG]?Hz|[kM]?N|"
                       r"[kM]?V|mA|kA|t)$")
COMPARATOR = re.compile(r"(?i)(a little over|a little under|just over|just under|well over|more than|less than|"
                        r"fewer than|at least|at most|up to|over|above|exceeding|under|below|almost|nearly|about|"
                        r"around|roughly|approximately|some|close to|~)\s*$")
CMP = {"more than": ">", "over": ">", "above": ">", "exceeding": ">", "well over": ">", "a little over": ">~",
       "just over": ">~", "at least": ">=", "less than": "<", "fewer than": "<", "under": "<", "below": "<",
       "a little under": "<~", "just under": "<~", "at most": "<=", "up to": "<=", "almost": "<~", "nearly": "<~",
       "about": "~", "around": "~", "roughly": "~", "approximately": "~", "some": "~", "close to": "~", "~": "~"}
TIME_TAIL = re.compile(r"(?i)\s+(in the morning|in the afternoon|in the evening|at night|tonight)")
TIME_END = r"(?=\s*(?:[,.;:)\[]|$|(?:in|and|at|on|or|but|so|tonight|o'clock|am|pm|a\.m\.|p\.m\.)\b))"
TIMES = [
    ("clock", re.compile(r"(?<![\w.:])([01]?\d|2[0-3]):([0-5]\d)(?![\d:])(?:\s*(am|pm|a\.m\.|p\.m\.))?")),
    ("ampm", re.compile(r"(?i)(?<![\w.:])(1[0-2]|0?[1-9])(?:[.:]([0-5]\d))?\s*(am|pm|a\.m\.|p\.m\.)(?!\w)")),
    ("words", re.compile(r"(?i)\b(quarter|half|twenty[- ]five|twenty|ten|five)\s+(past|to|after)\s+(" + HOURW
                         + r"|\d{1,2})\b" + TIME_END)),
    ("oclock", re.compile(r"(?i)\b(" + HOURW + r"|\d{1,2})\s+o'clock\b")),
    ("noon", re.compile(r"(?i)\b(?:at|by|until|till|from|before|after|around|about)\s+(noon|midday|midnight)\b")),
    ("at", re.compile(r"(?i)\bat\s+(" + HOURW + r")\b(?=\s*(?:[,.;]|$|in the (?:morning|afternoon|evening)|at night|"
                      r"tonight))")),
]
DATES = [
    ("dmy", re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + MONTH + r")\b\.?(?:,?\s+(\d{4}))?")),
    ("mdy", re.compile(r"\b(" + MONTH + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s+(\d{4}))?")),
    ("my", re.compile(r"\b(" + MONTH + r")\s+(\d{4})\b")),
    ("iso", re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")),
]
SENTENCE = re.compile(r"(?<=[.!?])[ ]+(?=[A-Z(\[\"“])")
CLAUSE = re.compile(r",\s|;\s|:\s|\s\(|\)\s|\s(?:and|but|while|whereas|after|before|than|compared with|up from|"
                    r"down from|from|to|versus|vs\.?)\s")
UNDERLINE = re.compile(r"^([=\-~^*#\"+])\1{3,}\s*$")
ABSENCE = re.compile(r"(?i)\b(?:does|do|did|will|can)\s?(?:not|n't)\s+(?:say|state|show|give|report|mention|cover|"
                     r"list|include|tell|cite|specify)\b|\bsays nothing\b|\bnothing (?:about|on)\b|"
                     r"\b(?:gives|has|reports|lists) no\b")
STOP = set("the a an of at to in on from and for by with is was are were it its this that as or be has have".split())


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def norm_space(text):
    """Collapse runs of ordinary whitespace; thin and no-break spaces inside numbers stay."""
    return re.sub(r"[ \t\r\n\f\v]+", " ", text).strip()


def sentences(text):
    return [s for s in SENTENCE.split(norm_space(text)) if s]


def number_value(raw):
    digits = re.sub(r"[,   ]", "", raw).replace('−', '-')
    decimals = len(digits.split(".")[1]) if "." in digits else 0
    zeros = 0 if decimals else len(digits) - len(digits.rstrip("0"))
    return float(digits), decimals, zeros


def word_value(match):
    tens, unit, small, mult = match.groups()
    value = (TENS[tens.lower()] + (SMALL[unit.lower()] if unit else 0)) if tens else SMALL[small.lower()]
    return value * ({"hundred": 100, "thousand": 1000}[mult.lower()] if mult else 1)


def unit_after(text):
    """Read a following unit through PhysicsGuard's only unit vocabulary."""
    match = PERCENT.match(text)
    if match:
        return "%", match.end(), "ok", read_unit("%")
    match = UNIT_WORDS.match(text)
    if not match:
        return None
    lead, parts = match.group(1), match.group(2).split(" ")
    if len(lead) > 1:
        return None
    if _unit_reader() is None:
        candidate = parts[0].rstrip('.,;:)]')
        return candidate, len(lead) + len(candidate), 'unavailable', None
    for size in range(len(parts), 0, -1):
        candidate = " ".join(parts[:size]).rstrip(".,;:)]")
        unit = read_unit(candidate)
        if unit is not None:
            return candidate, len(lead) + len(candidate), "ok", unit
    first = parts[0].rstrip(".,;:)]")
    if UNIT_LIKE.fullmatch(first.split("/")[0]):
        return first, len(lead) + len(first), "refused", None
    return None


def comparator(text, start):
    """('>', 'more than') for the comparator written just before a number, or (None, '')."""
    m = COMPARATOR.search(text[max(0, start - 20):start])
    return (CMP[m.group(1).lower()], m.group(1)) if m else (None, "")


def clock(hour, minute, mark=None, tail=None):
    """(minutes since midnight, ambiguous) for a clock time; ambiguous when am/pm is neither written nor implied."""
    mark = (mark or "").lower().replace(".", "")
    tail = (tail or "").lower()
    if mark == "pm" or tail in ("in the afternoon", "in the evening", "at night", "tonight"):
        hour = hour % 12 + 12
        return hour * 60 + minute, False
    if mark == "am" or tail == "in the morning":
        return (hour % 12) * 60 + minute, False
    return hour * 60 + minute, None


def readings(text):
    """Readings in text; earlier kinds win, each character is read once."""
    taken, found = [], []

    def free(a, b):
        return not any(a < y and x < b for x, y in taken)

    def add(row):
        taken.append((row["start"], row["end"]))
        row["raw"] = text[row["start"]:row["end"]].strip()
        found.append(row)

    for m in re.finditer(r"(?i)\bpep\W{0,4}(\d+)", text):
        add(dict(kind="id", key=f"PEP {int(m.group(1))}", start=m.start(), end=m.end()))
    for form, pattern in DATES:
        for m in pattern.finditer(text):
            if not free(*m.span()):
                continue
            g = m.groups()
            if form == "dmy":
                key = (int(g[2]) if g[2] else None, MONTHS[g[1]], int(g[0]))
            elif form == "mdy":
                key = (int(g[2]) if g[2] else None, MONTHS[g[0]], int(g[1]))
            elif form == "my":
                key = (int(g[1]), MONTHS[g[0]], None)
            else:
                key = (int(g[0]), int(g[1]), int(g[2]))
            if key[2] is not None and not 1 <= key[2] <= 31:
                continue
            add(dict(kind="date", key=key, start=m.start(), end=m.end()))
    for form, pattern in TIMES:
        for m in pattern.finditer(text):
            if not free(*m.span()):
                continue
            tail = TIME_TAIL.match(text, m.end())
            end = tail.end() if tail else m.end()
            tail = tail.group(1) if tail else None
            g = m.groups()
            if form == "clock":
                minutes, amb = clock(int(g[0]), int(g[1]), g[2], tail)
                if amb is None:  # 24-hour form: explicit with a leading zero or an hour above 12
                    amb = not (g[0].startswith("0") or int(g[0]) > 12)
            elif form == "ampm":
                minutes, amb = clock(int(g[0]), int(g[1] or 0), g[2], tail)
            elif form == "words":
                part = {"quarter": 15, "half": 30, "ten": 10, "five": 5, "twenty": 20, "twenty-five": 25, "twenty five": 25}[g[0].lower()]
                hour = SMALL[g[2].lower()] if g[2].lower() in SMALL else int(g[2])
                if g[1].lower() == "to":
                    hour, part = (hour - 1) or 12, 60 - part
                minutes, amb = clock(hour, part, None, tail)
            elif form in ("oclock", "at"):
                minutes, amb = clock(SMALL[g[0].lower()] if g[0].lower() in SMALL else int(g[0]), 0, None, tail)
            else:
                minutes, amb = (0 if g[0].lower() == "midnight" else 720), False
            if amb is None:  # a word time with no am/pm and no part of the day: either half of the day
                amb = True
            add(dict(kind="time", minutes=minutes % 1440, amb=bool(amb), start=m.start(), end=end))
    for m in re.finditer(r"(?<![\w./])v?(\d+(?:\.\d+){2,})(?![\w.]*\d)", text):
        if free(*m.span()):
            add(dict(kind="version", key=m.group(1), start=m.start(), end=m.end()))
    numbers = []
    for m in list(DIGITS.finditer(text)) + list(NUMWORD.finditer(text)):
        if not free(*m.span()) or any(m.start() < n["end"] and n["start"] < m.end() for n in numbers):
            continue
        if m.re is DIGITS:
            value, decimals, zeros = number_value(m.group(1))
        else:
            value, decimals, zeros = float(word_value(m)), 0, 0
        unit = unit_after(text[m.end():])
        if m.re is NUMWORD and unit is None:
            continue  # a number word is read only before a unit ("thirty-five minutes"), never alone ("one")
        row = dict(start=m.start(), end=m.end() + (unit[1] if unit else 0), value=value,
                   half=0.5 * 10 ** -decimals, hedged=0.5 * 10 ** (zeros if not decimals else -decimals),
                   cmp=comparator(text, m.start())[0], said=comparator(text, m.start())[1])
        if unit is None:
            raw = m.group(0)
            version = (re.fullmatch(r"\d\.\d{1,2}", raw) and not row["cmp"]
                       and re.search(r"(?i)\b(?:python|cpython|version)\s+$", text[:m.start()]))
            row.update(kind="version" if version else "number",
                       key=raw, unit=None)
        elif unit[2] in ("refused", "unavailable"):
            row.update(kind=unit[2], unit=unit[0])
        elif unit[0] == "%":
            row.update(kind="percent", unit="%", si=value, dim="%")
        else:
            u = unit[3]
            row.update(kind="quantity", unit=unit[0], si=value * u.factor + u.offset, dim=u.exponents,
                       half=row["half"] * u.factor, hedged=row["hedged"] * u.factor)
        numbers.append(row)
    numbers.sort(key=lambda r: r["start"])
    merged, skip = [], set()
    for i, (a, b) in enumerate(zip(numbers, numbers[1:])):
        if i in skip or b["kind"] not in ("percent", "quantity") or a["kind"] not in ("number", "version", b["kind"]):
            continue
        if a["kind"] == b["kind"] and a["unit"] != b["unit"]:
            continue
        between = text[a["end"]:b["start"]]
        before = text[max(0, a["start"] - 10):a["start"]]
        dash = re.fullmatch(r"\s*[-–—]\s*", between)
        to = re.fullmatch(r"\s+to\s+", between) and not re.search(r"(?i)\bfrom\s+$", before)
        between_and = re.fullmatch(r"\s+and\s+", between) and re.search(r"(?i)\bbetween\s+$", before)
        if not (dash or to or between_and):
            continue
        factor = 1.0 if b["kind"] == "percent" else read_unit(b["unit"])
        lo = a["value"] if b["kind"] == "percent" else a["value"] * factor.factor + factor.offset
        if a["kind"] == b["kind"]:
            lo = a["si"]
        start = a["start"] - (len(before) - len(re.sub(r"(?i)between\s+$", "", before)) if between_and else 0)
        merged.append(dict(kind="range", unit=b["unit"], dim=b["dim"], lo=lo, hi=b["si"],
                           half=max(a["half"] * (1 if b["kind"] == "percent" else factor.factor), b["half"]),
                           cmp=None, start=start, end=b["end"]))
        skip |= {i, i + 1}
    for i, row in enumerate(numbers):
        if i not in skip:
            add(row)
    for row in merged:
        add(row)
    return sorted(found, key=lambda r: r["start"])


def shown(r):
    """A reading as the screen prints a sensor value."""
    if r["kind"] == "time":
        return f"{r['minutes'] // 60:02d}:{r['minutes'] % 60:02d}"
    if r["kind"] == "date":
        y, m, d = r["key"]
        return f"{y or '?'}-{m:02d}" + (f"-{d:02d}" if d else "")
    return r["raw"]


# ---------------------------------------------------------------- comparison

def compatible(mine, other):
    k1, k2 = mine["kind"], other["kind"]
    if k1 in ("quantity", "percent", "range"):
        return k2 == k1 and other.get("dim") == mine.get("dim")
    if k1 in ("number", "version"):
        return k2 in ("number", "version")
    return k1 == k2


def agrees(mine, other):
    """Does the sensor reading `other` hold the value the text reading `mine` states (comparator aside)?"""
    k = mine["kind"]
    if k == "range":
        return abs(mine["lo"] - other["lo"]) <= mine["half"] + 1e-9 and abs(mine["hi"] - other["hi"]) <= mine["half"] + 1e-9
    if k in ("quantity", "percent"):
        return within(mine, other["si"])
    if k in ("number", "version"):
        if mine["kind"] == "version" or other["kind"] == "version":
            return mine["key"] == other["key"]
        return within(mine, other["value"])
    if k == "date":
        (y1, m1, d1), (y2, m2, d2) = mine["key"], other["key"]
        return m1 == m2 and (d1 == d2 or d1 is None or d2 is None) and (y1 == y2 or y1 is None or y2 is None)
    if k == "time":
        a, b = mine["minutes"], other["minutes"]
        return a == b or ((mine["amb"] or other["amb"]) and a % 720 == b % 720)
    if k == "refused":
        return mine["raw"] == other.get("raw")
    return mine["key"] == other["key"]


def within(mine, value):
    x = mine["si"] if "si" in mine else mine["value"]
    tiny = 1e-9 * max(abs(x), abs(value), 1.0)
    c, h = mine["cmp"], mine["hedged"] if mine["cmp"] else mine["half"]
    if c is None:
        return abs(value - x) <= mine["half"] + tiny
    if c == "~":
        return abs(value - x) <= h + tiny
    if c == ">":
        return value > x + tiny
    if c == ">=":
        return value >= x - tiny
    if c == "<":
        return value < x - tiny
    if c == "<=":
        return value <= x + tiny
    if c == ">~":
        return x + tiny < value <= x + 2 * h + tiny
    return x - 2 * h - tiny <= value <= x + tiny  # "<~": almost, nearly, just under


def magnitude(r):
    return next((r[key] for key in ("si", "value", "hi", "minutes") if key in r), 0)


def nearest(mine, others):
    x = magnitude(mine)
    return sorted(others, key=lambda o: abs(magnitude(o) - x))


# ---------------------------------------------------------------- sources

def words(text):
    out = set()
    for w in re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.lower().replace("’", "'")):
        w = re.sub(r"'s$", "", w)
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        if (len(w) > 1 or w.isdigit()) and w not in STOP:
            out.add(w)
    return out


def top(labels, have):
    scores = {label: len(words(label) & have) for label in labels}
    best = max(scores.values(), default=0)
    return [label for label, score in scores.items() if score == best] if best else []


def clause_of(sentence, pos):
    start, end = 0, len(sentence)
    for m in CLAUSE.finditer(sentence):
        if m.end() <= pos:
            start = m.end()
        elif m.start() >= pos:
            end = m.start()
            break
    return sentence[start:end]


def cell_agrees(ctx, sentence, pos):
    """A table cell agrees when its row and its column headers are among those the sentence names."""
    clause = words(clause_of(sentence, pos))
    named = top(ctx["row_labels"], clause) or top(ctx["row_labels"], words(sentence))
    if named and ctx["row"] not in named:
        return False, f"row {ctx['row']}; the sentence names {', '.join(named)}"
    for level, labels in enumerate(ctx["level_labels"]):
        named = top(labels, clause)
        if named and ctx["cols"][level] not in named:
            return False, f"column {ctx['cols'][level]}; the clause names {', '.join(named)}"
    return True, f"row {ctx['row']}, column {' / '.join(c for c in ctx['cols'] if c)}"


DIRECTIONAL = (">", ">=", "<", "<=", ">~", "<~")


def reading_scope(sentence, position, end=None):
    """An explicit nearest scope cue, never a natural-language entailment test."""
    declared = r'assum(?:e|es|ed|ing|ption)|target(?:s)?|expect(?:ed|s)?|forecast(?:s)?|projected|propos(?:e|ed|es)'
    observed = r'measured|observed|recorded|actual(?:ly)?|currently'
    cues = list(re.finditer(r'\b(' + declared + '|' + observed + r')\b', sentence[:position], re.I))
    if cues:
        return 'declared' if re.fullmatch(declared, cues[-1].group(), re.I) else 'observed'
    after = sentence[end if end is not None else position:]
    if re.match(r'\s*(?:(?:is|was|as|a|the)\s+){0,3}(?:target|forecast)\b', after, re.I):
        return 'declared'
    return None


def find(reading, rows, sentence):
    """('G', ctx, row) if a sensor row holds the value, ('cell', ctx, row) if only a table cell in another row or
    column does, else None. Cells must agree with the row and columns the sentence names before they count;
    a comparator ("more than 4%") is checked against the nearest value among those that count."""
    fits, conflicts, scope_conflicts = [], [], []
    wanted_scope = reading_scope(sentence, reading["start"], reading["end"])
    for r, ctx in rows:
        if not compatible(reading, r):
            continue
        if ctx.get("cell"):
            ok, why = cell_agrees(ctx, sentence, reading["start"])
            (fits if ok else conflicts).append((r, dict(ctx, why=why)))
        else:
            source_scope = reading_scope(ctx['sentence'], r['start'], r['end']) if ctx['source'] is not None else None
            if (reading['kind'] in ('number', 'quantity', 'percent', 'range')
                    and source_scope == 'declared' and wanted_scope != 'declared'):
                scope_conflicts.append((r, dict(ctx, why='the source states an assumption, prediction or target; not an observed result')))
            else:
                fits.append((r, ctx))
    x = magnitude(reading)
    pool = sorted(fits, key=lambda t: abs(magnitude(t[0]) - x))[:1] if reading.get("cmp") in DIRECTIONAL else fits
    for r, ctx in pool:
        if agrees(reading, r):
            return "G", ctx, r
    for r, ctx in conflicts:
        if agrees(reading, r):
            return "cell", ctx, r
    for r, ctx in scope_conflicts:
        if agrees(reading, r):
            return ('scope' if wanted_scope == 'observed' else 'scope-unknown'), ctx, r
    return None


def fitting(reading, rows, sentence):
    """The compatible sensor values that count for this sentence (prose, headers, agreeing cells), nearest first."""
    out = [r for r, ctx in rows if compatible(reading, r)
           and (not ctx.get("cell") or cell_agrees(ctx, sentence, reading["start"])[0])]
    return nearest(reading, out)




def passage_readings(text):
    """Read prose and ResearchGuard-owned table cells without losing their labels."""
    from researchguard.source.capture import table_cells
    rows = []
    for cell in table_cells(text):
        context = {key: value for key, value in cell.items() if key != 'text'}
        for reading in readings(cell['text']):
            rows.append((reading, context))
    prose = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('|'))
    for paragraph in re.split(r'\n\s*\n', prose):
        for sentence in sentences(paragraph):
            rows.extend((reading, dict(sentence=sentence)) for reading in readings(sentence))
    return rows


def build_sensors(brief):
    """Only originals bound by the brief or provider rows can serve as sensors."""
    anchors = {row['anchor_id']: row for row in brief['content_boundaries']['evidence_anchors']}
    passages, documents, issues = {}, {}, []
    if 'research_folder' in brief:
        from researchguard.source.capture import capture_passage, load_anchor_capture
        for identity in anchors:
            saved = load_anchor_capture(brief['research_folder'], identity)
            if saved is None or not saved['text']:
                continue
            if saved['colour'] != 'green':
                issues.append(dict(id=identity, colour='red' if saved['colour'] == 'red' else 'grey',
                                   reason=saved['reason'], source_digest=saved['source_digest']))
                continue
            passage = capture_passage(saved['text'], saved['quote'])
            if passage is None:
                issues.append(dict(id=identity, colour='red', reason='saved anchor quote absent from original',
                                   source_digest=saved['source_digest']))
                continue
            raw = passage['raw_text']
            measured = passage_readings(passage['title'] + '\n' + raw)
            # A document's own explicit identifier is metadata, not a numeric
            # measurement that must occur inside the anchor's section.
            for line in saved['text'].splitlines():
                if re.fullmatch(r'(?i)PEP:\s*\d+\s*', line):
                    measured.extend((row, dict(sentence=line)) for row in readings(line))
            passages[identity] = dict(file=Path(saved['path']).name, section=passage['section'],
                                      readings=measured, digest=saved['source_digest'], quote=saved['quote'])
            documents[identity] = saved
    request = [(row, dict(sentence=sentence)) for sentence in sentences(brief['request']) for row in readings(sentence)]
    providers = brief['provider_reports'] if 'provider_reports' in brief else []
    route = brief['route_composition'] if 'route_composition' in brief else {}
    research_folder = brief['research_folder'] if 'research_folder' in brief else None
    pg_rows, provider_issues = provider_sensors(providers, brief['request'], route, research_folder=research_folder)
    bound_rows = {identity for unit in brief['content_boundaries']['content_units'] for identity in unit['model_row_ids']}
    provider_issues = [row for row in provider_issues if not (
        row['colour'] == 'grey' and row['id'].startswith('physicsguard:')
        and 'pg:' + row['id'].removeprefix('physicsguard:') not in bound_rows)]
    return dict(anchors=anchors, passages=passages, documents=documents, issues=issues + provider_issues,
                request=request, pg_rows=pg_rows)


def _digest(value):
    return value.removeprefix('sha256:')


def provider_sensors(reports, request, route_composition=None, *, research_folder=None):
    """Read saved rows; compare bytes, never execute a specialist to repair an old report."""
    rows, issues = {}, []
    for report in reports:
        path = Path(report['path'])
        document = json.loads(path.read_text(encoding='utf-8'))
        source_data = provider_source_data(document)
        provider = report['provider']
        if provider not in ('physicsguard', 'researchguard', 'worldguard'):
            raise ValidationError('unknown provider: ' + provider)
        base = path.parent
        if provider == 'worldguard' and route_composition:
            field = 'world_mesh' if 'world_mesh' in route_composition else 'world_contract'
            if field in route_composition:
                base = Path(route_composition[field]).parent
        elif provider == 'researchguard' and research_folder is not None:
            base = Path(research_folder)
            if base.name == 'research.yaml':
                base = base.parent
        stale = []
        if 'input_digests' in document:
            for item in document['input_digests']:
                original = base / item['path']
                if not original.is_file() or sha(original.read_bytes()) != _digest(item['sha256']):
                    stale.append(item['path'])
        if provider == 'physicsguard':
            originals = list(source_data['sources'].values()) if 'sources' in source_data else (document['input_digests'] if 'input_digests' in document else [])
            if not any(_digest(item['sha256']) == sha(request.encode('utf-8')) for item in originals):
                stale.append('request_identity')
        if stale:
            issues.append(dict(id=provider, colour='red', reason='stale:' + ','.join(stale), source_digest=''))
            continue
        native_rows = source_data['source_readings'] if 'source_readings' in source_data else (document['checked']['source_statuses'] if 'checked' in document and 'source_statuses' in document['checked'] else [])
        for row in native_rows:
            for key in ('id', 'colour', 'reason', 'source_digest'):
                if key not in row:
                    raise ValidationError(f'{provider} source row missing {key}')
            problems = source_row_problems(row, document, base)
            if problems:
                issues.append(dict(row, id=provider + ':' + row['id'], colour='red', reason='stale:' + ','.join(problems)))
                continue
            if row['colour'] != 'green':
                issues.append(dict(row, id=provider + ':' + row['id']))
            if provider == 'physicsguard' and 'value' in row and 'unit' in row:
                rows['pg:' + row['id']] = _physical_row(row, row['colour'] == 'green')
        # Saved prototype reports predate source_readings; provenance is their input bytes plus request identity.
        if provider == 'physicsguard' and 'values' in document:
            for identity, row in document['values'].items():
                rows['pg:' + identity] = _physical_row(row, row['sourced'])
    return rows, issues


def provider_source_data(document):
    """PhysicsGuard keeps source evidence in metadata; other native owners own their layout."""
    if 'metadata' in document and ('source_readings' in document['metadata'] or 'sources' in document['metadata']):
        return document['metadata']
    return document



def source_row_problems(row, document, base):
    """The digest is evidence identity, including a specialist's aggregate of several originals."""
    supplied = row['source_digest']
    multiple = row['source_digests'] if 'source_digests' in row else []
    if not supplied and not multiple:
        return ['source_digest_missing'] if row['colour'] == 'green' else []
    candidates = document['input_digests'] if 'input_digests' in document else []
    source_data = provider_source_data(document)
    if 'sources' in source_data:
        candidates = [*candidates, *source_data['sources'].values()]
    bound = row['sources'] if 'sources' in row else []
    if bound:
        digests = [_digest(item['sha256']) for item in bound]
        canonical = json.dumps(bound, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        if _digest(supplied) not in [sha(canonical), *(digests if len(digests) == 1 else [])]:
            return ['source_digest_mismatch']
        candidates = bound
    else:
        requested = multiple if multiple else [supplied]
        # A digest not tied to any saved original cannot turn a row green.
        for digest in requested:
            if not any(_digest(item['sha256']) == _digest(digest) for item in candidates):
                return ['source_digest_unbound']
        candidates = [item for item in candidates if any(_digest(item['sha256']) == _digest(d) for d in requested)]
    return [item['path'] for item in candidates
            if not (base / item['path']).is_file() or sha((base / item['path']).read_bytes()) != _digest(item['sha256'])]


def _physical_row(row, sourced):
    unit = read_unit(row['unit'])
    if unit is None:
        return dict(row, sourced=False, dim=None, si=None)
    return dict(row, sourced=sourced, dim=unit.exponents, si=row['value'] * unit.factor + unit.offset)


def check_reading(reading, sentence, anchor_ids, row_ids, sensors):
    """Return one colour and the actual original or bound tool row used for comparison."""
    if ABSENCE.search(sentence):
        return 'grey', 'the sentence says the source does not give this; not checked'
    if reading['kind'] == 'unavailable':
        return 'grey', 'unit checking unavailable: install PhysicsGuard >= 0.18.0 to read ' + reading['raw']
    used = [(identity, sensors['passages'][identity]) for identity in anchor_ids if identity in sensors['passages']]
    source_rows = [(row, dict(context, source=passage)) for _, passage in used for row, context in passage['readings']]
    if not any(compatible(reading, row) for row, _ in source_rows):
        source_rows += [(row, dict(context, source=None)) for row, context in sensors['request']]
    bound = [sensors['pg_rows'][identity] for identity in row_ids if identity in sensors['pg_rows']]
    native_roles = [row for row in bound if 'source_entity' in row]
    if native_roles and reading['kind'] in ('range', 'number', 'percent', 'refused'):
        return 'grey', 'PhysicsGuard scalar entity rows do not verify this interval, unitless value or unread unit; role/value agreement was not checked'
    if reading['kind'] == 'refused':
        if any(reading['raw'] == row['raw'] for row, _ in source_rows):
            return 'green', 'unknown unit; identical words occur in the bound original'
        return 'red', f"refused: unit {reading['unit']!r} is not in PhysicsGuard's unit table"
    physical = [row for row in bound if reading['kind'] == 'quantity' and row['dim'] == reading['dim']]
    role_rows = [row for row in physical if 'source_entity' in row]
    if reading['kind'] == 'quantity' and native_roles and not role_rows:
        return 'grey', 'PhysicsGuard entity rows have no compatible quantity; property-dependent conversion and role/value agreement were not checked'
    if role_rows:
        known = {row['source_entity'] for row in sensors['pg_rows'].values() if 'source_entity' in row}
        clause = clause_of(sentence, reading['start'])
        entity = '(?:' + '|'.join(re.escape(name) for name in sorted(known, key=len, reverse=True)) + ')'
        group = entity + r'(?:\s*(?:,|and|&)\s*' + entity + r')+'
        copula = r'\s+(?:are|were|is|was)\s+'
        collective = re.search(
            r'(?<!\w)(?:' + group + copula + r'(?:(?:both|each|all)\s+)?|'
            + r'(?:Both|Each of|All of)\s+' + group + copula + r')'
            + r'(?:(?:at|exactly|about|around)\s+)?$', sentence[:reading['start']], re.I)
        scope = collective.group() if collective else clause
        named = {entity for entity in known if re.search(r'(?<!\w)' + re.escape(entity) + r'(?!\w)', scope, re.I)}
        if re.search(r'\b(?:Each inlet (?:is|was)|(?:Both|All) inlets (?:are|were))\s+(?:at\s+)?$',
                     sentence[:reading['start']], re.I):
            inlets = [row for row in sensors['pg_rows'].values() if 'source_entity' in row
                      and 'input_group' in row and re.fullmatch(r'.+\.inlet_[12]', row['input_group'])]
            groups = {row['input_group'] for row in inlets}
            parents = {group.rsplit('.', 1)[0] for group in groups}
            if len(parents) != 1 or len(groups) != 2:
                return 'grey', 'PhysicsGuard each-inlet statement has no unique complete native inlet pair'
            named = {row['source_entity'] for row in inlets}
            collective = True
        if not named:
            return 'grey', 'PhysicsGuard value is bound, but this sentence does not identify its captured source entity'
        if len(named) > 1 and not collective:
            return 'grey', 'PhysicsGuard value names several source entities without a unique literal role'
        unchecked = []
        for entity in sorted(named):
            candidates = [row for row in role_rows if row['source_entity'] == entity]
            if not candidates:
                if any(row['source_entity'] == entity for row in native_roles):
                    unchecked.append(entity)
                    continue
                return 'red', f'PhysicsGuard role binding names {entity!r}, but the selected result rows belong to another source entity'
            if not any(within(reading, row['si']) for row in candidates):
                return 'red', f'PhysicsGuard {entity}: the claimed value {reading["raw"]} disagrees with this entity result'
        if unchecked:
            return 'grey', 'PhysicsGuard selected entity rows have no compatible quantity for ' + ', '.join(unchecked)
        selected = [row for row in role_rows if row['source_entity'] in named and within(reading, row['si'])]
        return ('green' if all(row['sourced'] for row in selected) else 'grey'), 'PhysicsGuard value and captured source entity agree: ' + ', '.join(sorted(named))
    for row in physical:
        if within(reading, row['si']):
            return ('green' if row['sourced'] else 'grey'), f"PhysicsGuard {row['value']:g} {row['unit']}" + ('' if row['sourced'] else ' rests on AI values')
    got = find(reading, source_rows, sentence)
    if got and got[0] == 'G':
        context, original = got[1], got[2]
        where = 'owner request' if context['source'] is None else context['source']['file'] + ' §' + context['source']['section']
        return 'green', f"{where}: {original['raw']}"
    if physical:
        row = nearest(reading, physical)[0]
        difference = f"x{reading['si'] / row['si']:.3g}" if row['si'] else 'different from zero'
        return 'red', f"PhysicsGuard {row['value']:g} {row['unit']}; claim {reading['raw']} ({difference})"
    if got:
        if got[0] in ('scope', 'scope-unknown'):
            return ('red' if got[0] == 'scope' else 'grey'), got[1]['why']
        return 'red', 'value occurs only in another table ' + got[1]['why']
    if bound and reading['kind'] == 'quantity' and not physical:
        return 'red', 'the bound PhysicsGuard rows have no compatible quantity for ' + reading['raw']
    if used:
        matching = fitting(reading, source_rows, sentence)
        have = ', '.join(dict.fromkeys(shown(row) for row in matching[:4]))
        return 'red', 'not in bound original; it reads ' + (have if have else 'no matching ' + reading['kind'])
    return 'grey', 'no bound original or matching tool row'


NEGATORS = frozenset('not no never none nor neither unless except without only cannot'.split())
SPEECH = r'(?:said|says|told|wrote|writes|added|adds|explained|noted|warned|argued|replied|stated|insisted)'
NAME = r"([A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+)*)"


def speaker_of(text, start, end):
    before, after = text[max(0, start - 160):start], text[end:end + 160]
    patterns = (re.match(rf'\s*,?\s*{SPEECH}\s+(?:(?:the\s+)?[a-z][\w\'’-]*\s+){{0,3}}{NAME}', after),
                re.match(rf'\s*,?\s*{NAME}\s+{SPEECH}\b', after),
                re.search(rf'{NAME}\s+{SPEECH}\s*[:,]?\s*$', before),
                re.search(rf'[Aa]ccording to\s+(?:(?:the\s+)?[a-z][\w\'’-]*\s+){{0,3}}{NAME}', before + ' ' + after))
    return next((match.group(1) for match in patterns if match), None)


def quote_readings(text, anchor_ids, sensors):
    documents = [sensors['documents'][identity] for identity in anchor_ids if identity in sensors['documents']]
    for match in re.finditer(r'“([^”]+)”|"([^"]+)"', text):
        quote = match.group(1) or match.group(2)
        if len(quote.split()) < 3:
            continue
        if not documents:
            yield dict(raw=quote, colour='grey', reason='quote has no bound saved original')
            continue
        from researchguard.source.capture import match_quote
        found = next(((document, result) for document in documents
                      for result in [match_quote(document['text'], quote, word_match=True)] if result), None)
        if found is None:
            yield dict(raw=quote, colour='red', reason='quoted words differ from bound saved original')
            continue
        document, result = found
        omitted = ' '.join(result['omitted_words'])
        changed = [word for word in re.findall(r"[\w]+(?:n't)?", omitted.casefold()) if word in NEGATORS or word.endswith("n't")]
        if changed:
            yield dict(raw=quote, colour='red', reason='ellipsis omits ' + ', '.join(changed) + ': ' + omitted)
            continue
        yield dict(raw=quote, colour='green', reason='quote in ' + Path(document['path']).name)
        speaker = speaker_of(text, match.start(), match.end())
        if speaker:
            original = result['context_text']
            start, end = result['context_start'], result['context_end']
            prior = max([m.end() for m in re.finditer(r'[.!?]["”’]?\s+', original[:start])], default=0)
            following = next((m.start() + end for m in re.finditer(r'[.!?]["”’]?\s+', original[end:])), len(original))
            outside = original[prior:start] + ' ' + original[end:following]
            if not re.search(r'\b[A-Z][a-z]+', outside.strip()[2:]):
                previous = max([m.end() for m in re.finditer(r'[.!?]["”’]?\s+', original[:prior])], default=0)
                outside = original[previous:start] + ' ' + original[end:following]
            found_name = re.search(rf'\b{re.escape(speaker.split()[-1].casefold())}\b', outside.casefold())
            yield dict(raw=speaker, colour='green' if found_name else 'red',
                       reason='speaker named with source quote' if found_name else 'speaker differs from source quote context: ' + outside)


def check_text(text, anchor_ids, row_ids, sensors):
    result = []
    source_digest = reading_source_digest(anchor_ids, row_ids, sensors)
    for sentence in sentences(text):
        for reading in readings(sentence):
            colour, reason = check_reading(reading, sentence, anchor_ids, row_ids, sensors)
            result.append(dict(raw=reading['raw'], colour=colour, reason=reason, source_digest=source_digest))
    result.extend(dict(row, source_digest=source_digest) for row in quote_readings(text, anchor_ids, sensors))
    return result


def reading_source_digest(anchor_ids, row_ids, sensors):
    """Fingerprint the original windows and saved result rows actually made available.

    A digest records the evidence boundary; it does not license an unrelated
    equal number as a semantically correct claim.
    """
    originals = {identity: dict(digest=sensors['passages'][identity]['digest'],
                                quote=sensors['passages'][identity]['quote'] if 'quote' in sensors['passages'][identity] else '')
                 for identity in anchor_ids if identity in sensors['passages'] and 'digest' in sensors['passages'][identity]}
    results = {identity: sensors['pg_rows'][identity] for identity in row_ids if identity in sensors['pg_rows']}
    request = sensors['request']
    if not originals and not results and not request:
        return ''
    canonical = json.dumps(dict(originals=originals, result_rows=results, request=request),
                           sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)
    return 'sha256:' + sha(canonical.encode('utf-8'))


def plan_readings(brief, *, sensors=None):
    sensors = build_sensors(brief) if sensors is None else sensors
    rows = [dict(row, content_unit_id=row['id']) for row in sensors['issues']]
    for unit in brief['content_boundaries']['content_units']:
        rows.extend(dict(row, content_unit_id=unit['content_unit_id']) for row in
                    check_text(unit['safe_meaning'], unit['evidence_anchor_ids'], unit['model_row_ids'], sensors))
    return [dict(row, id=f"{row['content_unit_id']}:reading:{index}") for index, row in enumerate(rows)]


def text_readings(brief, artifact_map, shared_writing, *, sensors=None):
    sensors = build_sensors(brief) if sensors is None else sensors
    content = {row['content_unit_id']: row for row in brief['content_boundaries']['content_units']}
    artifacts = {row['artifact_unit_id']: row for row in artifact_map['units']}
    boundaries = brief['content_boundaries']
    by_source = {}
    for anchor in boundaries['evidence_anchors']:
        by_source.setdefault(anchor['source_id'], []).append(anchor['anchor_id'])
    rows = [dict(row, artifact_unit_id='artifact:document') for row in sensors['issues']]
    for binding in shared_writing['unit_bindings']:
        units = [content[identity] for identity in binding['content_unit_ids']]
        anchors = {identity for unit in units for identity in unit['evidence_anchor_ids']}
        model_rows = {identity for unit in units for identity in unit['model_row_ids']} | set(binding['model_row_ids'] if 'model_row_ids' in binding else [])
        for identity in binding['artifact_unit_ids']:
            text = artifacts[identity]['text']
            for sentence in sentences(text):
                cited = set(anchors)
                named_sources = {duty['source_id'] for duty in boundaries['citation_duties'] if duty['marker'] in sentence}
                if named_sources:
                    cited = {identity for source in named_sources if source in by_source for identity in by_source[source]}
                for duty in boundaries['citation_duties']:
                    sentence = sentence.replace(duty['marker'], ' ')
                scoped = dict(sensors, request=[]) if named_sources else sensors
                rows.extend(dict(row, artifact_unit_id=identity) for row in check_text(sentence, sorted(cited), sorted(model_rows), scoped))
    return [dict(row, id=f"{row['artifact_unit_id']}:reading:{index}") for index, row in enumerate(rows)]


def reading_risks(rows):
    return [dict(defect_id='claim_source_gap:' + row['content_unit_id'], reason=row['reason'])
            for row in rows if row['colour'] == 'grey']


def validate_plan_readings(brief):
    rows = plan_readings(brief)
    for row in rows:
        if row['colour'] == 'red':
            raise ValidationError('claim_value_not_in_source:' + row['content_unit_id'] + ' (' + row['reason'] + ')')
    return rows
