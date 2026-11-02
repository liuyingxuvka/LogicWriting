"""Every exception handler that does not re-raise is listed here with the reason it may stay.

The scan below is computed from the source (shipped skill scripts, route scripts and repository scripts),
so a new handler that swallows an error fails this test until someone either lets the error through or
states why the handler is the one route: it reports the error with its text, or the caught error is the
answer to the question the code asks. Behaviour tests for the cases that used to hide an error live in
tests/contract/test_one_route.py.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
F = 'skills/logic-writing/routes/fiction/scripts/'
T = 'skills/logic-writing/routes/travel/scripts/'
S = 'skills/logic-writing/scripts/'

REPORTED = 'the error becomes a reported issue, a blocked result or a nonzero exit that carries its text'
READ_REPORTED = 'a file that cannot be read or parsed is added as a read_error/json_decode_error issue and the report fails'
PARSE = 'a parse attempt whose failure is the answer (not a date, not this format); the caller reports the value as invalid'
UNBOUND = 'an unreadable mesh, contract or report becomes a world_report_unbound/mismatch problem, which fails closure'

NON_RAISING_HANDLERS = {
    F + 'chapter_interface_check.py:validate:storyline_route_check.RouteBlocked': REPORTED,
    F + 'chapter_interface_check.py:main:OSError': READ_REPORTED,
    F + 'chapter_interface_check.py:main:json.JSONDecodeError': READ_REPORTED,
    F + 'fiction_plan.py:load_context:(OSError, UnicodeError, json.JSONDecodeError)': REPORTED,
    F + 'longform_closure_check.py:_read_reference:(OSError, ValueError)': REPORTED,
    F + 'longform_closure_check.py:validate:(OSError, UnicodeError, ValueError)': REPORTED,
    F + 'longform_closure_check.py:main:(OSError, UnicodeError, ValueError)': READ_REPORTED,
    F + 'novel_ledger_check.py:validate_target:storyline_route_check.RouteBlocked': REPORTED,
    F + 'novel_ledger_check.py:main:OSError': READ_REPORTED,
    F + 'novel_ledger_check.py:main:json.JSONDecodeError': READ_REPORTED,
    F + 'promise_payoff_check.py:main:OSError': READ_REPORTED,
    F + 'promise_payoff_check.py:main:json.JSONDecodeError': READ_REPORTED,
    F + 'run_longform_regression.py:parse_json:json.JSONDecodeError':
        'repository regression runner: output that is not JSON has no payload, so the case cannot match an expected issue code and fails',
    F + 'run_route_regression.py:run_case:RouteBlocked':
        'repository regression runner: an expected block is the case answer; any other block fails the case with its code',
    F + 'run_route_regression.py:review_taxonomy_contract:RouteBlocked': 'each unexpected block is appended to the failures that fail the run',
    F + 'scene_contract_check.py:worldguard_claim_passable:ValueError': 'a WorldGuard claim whose status cannot be read is not passable: the check fails closed',
    F + 'scene_contract_check.py:validate_scene_contracts:ValueError': REPORTED,
    F + 'scene_contract_check.py:main:OSError': READ_REPORTED,
    F + 'scene_contract_check.py:main:json.JSONDecodeError': READ_REPORTED,
    F + 'story_contribution_check.py:validate:storyline_route_check.RouteBlocked': REPORTED,
    F + 'story_contribution_check.py:main:OSError': READ_REPORTED,
    F + 'story_contribution_check.py:main:json.JSONDecodeError': READ_REPORTED,
    F + 'story_ledger_check.py:validate_ledger:ValueError': REPORTED,
    F + 'story_ledger_check.py:main:OSError': READ_REPORTED,
    F + 'story_ledger_check.py:main:json.JSONDecodeError': READ_REPORTED,
    F + 'storyline_project_mesh_check.py:contained:ValueError': REPORTED,
    F + 'storyline_project_mesh_check.py:load_json:(OSError, json.JSONDecodeError)': REPORTED,
    F + 'storyline_project_mesh_check.py:run_native_owner:json.JSONDecodeError':
        'a native owner whose output is not JSON is recorded as failed with its stdout, stderr and exit code',
    F + 'storyline_route_check.py:main:RouteBlocked': REPORTED,
    F + 'turning_point_check.py:main:OSError': READ_REPORTED,
    F + 'turning_point_check.py:main:json.JSONDecodeError': READ_REPORTED,
    F + 'voice_style_continuity_check.py:main:OSError': READ_REPORTED,
    F + 'voice_style_continuity_check.py:main:json.JSONDecodeError': READ_REPORTED,
    T + 'travel_contract.py:_parse_iso_date:ValueError': PARSE,
    T + 'travel_contract.py:_parse_iso_datetime:ValueError': PARSE,
    T + 'travel_contract.py:review_plan_file:FileNotFoundError': REPORTED,
    T + 'travel_contract.py:review_plan_file:(OSError, UnicodeError, json.JSONDecodeError)': REPORTED,
    T + 'validate_failure_cases.py:run_case:(OSError, UnicodeError, json.JSONDecodeError)': REPORTED,
    T + 'validate_failure_cases.py:run_case:MutationError': REPORTED,
    T + 'validate_positive_cases.py:run_case:(OSError, UnicodeError, json.JSONDecodeError)': REPORTED,
    T + 'validate_positive_cases.py:run_case:MutationError': REPORTED,
    T + 'validate_travel_text_outputs.py:validate_failure_dir:(OSError, UnicodeError, json.JSONDecodeError)': REPORTED,
    T + 'validate_travel_text_outputs.py:validate_failure_dir:MutationError': REPORTED,
    S + '_common.py:cli_validate:(ValidationError, OSError, json.JSONDecodeError)': REPORTED,
    S + '_common.py:read_worldguard_report:(OSError, UnicodeError, ValueError, TypeError)':
        "an unreadable report is the status 'unreadable', which never passes",
    S + '_common.py:worldguard_report_identity_problems:(ImportError, OSError, UnicodeError, ValueError, TypeError)': UNBOUND,
    S + '_common.py:worldguard_report_identity_problems:yaml.YAMLError': UNBOUND,
    S + '_common.py:worldguard_report_identity_problems:(OSError, UnicodeError, ValueError, TypeError)': UNBOUND,
    S + '_common.py:worldguard_report_identity_problems:ImportError': UNBOUND,
    S + '_common.py:worldguard_report_identity_problems:(OSError, UnicodeError, ValueError, yaml.YAMLError)': UNBOUND,
    S + '_common.py:input_digest_problems:(OSError, ValueError)': 'an input file that cannot be read is reported stale by its path',
    S + 'build_source_unit_manifest.py:main:(ValidationError, OSError, json.JSONDecodeError)': REPORTED,
    S + 'derive_closure.py:provider_checks:(OSError, ValueError, UnicodeError)':
        "an unreadable ResearchGuard report is status 'unreadable' with the read error as its reason; it never passes",
    S + 'derive_closure.py:main:(OSError, ValueError, ValidationError)': REPORTED,
    S + 'known_bad.py:_first_rejection:ValidationError': 'a rejected bad variant is the answer the generator looks for; the error is recorded as how it was caught',
    S + 'known_bad.py:check_known_bad:ValidationError': 'a rejected bad variant is the answer the generator looks for; the error is recorded as how it was caught',
    S + 'known_bad.py:main:(OSError, ValueError, ValidationError)': REPORTED,
    S + 'provider_preflight.py:_researchguard_distribution:importlib.metadata.PackageNotFoundError':
        "a missing distribution answers 'not installed'; the preflight reports provider_unavailable",
    S + 'provider_preflight.py:_run_console_probe:subprocess.TimeoutExpired': 'a probe that times out is a failed probe with timed_out and its reason',
    S + 'provider_preflight.py:_run_console_probe:OSError': 'a probe that cannot start is a failed probe with its reason',
    S + 'provider_preflight.py:_worldguard_preflight:(OSError, UnicodeError)': 'reported as provider_unavailable with the reason',
    S + 'provider_preflight.py:_worldguard_preflight:(OSError, SyntaxError, UnicodeError, subprocess.TimeoutExpired)':
        'reported as provider_unavailable with the exception name',
    S + 'reader_fill.py:fill_check_fingerprints:ValidationError': 'quote errors of every binding are collected and raised together',
    S + 'researchguard_status.py:research_report_identity_problems:(OSError, UnicodeError, yaml.YAMLError)':
        'research.yaml is a required input digest: when it cannot be read, its digest problem is already in the returned list',
    S + 'run_chain.py:_finish:(OSError, ValueError, KeyError, TypeError)':
        "the readback line is a view: it names the error and keeps the chain's real state; the chain result is unchanged",
    S + 'run_chain.py:run_chain:(OSError, ValueError)': REPORTED,
    S + 'run_chain.py:run_chain:(OSError, json.JSONDecodeError)': REPORTED,
    S + 'run_chain.py:run_chain:(ValidationError, ValueError, KeyError, TypeError)': REPORTED,
    S + 'run_chain.py:_stamp_review:(OSError, ValueError, KeyError, TypeError)': REPORTED,
    S + 'schema_validation.py:_valid_date_time:ValueError': PARSE,
    S + 'schema_validation.py:validate_schema:(TypeError, ValueError)':
        'an artifact that does not round-trip through canonical JSON is validated without the memo; only caching is skipped',
    S + 'show_argument.py:main:(OSError, ValueError, TypeError, KeyError)': REPORTED,
    S + 'show_plan.py:_partial_shared:ValidationError': 'a quote that does not resolve leaves that binding unbound, shown as UNBOUND in the readback',
    S + 'show_plan.py:_results:(OSError, UnicodeError, ValueError)': "a broken result file reads back as 'unreadable', never as not run",
    S + 'show_plan.py:main:(OSError, ValueError, TypeError, KeyError)': REPORTED,
    'scripts/run_fiction_regression.py:_run_case:subprocess.TimeoutExpired': 'a case that times out is reported timed_out and fails',
    'scripts/validate_skill.py:validate_skill:ValueError': REPORTED,
    'scripts/validate_skill.py:validate_skill:SyntaxError': REPORTED,
}


def _non_raising_handlers() -> dict[str, int]:
    found: dict[str, int] = {}
    paths = sorted((ROOT / 'skills/logic-writing').rglob('*.py')) + sorted((ROOT / 'scripts').glob('*.py'))
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()

        def visit(node, names):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    visit(child, names + [child.name])
                    continue
                if isinstance(child, ast.ExceptHandler):
                    body = ast.Module(body=child.body, type_ignores=[])
                    if not any(isinstance(item, ast.Raise) for item in ast.walk(body)):
                        caught = ast.unparse(child.type) if child.type else 'BARE'
                        key = f"{relative}:{'.'.join(names) or '<module>'}:{caught}"
                        found[key] = found.get(key, 0) + 1
                visit(child, names)

        visit(ast.parse(path.read_text(encoding='utf-8')), [])
    return found


def test_every_non_raising_handler_is_listed_with_a_reason():
    found = _non_raising_handlers()
    assert not [key for key in found if key.endswith(':BARE')], 'a bare except swallows everything, including KeyboardInterrupt'
    assert not [key for key in found if key.endswith(':Exception') or key.endswith(':BaseException')], \
        'a broad Exception handler hides programming errors: catch the domain errors it means'
    assert sorted(set(found) - set(NON_RAISING_HANDLERS)) == [], 'new handlers that do not re-raise: let the error through or state why'
    assert sorted(set(NON_RAISING_HANDLERS) - set(found)) == [], 'listed handlers that no longer exist: drop them'
    assert all(reason.strip() for reason in NON_RAISING_HANDLERS.values())
