"""Every exception handler that can end without raising is listed here, with how many, why, and the rule it serves.

The scan below is computed from the source (shipped skill scripts, route scripts and repository scripts):
- a handler counts as re-raising only when every path through its body raises, so a `raise` inside one
  branch does not hide the other branches;
- `contextlib.suppress(...)` is a handler too, however it is reached (imported under another name, read from
  an alias of the module, assigned to a new name or fetched with getattr), and so is a class whose `__exit__`
  can return something other than None or False (it swallows the error of its `with` block);
- a `return`, `break` or `continue` inside `finally` (which drops the error in flight) is forbidden;
- each key is listed with the number of such handlers in that function, so a second quiet handler of the
  same kind fails the test;
- each entry names the requirement it comes from as a sentence that must be present in that file.
A new handler that swallows an error fails this test until someone lets the error through or states why the
handler is the one route. Behaviour tests for the cases that used to hide an error live in
tests/contract/test_one_route.py; the default reads (`.get(key, default)`, `.get(key) or default`,
`getattr(obj, name, default)`) are inventoried in tests/contract/default_reads.py.

What the scan cannot see: a handler reached only through code it does not parse (exec, a string import), a context
manager made elsewhere (contextlib.ExitStack callbacks, a library class), and other quiet defaults such as
`next(iterator, default)` or `dict.setdefault`; those are not inventoried.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import NamedTuple

from tests.contract.default_reads import DEFAULT_READS, GETATTR_DEFAULTS, OR_DEFAULT_READS

ROOT = Path(__file__).resolve().parents[2]
F = 'skills/logic-writing/routes/fiction/scripts/'
T = 'skills/logic-writing/routes/travel/scripts/'
S = 'skills/logic-writing/scripts/'

# The rule each kept handler serves: a file and a sentence that file must contain (whitespace is normalised).
REQUIREMENTS = {
    'one-route': ('AGENTS.md', 'One route per function: when a step fails, the error reaches the caller or is reported with its text'),
    'exit-codes': (S[:-8] + 'references/shared/reader-chain.md',
                   'exit 0 for a passing chain, 1 for a native rejection, 2 for unreadable'),
    'report-unreadable': (S[:-8] + 'references/shared/closure.md', 'An unreadable report stays `unreadable`.'),
    'world-unbound': (S[:-8] + 'references/shared/closure.md',
                      'no readable `world_contract` is `world_report_unbound:world_contract`'),
    'research-digests': (S[:-8] + 'references/shared/closure.md', 'Changed or missing bytes are `research_report_stale:<path>`'),
    'provider-unavailable': (S[:-8] + 'references/adapters/researchguard.md',
                             'Missing, ambiguous, failed or timed-out consoles stay `provider_unavailable`'),
    'travel-iso-date': (S[:-8] + 'routes/travel/references/source-portfolio.md', 'Each source records `checked_on` as an ISO date.'),
    'schema-date-time': (S[:-8] + 'assets/schemas/reader-judgment.schema.json', '"format": "date-time"'),
    'known-bad': (S[:-8] + 'SKILL.md', 'each one must be caught, and closure lists uncaught ones'),
    'readback-unbound': (S[:-8] + 'references/shared/reader-chain-inputs.md',
                         'shows the plan tree even before drafting, with `UNBOUND` units'),
    'brief-stale': (S[:-8] + 'references/shared/reader-chain.md',
                    'the summary line starts with `brief: stale (...)` and names why (the brief was built from an older '
                    'request, or the request no longer builds, with its error)'),
}


class H(NamedTuple):
    requirement: str
    reason: str
    count: int = 1


REPORTED = 'the error becomes a reported issue, a blocked result or a nonzero exit that carries its text'
READ_REPORTED = 'a file that cannot be read or parsed is added as a read_error/json_decode_error issue and the report fails'
PARSE = 'a parse attempt whose failure is the answer (not a date, not this format); the caller reports the value as invalid'
UNBOUND = 'an unreadable mesh, contract or report becomes a world_report_unbound/mismatch problem, which fails closure'
RUNNER = 'repository regression runner: the case fails with the error text'

NON_RAISING_HANDLERS = {
    F + 'chapter_interface_check.py:validate:storyline_route_check.RouteBlocked': H('one-route', REPORTED),
    F + 'chapter_interface_check.py:main:OSError': H('one-route', READ_REPORTED),
    F + 'chapter_interface_check.py:main:json.JSONDecodeError': H('one-route', READ_REPORTED),
    F + 'fiction_plan.py:load_context:(OSError, UnicodeError, json.JSONDecodeError)': H('one-route', REPORTED),
    F + 'longform_closure_check.py:_read_reference:(OSError, ValueError)': H('one-route', REPORTED),
    F + 'longform_closure_check.py:validate:(OSError, UnicodeError, ValueError)': H('one-route', REPORTED),
    F + 'longform_closure_check.py:main:(OSError, UnicodeError, ValueError)': H('one-route', READ_REPORTED),
    F + 'novel_ledger_check.py:validate_target:storyline_route_check.RouteBlocked': H('one-route', REPORTED),
    F + 'novel_ledger_check.py:main:OSError': H('one-route', READ_REPORTED),
    F + 'novel_ledger_check.py:main:json.JSONDecodeError': H('one-route', READ_REPORTED),
    F + 'promise_payoff_check.py:main:OSError': H('one-route', READ_REPORTED),
    F + 'promise_payoff_check.py:main:json.JSONDecodeError': H('one-route', READ_REPORTED),
    F + 'run_longform_regression.py:parse_json:json.JSONDecodeError': H('one-route',
        RUNNER + ': output that is not JSON has no payload, so the case cannot match an expected issue code and fails'),
    F + 'run_route_regression.py:run_case:RouteBlocked': H('one-route',
        RUNNER + ': an expected block is the case answer; any other block fails the case with its code'),
    F + 'run_route_regression.py:review_taxonomy_contract:RouteBlocked': H('one-route',
        'each unexpected block is appended to the failures that fail the run', count=2),
    F + 'scene_contract_check.py:worldguard_claim_passable:ValueError': H('report-unreadable',
        'a WorldGuard claim whose status cannot be read is not passable: the check fails closed'),
    F + 'scene_contract_check.py:validate_scene_contracts:ValueError': H('one-route', REPORTED),
    F + 'scene_contract_check.py:main:OSError': H('one-route', READ_REPORTED),
    F + 'scene_contract_check.py:main:json.JSONDecodeError': H('one-route', READ_REPORTED),
    F + 'story_contribution_check.py:validate:storyline_route_check.RouteBlocked': H('one-route', REPORTED),
    F + 'story_contribution_check.py:main:OSError': H('one-route', READ_REPORTED),
    F + 'story_contribution_check.py:main:json.JSONDecodeError': H('one-route', READ_REPORTED),
    F + 'story_ledger_check.py:validate_ledger:ValueError': H('one-route', REPORTED),
    F + 'story_ledger_check.py:main:OSError': H('one-route', READ_REPORTED),
    F + 'story_ledger_check.py:main:json.JSONDecodeError': H('one-route', READ_REPORTED),
    F + 'storyline_project_mesh_check.py:contained:ValueError': H('one-route', REPORTED),
    F + 'storyline_project_mesh_check.py:load_json:(OSError, json.JSONDecodeError)': H('one-route', REPORTED),
    F + 'storyline_project_mesh_check.py:run_native_owner:json.JSONDecodeError': H('one-route',
        'a native owner whose output is not JSON is recorded as failed with its stdout, stderr and exit code'),
    F + 'storyline_route_check.py:main:RouteBlocked': H('one-route', REPORTED),
    F + 'turning_point_check.py:main:OSError': H('one-route', READ_REPORTED),
    F + 'turning_point_check.py:main:json.JSONDecodeError': H('one-route', READ_REPORTED),
    F + 'voice_style_continuity_check.py:main:OSError': H('one-route', READ_REPORTED),
    F + 'voice_style_continuity_check.py:main:json.JSONDecodeError': H('one-route', READ_REPORTED),
    T + 'travel_contract.py:_parse_iso_date:ValueError': H('travel-iso-date', PARSE),
    T + 'travel_contract.py:_parse_iso_datetime:ValueError': H('travel-iso-date', PARSE),
    T + 'travel_contract.py:review_plan_file:FileNotFoundError': H('one-route', REPORTED),
    T + 'travel_contract.py:review_plan_file:(OSError, UnicodeError, json.JSONDecodeError)': H('one-route', REPORTED),
    T + 'validate_failure_cases.py:run_case:(OSError, UnicodeError, json.JSONDecodeError)': H('one-route', REPORTED, count=2),
    T + 'validate_failure_cases.py:run_case:MutationError': H('one-route', REPORTED),
    T + 'validate_positive_cases.py:run_case:(OSError, UnicodeError, json.JSONDecodeError)': H('one-route', REPORTED, count=2),
    T + 'validate_positive_cases.py:run_case:MutationError': H('one-route', REPORTED),
    T + 'validate_travel_text_outputs.py:validate_failure_dir:(OSError, UnicodeError, json.JSONDecodeError)': H('one-route', REPORTED),
    T + 'validate_travel_text_outputs.py:validate_failure_dir:MutationError': H('one-route', REPORTED),
    S + '_common.py:cli_validate:(ValidationError, OSError, json.JSONDecodeError)': H('exit-codes', REPORTED),
    S + '_common.py:read_worldguard_report:(OSError, UnicodeError, ValueError, TypeError)': H('report-unreadable',
        "an unreadable report is the status 'unreadable', which never passes"),
    S + '_common.py:worldguard_report_identity_problems:(ImportError, OSError, UnicodeError, ValueError, TypeError)':
        H('world-unbound', UNBOUND),
    S + '_common.py:worldguard_report_identity_problems:yaml.YAMLError': H('world-unbound', UNBOUND),
    S + '_common.py:worldguard_report_identity_problems:(OSError, UnicodeError, ValueError, TypeError)':
        H('world-unbound', UNBOUND, count=2),
    S + '_common.py:worldguard_report_identity_problems:ImportError': H('world-unbound', UNBOUND),
    S + '_common.py:worldguard_report_identity_problems:(OSError, UnicodeError, ValueError, yaml.YAMLError)':
        H('world-unbound', UNBOUND),
    S + '_common.py:input_digest_problems:(OSError, ValueError)': H('research-digests',
        'an input file that cannot be read is reported stale by its path'),
    S + 'build_source_unit_manifest.py:main:(ValidationError, OSError, json.JSONDecodeError)': H('exit-codes', REPORTED),
    S + 'derive_closure.py:provider_checks:(OSError, ValueError, UnicodeError)': H('report-unreadable',
        "an unreadable ResearchGuard report is status 'unreadable' with the read error as its reason; it never passes"),
    S + 'derive_closure.py:main:(OSError, ValueError, ValidationError)': H('exit-codes', REPORTED),
    S + 'known_bad.py:_first_rejection:ValidationError': H('known-bad',
        'a rejected bad variant is the answer the generator looks for; the error is recorded as how it was caught'),
    S + 'known_bad.py:check_known_bad:ValidationError': H('known-bad',
        'a rejected bad variant is the answer the generator looks for; the error is recorded as how it was caught'),
    S + 'known_bad.py:main:(OSError, ValueError, ValidationError)': H('exit-codes', REPORTED),
    S + 'provider_preflight.py:_researchguard_distribution:importlib.metadata.PackageNotFoundError': H('provider-unavailable',
        "a missing distribution answers 'not installed'; the preflight reports provider_unavailable"),
    S + 'provider_preflight.py:_run_console_probe:subprocess.TimeoutExpired': H('provider-unavailable',
        'a probe that times out is a failed probe with timed_out and its reason'),
    S + 'provider_preflight.py:_run_console_probe:OSError': H('provider-unavailable', 'a probe that cannot start is a failed probe with its reason'),
    S + 'provider_preflight.py:_worldguard_preflight:(OSError, UnicodeError)': H('provider-unavailable',
        'reported as provider_unavailable with the reason'),
    S + 'provider_preflight.py:_worldguard_preflight:(OSError, SyntaxError, UnicodeError, subprocess.TimeoutExpired)':
        H('provider-unavailable', 'reported as provider_unavailable with the exception name'),
    S + 'reader_fill.py:fill_check_fingerprints:ValidationError': H('one-route', 'quote errors of every binding are collected and raised together'),
    S + 'researchguard_status.py:research_report_identity_problems:(OSError, UnicodeError, yaml.YAMLError)': H('research-digests',
        'research.yaml is a required input digest: when it cannot be read, its digest problem is already in the returned list'),
    S + 'run_chain.py:_finish:(OSError, ValueError, KeyError, TypeError)': H('exit-codes',
        "the readback line is a view: it names the error and keeps the chain's real state; the exit code is unchanged"),
    S + 'run_chain.py:run_chain:(OSError, ValueError)': H('exit-codes', REPORTED),
    S + 'run_chain.py:run_chain:(OSError, json.JSONDecodeError)': H('exit-codes', REPORTED),
    S + 'run_chain.py:run_chain:(ValidationError, ValueError, KeyError, TypeError)': H('exit-codes', REPORTED),
    S + 'run_chain.py:_stamp_review:(OSError, ValueError, KeyError, TypeError)': H('exit-codes', REPORTED),
    S + 'schema_validation.py:_valid_date_time:ValueError': H('schema-date-time', PARSE),
    S + 'show_argument.py:main:(OSError, ValueError, TypeError, KeyError)': H('exit-codes', REPORTED),
    S + 'show_plan.py:_partial_shared:ValidationError': H('readback-unbound',
        'a quote that does not resolve leaves that binding unbound, shown as UNBOUND in the readback'),
    S + 'show_plan.py:_brief_state:(OSError, ValueError, KeyError, TypeError)': H('brief-stale',
        'a request that no longer builds is the stale answer: its error text starts the summary and the picture problems'),
    S + 'show_plan.py:_results:(OSError, UnicodeError, ValueError)': H('report-unreadable',
        "a broken result file reads back as 'unreadable', never as not run"),
    S + 'show_plan.py:main:(OSError, ValueError, TypeError, KeyError)': H('exit-codes', REPORTED),
    'scripts/run_fiction_regression.py:_run_case:subprocess.TimeoutExpired': H('one-route', RUNNER + ': a case that times out is reported timed_out'),
    'scripts/validate_skill.py:validate_skill:ValueError': H('one-route', REPORTED),
    'scripts/validate_skill.py:validate_skill:SyntaxError': H('one-route', REPORTED),
}

RAISE, EXIT, FALL = 'raise', 'exit', 'fall'


def _block(statements) -> str:
    """'raise' when every path through these statements raises, 'exit' when one can leave without raising."""
    for statement in statements:
        outcome = _statement(statement)
        if outcome != FALL:
            return outcome
    return FALL


def _returns(statements) -> bool:
    return any(isinstance(node, ast.Return) for statement in statements for node in ast.walk(statement))


def _statement(node) -> str:
    if isinstance(node, ast.Raise):
        return RAISE
    if isinstance(node, (ast.Return, ast.Break, ast.Continue)):
        return EXIT
    if isinstance(node, ast.If):
        outcomes = (_block(node.body), _block(node.orelse))
        return RAISE if outcomes == (RAISE, RAISE) else EXIT if EXIT in outcomes else FALL
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return _block(node.body)
    if isinstance(node, (ast.Try, getattr(ast, 'TryStar', ast.Try))):
        if _block(node.finalbody) == RAISE:
            return RAISE
        body, handlers, orelse = _block(node.body), [_block(row.body) for row in node.handlers], _block(node.orelse)
        if body == RAISE and all(outcome == RAISE for outcome in handlers):
            return RAISE
        return EXIT if EXIT in (body, *handlers, orelse) else FALL
    if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):  # the body may not run; a return inside still leaves
        return EXIT if _returns(node.body) or _returns(node.orelse) else FALL
    return FALL


def _sources():
    paths = sorted((ROOT / 'skills/logic-writing').rglob('*.py')) + sorted((ROOT / 'scripts').glob('*.py'))
    for path in paths:
        yield path.relative_to(ROOT).as_posix(), ast.parse(path.read_text(encoding='utf-8'))


def _walk(tree):
    """(node, enclosing function names) for every node, function bodies included."""
    stack = [(tree, [])]
    while stack:
        node, names = stack.pop()
        for child in ast.iter_child_nodes(node):
            inner = names + [child.name] if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else names
            yield child, inner
            stack.append((child, inner))


def _call_name(node) -> str:
    return node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ''


def _suppress_names(tree) -> tuple[set[str], set[str]]:
    """Names in this module that stand for contextlib.suppress, and names bound to the contextlib module."""
    functions, modules = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == 'contextlib':
            # `from contextlib import *` binds suppress under its own name.
            functions.update('suppress' if alias.name == '*' else alias.asname or alias.name
                             for alias in node.names if alias.name in ('suppress', '*'))
        elif isinstance(node, ast.Import):
            modules.update(alias.asname or alias.name for alias in node.names if alias.name == 'contextlib')

    def refers(value) -> bool:
        if isinstance(value, ast.Name):
            return value.id in functions
        if isinstance(value, ast.Attribute):
            return value.attr == 'suppress'
        return (isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == 'getattr'
                and len(value.args) >= 2 and isinstance(value.args[1], ast.Constant) and value.args[1].value == 'suppress')
    changed = True
    while changed:  # `hush = contextlib.suppress`, `also = hush`: every name assigned a suppress is one too
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and refers(node.value):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id not in functions:
                        functions.add(target.id)
                        changed = True
    return functions, modules


def _is_suppress_call(node, functions) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in functions
    if isinstance(func, ast.Attribute):
        return func.attr == 'suppress'
    return (isinstance(func, ast.Call) and isinstance(func.func, ast.Name) and func.func.id == 'getattr'
            and len(func.args) >= 2 and isinstance(func.args[1], ast.Constant) and func.args[1].value == 'suppress')


def _may_return_true(function) -> bool:
    """An __exit__ that can return anything but None or False swallows the error of its with block."""
    if isinstance(function, ast.Lambda):
        return not (isinstance(function.body, ast.Constant) and function.body.value in (None, False))
    stack = list(function.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Return) and node.value is not None and not (
                isinstance(node.value, ast.Constant) and node.value.value in (None, False)):
            return True
        stack.extend(ast.iter_child_nodes(node))
    return False


def _handlers_in(relative: str, tree) -> dict[str, int]:
    """Every place in one module where an error can end without being raised, by function, with how many."""
    found: dict[str, int] = {}
    functions, _ = _suppress_names(tree)
    for node, names in _walk(tree):
        where = f"{relative}:{'.'.join(names) or '<module>'}"
        if isinstance(node, ast.ExceptHandler) and _block(node.body) != RAISE:
            key = f"{where}:{ast.unparse(node.type) if node.type else 'BARE'}"
        elif isinstance(node, ast.Call) and _is_suppress_call(node, functions):
            key = f"{where}:suppress({', '.join(ast.unparse(argument) for argument in node.args)})"
        elif (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in ('__exit__', '__aexit__')
              and len(names) >= 2 and _may_return_true(node)):
            key = f"{where}:may return true"
        elif (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in ('__exit__', '__aexit__')
                                                    for target in node.targets)
              and isinstance(node.value, ast.Lambda) and _may_return_true(node.value)):
            key = f"{where}:__exit__ may return true"
        else:
            continue
        found[key] = found.get(key, 0) + 1
    return found


def _merged(scan) -> dict[str, int]:
    found: dict[str, int] = {}
    for relative, tree in _sources():
        for key, count in scan(relative, tree).items():
            found[key] = found.get(key, 0) + count
    return found


def _non_raising_handlers() -> dict[str, int]:
    return _merged(_handlers_in)


def _finally_exits() -> list[str]:
    return [f'{relative}:{node.lineno}' for relative, tree in _sources() for node, _ in _walk(tree)
            if isinstance(node, ast.Try) and _block(node.finalbody) == EXIT]


def _default_reads_in(relative: str, tree) -> dict[str, int]:
    """`.get(key, default)` calls, by function: a missing key quietly becomes the default."""
    found: dict[str, int] = {}
    for node, names in _walk(tree):
        if isinstance(node, ast.Call) and _call_name(node) == 'get' and isinstance(node.func, ast.Attribute) and len(node.args) == 2:
            key = f"{relative}:{'.'.join(names) or '<module>'}"
            found[key] = found.get(key, 0) + 1
    return found


def _or_default_reads_in(relative: str, tree) -> dict[str, int]:
    """`.get(key) or default`, by function: a missing (or empty) value quietly becomes what follows the `or`."""
    found: dict[str, int] = {}
    for node, names in _walk(tree):
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            count = sum(1 for value in node.values[:-1] if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
                        and value.func.attr == 'get' and len(value.args) == 1 and not value.keywords)
            if count:
                key = f"{relative}:{'.'.join(names) or '<module>'}"
                found[key] = found.get(key, 0) + count
    return found


def _getattr_defaults_in(relative: str, tree) -> dict[str, int]:
    """`getattr(obj, name, default)`, by function: a missing attribute quietly becomes the default."""
    found: dict[str, int] = {}
    for node, names in _walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'getattr' and len(node.args) == 3:
            key = f"{relative}:{'.'.join(names) or '<module>'}"
            found[key] = found.get(key, 0) + 1
    return found


def _default_reads() -> dict[str, int]:
    return _merged(_default_reads_in)


def test_every_non_raising_handler_is_listed_with_its_count_reason_and_requirement():
    found = _non_raising_handlers()
    assert not [key for key in found if key.endswith(':BARE')], 'a bare except swallows everything, including KeyboardInterrupt'
    assert not [key for key in found if key.endswith(':Exception') or key.endswith(':BaseException')], \
        'a broad Exception handler hides programming errors: catch the domain errors it means'
    assert sorted(set(found) - set(NON_RAISING_HANDLERS)) == [], 'new handlers that can end without raising: let the error through or state why'
    assert sorted(set(NON_RAISING_HANDLERS) - set(found)) == [], 'listed handlers that no longer exist: drop them'
    assert {key: count for key, count in found.items() if NON_RAISING_HANDLERS[key].count != count} == {}, \
        'the number of such handlers in a function changed: list each one'
    assert all(row.reason.strip() and row.requirement in REQUIREMENTS for row in NON_RAISING_HANDLERS.values())


def test_each_requirement_named_by_a_handler_is_stated_in_its_file():
    for identity, (relative, sentence) in REQUIREMENTS.items():
        text = ' '.join((ROOT / relative).read_text(encoding='utf-8').split())
        assert ' '.join(sentence.split()) in text, f'{identity}: {relative} does not state {sentence!r}'
    assert {row.requirement for row in NON_RAISING_HANDLERS.values()} == set(REQUIREMENTS), 'a requirement no handler names: drop it'


def test_no_finally_block_drops_the_error_in_flight():
    assert _finally_exits() == []


def test_every_default_read_is_in_the_inventory():
    assert _default_reads() == DEFAULT_READS, 'a .get(key, default) read was added or removed: update tests/contract/default_reads.py'


def test_the_scan_sees_conditional_raises_duplicates_and_suppress(tmp_path):
    """The scanner itself: a raise in one branch, a second quiet handler and contextlib.suppress are all counted."""
    code = '''
import contextlib
def f(x):
    try:
        g()
    except (OSError, ValueError) as error:
        if x:
            raise
        return None
    try:
        g()
    except (OSError, ValueError):
        y = 0
    with contextlib.suppress(OSError):
        g()
    try:
        g()
    except KeyError:
        raise RuntimeError('wrapped') from None
'''
    tree = ast.parse(code)
    handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]
    assert [_block(row.body) for row in handlers] == [EXIT, FALL, RAISE]
    assert [_call_name(node) for node in ast.walk(tree) if isinstance(node, ast.Call) and _call_name(node) == 'suppress'] == ['suppress']


def test_the_scan_sees_aliased_suppress_and_context_managers_that_swallow():
    """Review gap: an aliased contextlib.suppress and a context manager whose __exit__ returns True were not counted."""
    code = '''
import contextlib as cl
from contextlib import suppress as quiet
hush = cl.suppress
also = getattr(cl, 'suppress')
class Swallow:
    def __enter__(self):
        return self
    def __exit__(self, *details):
        return True
class Passes:
    def __exit__(self, *details):
        return None
class Lambda:
    __exit__ = lambda self, *details: True
def f():
    with quiet(OSError):
        g()
    with cl.suppress(KeyError):
        g()
    with hush(ValueError):
        g()
    with also(TypeError):
        g()
'''
    found = _handlers_in('probe.py', ast.parse(code))
    assert found == {'probe.py:f:suppress(OSError)': 1, 'probe.py:f:suppress(KeyError)': 1,
                     'probe.py:f:suppress(ValueError)': 1, 'probe.py:f:suppress(TypeError)': 1,
                     'probe.py:Swallow.__exit__:may return true': 1, 'probe.py:Lambda:__exit__ may return true': 1}


def test_the_scan_sees_or_defaults_and_getattr_defaults():
    """Review gap: `.get(k) or default` and `getattr(o, n, default)` turned a missing value into a default unseen."""
    code = '''
def f(row, obj):
    a = row.get('a') or []
    b = row.get('b') or row.get('c') or 'none'
    c = row.get('d', 0)
    d = getattr(obj, 'version', '')
    e = getattr(obj, 'version')
    return row.get('e') and a
'''
    tree = ast.parse(code)
    assert _or_default_reads_in('probe.py', tree) == {'probe.py:f': 3}
    assert _getattr_defaults_in('probe.py', tree) == {'probe.py:f': 1}


def test_every_or_default_and_getattr_default_is_in_the_inventory():
    assert _merged(_or_default_reads_in) == OR_DEFAULT_READS, \
        'a `.get(key) or default` read was added or removed: update tests/contract/default_reads.py'
    assert _merged(_getattr_defaults_in) == GETATTR_DEFAULTS, \
        'a getattr(obj, name, default) read was added or removed: update tests/contract/default_reads.py'
