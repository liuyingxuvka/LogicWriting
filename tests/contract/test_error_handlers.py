"""The original policy assertions use the shared map instead of a second AST scanner."""
from __future__ import annotations
import ast
from contextlib import closing
from pathlib import Path
import tempfile
from flowguard.structure import build
from flowguard.structure.query import handler_outcome
from tests.contract.error_policy import (ROOT, REQUIREMENTS, NON_RAISING_HANDLERS, DEFAULT_READS,
    OR_DEFAULT_READS, GETATTR_DEFAULTS, handler_counts, finally_exits, default_counts)

RAISE, EXIT, FALL = 'raise', 'exit', 'fall'


def _query(relative, tree, operation):
    with tempfile.TemporaryDirectory(prefix='lw-source-query-') as temporary:
        folder = Path(temporary)
        source = folder / 'source'
        path = source / relative
        path.parent.mkdir(parents=True)
        path.write_text(ast.unparse(tree) + '\n', encoding='utf-8')
        with closing(build(source, folder / 'map.sqlite')) as graph:
            return operation(graph)


def _block(statements):
    fall, exits = handler_outcome(statements)
    return EXIT if exits else FALL if fall else RAISE


def _call_name(node):
    return node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ''


def _handlers_in(relative, tree):
    return _query(relative, tree, lambda graph: handler_counts(graph, shipped_only=False))


def _default_reads_in(relative, tree):
    return _query(relative, tree, lambda graph: default_counts(graph, 'get', shipped_only=False))


def _or_default_reads_in(relative, tree):
    return _query(relative, tree, lambda graph: default_counts(graph, 'or_get', shipped_only=False))


def _getattr_defaults_in(relative, tree):
    return _query(relative, tree, lambda graph: default_counts(graph, 'getattr', shipped_only=False))


def _merged(scan):
    kind = {_default_reads_in: 'get', _or_default_reads_in: 'or_get', _getattr_defaults_in: 'getattr'}[scan]
    with closing(build(ROOT)) as graph:
        return default_counts(graph, kind)


def _non_raising_handlers():
    with closing(build(ROOT)) as graph:
        return handler_counts(graph)


def _finally_exits():
    with closing(build(ROOT)) as graph:
        return finally_exits(graph)


def _default_reads():
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
