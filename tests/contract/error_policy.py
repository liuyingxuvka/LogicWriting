"""LogicWriting's documented exception/default policy over shared source facts."""
from collections import Counter
from pathlib import Path
from typing import NamedTuple
from tests.contract.default_reads import DEFAULT_READS, OR_DEFAULT_READS, GETATTR_DEFAULTS

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
    F + '_fiction_common.py:json_check_cli:OSError': H('one-route', READ_REPORTED),
    F + '_fiction_common.py:json_check_cli:json.JSONDecodeError': H('one-route', READ_REPORTED),
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
    F + 'run_longform_regression.py:parse_json:json.JSONDecodeError': H('one-route',
        RUNNER + ': output that is not JSON has no payload, so the case cannot match an expected issue code and fails'),
    F + 'run_route_regression.py:run_case:RouteBlocked': H('one-route',
        RUNNER + ': an expected block is the case answer; any other block fails the case with its code'),
    F + 'run_route_regression.py:review_taxonomy_contract:RouteBlocked': H('one-route',
        'each unexpected block is appended to the failures that fail the run', count=2),
    F + 'scene_contract_check.py:worldguard_claim_passable:ValueError': H('report-unreadable',
        'a WorldGuard claim whose status cannot be read is not passable: the check fails closed'),
    F + 'scene_contract_check.py:validate_scene_contracts:ValueError': H('one-route', REPORTED),
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

def shipped(relative):
    return relative.startswith('skills/logic-writing/') or relative.startswith('scripts/') and len(Path(relative).parts) == 2


def where(row):
    return row['file'] + ':' + (row['node'].partition(':')[2] or '<module>')


def handler_rows(graph, *, shipped_only=True):
    return [row for row in graph.handlers() if (not shipped_only or shipped(row['file'])) and row['non_raising']
            and row['kind'] in {'except', 'suppress', 'exit_method'}]


def handler_key(row):
    return where(row) + ':' + (row['type'] or 'BARE')


def handler_counts(graph, *, shipped_only=True):
    return dict(Counter(handler_key(row) for row in handler_rows(graph, shipped_only=shipped_only)))


def finally_exits(graph):
    return [row['file'] + ':' + str(row['line']) for row in graph.handlers()
            if shipped(row['file']) and row['kind'] == 'finally']


def default_counts(graph, kind, *, shipped_only=True):
    def selected(row):
        name = row['text'].rsplit('.', 1)[-1]
        if kind == 'get':
            return '.' in row['text'] and name == 'get' and row['positional_arg_count'] == 2
        if kind == 'or_get':
            return ('.' in row['text'] and name == 'get' and row['positional_arg_count'] == 1
                    and row['keyword_count'] == 0 and row['boolop_or_nonfinal'])
        return row['text'] == 'getattr' and row['positional_arg_count'] == 3
    return dict(Counter(where(row) for row in graph.calls() if (not shipped_only or shipped(row['file'])) and selected(row)))


def violations(graph):
    rows = [dict(row, node=handler_key(row)) for row in handler_rows(graph)]
    counts = handler_counts(graph)
    for key, expected in NON_RAISING_HANDLERS.items():
        if counts.get(key, 0) != expected.count:
            rows.append(f'handler count {key}: {counts.get(key, 0)} instead of {expected.count}')
    for row in handler_rows(graph):
        if row['kind'] == 'except' and row['type'] in ('', 'Exception', 'BaseException'):
            rows.append('bare or broad handler: ' + handler_key(row))
    rows += ['finally drops the error: ' + item for item in finally_exits(graph)]
    for identity, (path, sentence) in REQUIREMENTS.items():
        if ' '.join(sentence.split()) not in ' '.join((graph.root / path).read_text(encoding='utf-8').split()):
            rows.append(f'{identity}: {path} no longer states its error boundary')
    return rows


def default_violations(graph):
    rows = []
    for kind, expected in [('get', DEFAULT_READS), ('or_get', OR_DEFAULT_READS), ('getattr', GETATTR_DEFAULTS)]:
        actual = default_counts(graph, kind)
        for node in sorted(set(actual) | set(expected)):
            if actual.get(node, 0) != expected.get(node, 0):
                rows.append(f'{kind} {node}: {actual.get(node, 0)} instead of {expected.get(node, 0)}')
    return rows
