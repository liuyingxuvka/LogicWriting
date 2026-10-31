"""Saved provider reports constrain broad claims while their raw inputs remain current.

ResearchGuard inputs are checked by digest; WorldGuard also retains its contract identity.
Closure never runs a provider. The independent trip validator reads raw saved status.
"""
from dataclasses import dataclass, replace
from pathlib import Path
import json
import shutil
import sys
import tempfile

from flowguard import (FunctionResult, Invariant, InvariantResult, ReplayObservation,
                       Workflow, replay_trace, select_covering_traces)
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFacts

MODEL_ID = 'closure_claim_model'
PARENT = 'reader-closure'
COMPONENTS = ['reader-closure', 'travel-model', 'researchguard-handoff']
IMPLEMENTED_BY = {
    "Reports": "skills/logic-writing/scripts/derive_closure.py:provider_checks",
    "ResearchVerdict": "skills/logic-writing/scripts/researchguard_status.py:assess_research_verdict",
    "ResearchIdentity": "skills/logic-writing/scripts/researchguard_status.py:research_report_identity_problems",
}
TESTED_BY = {
    "research_verdict_risks_are_preserved": [
        "tests/unit/test_closure_claim_model.py:test_provider_status_is_copied_from_the_report_file"
    ],
    "travel_world_failure_limits_claim": [
        "tests/unit/test_closure_claim_model.py:test_failing_world_report_limits_the_travel_closure"
    ],
    "broad_claim_needs_every_required_provider": [
        "tests/unit/test_closure_claim_model.py:test_missing_required_provider_report_blocks_the_broad_claim"
    ],
    "provider_status_is_copied_unchanged": [
        "tests/unit/test_closure_claim_model.py:test_provider_status_is_copied_from_the_report_file"
    ],
    "missing_or_failed_provider_is_named": [
        "tests/unit/test_closure_claim_model.py:test_unreadable_report_is_not_a_pass"
    ],
    "research_report_belongs_to_the_folder": [
        "tests/unit/test_researchguard_status.py:test_report_from_another_folder_fails_the_provider_check"
    ],
    "world_report_belongs_to_the_contract": [
        "tests/unit/test_closure_claim_model.py:test_world_report_for_another_contract_fails_closure",
        "tests/unit/test_world_mesh.py:test_tree_report_binds_like_a_contract",
        "tests/unit/test_world_mesh.py:test_old_tree_report_is_refused_with_the_regenerate_command",
    ],
    "research_report_is_current": [
        "tests/unit/test_closure_claim_model.py:test_stale_research_report_fails_the_provider_check",
        "tests/unit/test_closure_claim_model.py:test_report_missing_a_models_digest_is_stale",
    ],
    "world_report_is_current": [
        "tests/unit/test_closure_claim_model.py:test_stale_world_report_fails_closure",
        "tests/unit/test_world_mesh.py:test_changed_node_file_makes_the_tree_report_stale",
        "tests/unit/test_world_mesh.py:test_embedded_node_bytes_make_the_tree_report_stale",
        "tests/unit/test_world_mesh.py:test_missing_node_digest_is_stale",
    ],
    "world_scope_limits_are_preserved": [
        "tests/unit/test_world_mesh.py:test_world_scope_limits_remain_nonblocking_and_visible"],
    "wording_within_license": [
        "tests/unit/test_evidence_rules.py:test_withheld_root_claim_needs_a_limit",
        "tests/unit/test_evidence_rules.py:test_limit_anchor_satisfies_the_license",
    ],
}
ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / 'skills/logic-writing/assets/examples'
WORLD_ID = 'old-market-day'  # contract_id of the travel example's world.yaml
PASSING = {'researchguard': 'passed', 'worldguard': 'PASS'}
RESEARCH_PASS = {'research_ready', 'research_contested', 'research_source_only'}
RESEARCH_FAIL = {'research_search_open', 'research_errors', 'research_live_withhold', 'research_alternative_conflict'}
FOREIGN = {'research_foreign', 'world_foreign'}
LICENSE_EXPECTED = {'source_only': 'passed', 'assert': 'passed',
                    'withhold': 'wording_exceeds_license', 'qualify': 'wording_exceeds_license',
                    'withhold_limit': 'passed+risk', 'qualify_limitation': 'passed+risk',
                    'counter': 'passed+risk', 'unrelated': 'passed+risk', 'optional': 'passed+risk'}
WORLD_EXPECTED = {'mesh_bound': 'passed', 'contract_scope': 'passed',
                  'mesh_foreign': 'world_report_mismatch:mesh_id',
                  'mesh_old': 'world_report_unbound:world_mesh+regenerate',
                  'mesh_node_stale': 'world_report_stale:ch2_fixed.yaml',
                  'mesh_embedded_stale': 'world_report_stale:mesh_fixed.yaml',
                  'mesh_digest_omitted': 'world_report_stale:ch2_fixed.yaml'}


@dataclass(frozen=True)
class State:
    owner: str
    independent: bool = True
    report: str = 'not_run'
    closed: bool = False
    copied: str = ''
    broad: bool = False
    named: bool = False
    travel_claim_level: str = 'initial_plan'
    research_risks: tuple[str, ...] = ()
    license_case: str = ''
    license_result: str = ''
    world_case: str = ''
    world_result: str = ''
    world_scope_preserved: bool = False


@dataclass(frozen=True)
class Event:
    kind: str
    status: str = ''


def provider(state):
    return 'researchguard' if state.owner == 'investigation' else 'worldguard'


def expected_status(state):
    if state.report == "not_run":
        return "not_run"
    if provider(state) == "worldguard":
        return (
            state.report
            if state.report in {"PASS", "FAIL"}
            else "failed" if state.report in {"world_foreign", "world_stale"} else "unreadable"
        )
    return (
        "passed"
        if state.report in RESEARCH_PASS
        else (
            "failed"
            if state.report
            in RESEARCH_FAIL | {"research_foreign", "research_stale", "research_digest_omitted"}
            else "unreadable"
        )
    )


def stale_report(state):
    return state.report in (
        {"research_stale", "research_digest_omitted"}
        if provider(state) == "researchguard"
        else {"world_stale"}
    )

def trip_report_status(state):
    # The trip validator reads the saved provider status; closure separately rejects stale inputs.
    return 'PASS' if state.report=='world_stale' else expected_status(state)


def foreign_identity(state):
    """A readable report of another research question or world: closure needs repair."""
    return state.report == {'researchguard': 'research_foreign', 'worldguard': 'world_foreign'}[provider(state)]


def expected_research_risks(state):
    if provider(state) != 'researchguard':
        return ()
    return {'research_contested': ('research:contested',),
            'research_source_only': ('research:root_claim_not_run',),
            'research_foreign': ('research:root_claim_not_run',),
            'research_live_withhold': ('research:wording_boundary',)}.get(state.report, ())


def report_input(owner, case):
    """Finite native input cases, including the source-only shipped verdict shape."""
    if case in {"PASS", "FAIL", "world_foreign", "world_stale"}:
        import hashlib

        world = EXAMPLES / "travel/world.yaml"
        raw = world.read_bytes() + (b"\n" if case == "world_stale" else b"")
        return {
            "status": "PASS" if case in {"world_foreign", "world_stale"} else case,
            "contract_id": "another-world" if case == "world_foreign" else WORLD_ID,
            "input_digests": [{"path": world.name, "sha256": hashlib.sha256(raw).hexdigest()}],
        }, []
    if case not in RESEARCH_PASS | RESEARCH_FAIL | {
        "research_foreign",
        "research_stale",
        "research_digest_omitted",
    }:
        return {}, []
    document = json.loads(
        (EXAMPLES / "investigation/research-status.json").read_text(encoding="utf-8")
    )
    verdict = document["verdict"]
    if case == "research_foreign":
        # Another question's report (the Ever Given probe): same verdict shape, other identity.
        document["question"] = "Why did container freight rates surge in 2021?"
        document["hypotheses"] = [{"id": "h_suez", "text": "The Suez blockage caused the surge."}]
        verdict["live_hypotheses"] = ["h_suez"]
        import yaml, hashlib

        index = yaml.safe_load((EXAMPLES / "investigation/research/research.yaml").read_text())
        index.update(question=document["question"], hypotheses=document["hypotheses"])
        for row in document["input_digests"]:
            if row["path"] == "research.yaml":
                row["sha256"] = hashlib.sha256(
                    yaml.safe_dump(index, sort_keys=False).encode()
                ).hexdigest()
        return document, []
    verdict = document["verdict"]
    if case != "research_source_only":
        verdict["root_claim"] = {
            "id": "h-main-answer",
            "wording_license": "assert",
            "reason": "Native argument support is sufficient within scope.",
        }
    if case == "research_contested":
        verdict["contested"] = True
    elif case == "research_search_open":
        verdict["search"] = "continue_search"
    elif case == "research_errors":
        verdict["errors"] = 1
    elif case == "research_live_withhold":
        verdict["root_claim"].update(
            wording_license="withhold", reason="Native counterevidence remains."
        )
        verdict["live_hypotheses"].append("h-other")
    elif case == "research_alternative_conflict":
        # The report keeps the folder's identity; the brief calls a live hypothesis rejected.
        return document, (
            [
                {
                    "alternative_id": "h-main-answer",
                    "safe_meaning": "A live hypothesis is called rejected.",
                    "status": "rejected",
                    "content_unit_ids": ["content:answer"],
                }
            ]
            if owner == "investigation"
            else []
        )
    if case == "research_digest_omitted":
        document["input_digests"] = [
            row for row in document["input_digests"] if row["path"] != "source.yaml"
        ]
    if case == "research_stale":
        import hashlib

        for row in document["input_digests"]:
            if row["path"] == "source.yaml":
                row["sha256"] = hashlib.sha256(
                    (EXAMPLES / "investigation/research/source.yaml").read_bytes() + b"\n"
                ).hexdigest()
    return document, []


class Step:
    name = 'Step'
    reads = ('owner', 'independent', 'report')
    writes = ('report', 'closed', 'copied', 'broad', 'named', 'travel_claim_level', 'research_risks', 'license_case', 'license_result', 'world_case', 'world_result', 'world_scope_preserved')
    ignore, rewrite, omit = False, False, False

    def license_result(self, case):
        return LICENSE_EXPECTED[case]

    def apply(self, event, state):
        if event.kind == 'world':
            result = WORLD_EXPECTED[event.status]
            return (FunctionResult(result, replace(state, world_case=event.status, world_result=result,
                                                   world_scope_preserved=event.status in {'mesh_bound', 'contract_scope'}),
                                   label='world_' + event.status),)
        if event.kind == 'license':
            result = self.license_result(event.status)
            return (FunctionResult(result, replace(state, license_case=event.status, license_result=result),
                                   label='license_' + event.status),)
        if event.kind == 'report':
            return (FunctionResult('saved', replace(state, report=event.status, closed=False,
                                                   copied='', broad=False, named=False, travel_claim_level='initial_plan', research_risks=()), label='saved'),)
        current_status = expected_status(state)
        passing = current_status == PASSING[provider(state)]
        result = replace(state, closed=True, copied=PASSING[provider(state)] if self.rewrite else current_status,
                         broad=state.independent and (passing or self.ignore),
                         named=not passing and not self.omit,
                         travel_claim_level='bookable' if state.owner == 'travel-guide' and trip_report_status(state)=='PASS' else 'initial_plan',
                         research_risks=expected_research_risks(state))
        case_label = 'foreign_report' if (state.owner == 'travel-guide' and state.report in RESEARCH_PASS | RESEARCH_FAIL | {'research_foreign'}) or (state.owner == 'investigation' and state.report in {'PASS', 'FAIL', 'world_foreign'}) else state.report
        output = 'needs_repair' if foreign_identity(state) or stale_report(state) else 'passed'
        return (FunctionResult(output, result, label=f'closed:{state.owner}:{case_label}'),)


class IgnoreReports(Step):
    ignore = True


class RewriteFailure(Step):
    rewrite = True


class OmitRisk(Step):
    omit = True


def broad_needs_reports(state, trace):
    if state.broad and (not state.independent or expected_status(state) != PASSING[provider(state)]):
        return InvariantResult.fail('broad claim without a passing required report and independent read')
    return InvariantResult.pass_()


def status_copied(state, trace):
    if state.closed and state.copied != expected_status(state):
        return InvariantResult.fail('native status was rewritten')
    return InvariantResult.pass_()


def failure_named(state, trace):
    if state.closed and expected_status(state) != PASSING[provider(state)] and not state.named:
        return InvariantResult.fail('missing or failed provider is absent from residual risk')
    return InvariantResult.pass_()


class TravelReadsHandwrittenWorldStatus(Step):
    """Known bad: a travel declaration overwrites a failing saved report."""
    def apply(self, event, state):
        results = super().apply(event, state)
        if event.kind == 'close' and state.owner == 'travel-guide':
            return tuple(replace(result, new_state=replace(result.new_state,
                copied='PASS', travel_claim_level='bookable', broad=state.independent)) for result in results)
        return results


def travel_world_failure_limits_claim(state, trace):
    if state.owner == 'travel-guide' and state.closed and trip_report_status(state) != 'PASS' and state.travel_claim_level != 'initial_plan':
        return InvariantResult.fail('a non-pass saved world report permits only initial planning')
    return InvariantResult.pass_()


class ReadsMemberReports(Step):
    """Known bad: green member results replace the research tree verdict."""
    def apply(self, event, state):
        results = super().apply(event, state)
        if event.kind == 'close' and provider(state) == 'researchguard':
            return tuple(replace(result, new_state=replace(result.new_state,
                copied='passed', broad=state.independent, named=False)) for result in results)
        return results


class DropsResearchRisks(Step):
    """Known bad: discard the research disagreement or wording boundary."""
    def apply(self, event, state):
        results = super().apply(event, state)
        if event.kind == 'close' and provider(state) == 'researchguard':
            return tuple(replace(result, new_state=replace(result.new_state,
                research_risks=())) for result in results)
        return results


def research_verdict_risks_are_preserved(state, trace):
    if state.closed and state.research_risks != expected_research_risks(state):
        return InvariantResult.fail('contested or non-assert research wording risk was lost')
    if state.closed and state.report == 'research_contested' and provider(state) == 'researchguard' and state.broad != state.independent:
        return InvariantResult.fail('contested was turned into a research gate')
    if state.closed and state.report == 'research_source_only' and provider(state) == 'researchguard' and state.broad != state.independent:
        return InvariantResult.fail('source-only sufficiency was incorrectly treated as a missing assert gate')
    return InvariantResult.pass_()


class ForeignResearchReportPasses(Step):
    """Known bad: a passing report of another research question passes closure."""
    def apply(self, event, state):
        results = super().apply(event, state)
        if event.kind == 'close' and provider(state) == 'researchguard' and state.report == 'research_foreign':
            return tuple(replace(result, new_state=replace(result.new_state, copied='passed',
                broad=state.independent, named=False)) for result in results)
        return results


class ForeignWorldReportPasses(Step):
    """Known bad: a passing report of another world passes closure."""
    def apply(self, event, state):
        results = super().apply(event, state)
        if event.kind == 'close' and provider(state) == 'worldguard' and state.report == 'world_foreign':
            return tuple(replace(result, new_state=replace(result.new_state, copied='PASS',
                broad=state.independent, named=False, travel_claim_level='bookable')) for result in results)
        return results


def research_report_belongs_to_the_folder(state, trace):
    if state.closed and provider(state) == 'researchguard' and state.report == 'research_foreign' and (state.copied != 'failed' or not state.named):
        return InvariantResult.fail('a research report of another question was counted for this folder')
    return InvariantResult.pass_()


def world_report_belongs_to_the_contract(state, trace):
    if state.world_case in {'mesh_bound', 'contract_scope', 'mesh_foreign', 'mesh_old'} and state.world_result != WORLD_EXPECTED[state.world_case]:
        return InvariantResult.fail('a tree report must bind by mesh_id; an old report needs the native regeneration command')
    if state.closed and provider(state) == 'worldguard' and state.report == 'world_foreign' and (state.copied != 'failed' or not state.named):
        return InvariantResult.fail('a world report of another contract was counted for this world')
    return InvariantResult.pass_()


def research_report_is_current(state, trace):
    if (
        state.closed
        and provider(state) == "researchguard"
        and stale_report(state)
        and (state.copied != "failed" or state.broad or not state.named)
    ):
        return InvariantResult.fail("stale research report licensed closure")
    return InvariantResult.pass_()

def world_report_is_current(state,trace):
    if state.world_case in {'mesh_node_stale', 'mesh_embedded_stale', 'mesh_digest_omitted'} and state.world_result != WORLD_EXPECTED[state.world_case]:
        return InvariantResult.fail('tree bytes and every file node must be covered by current raw input digests')
    if state.closed and provider(state)=='worldguard' and state.report=='world_stale' and (state.copied!='failed' or state.broad or not state.named):
        return InvariantResult.fail('stale world report licensed closure')
    return InvariantResult.pass_()

class StaleResearchReportPasses(Step):
    def apply(self,event,state):
        rows=super().apply(event,state)
        if event.kind=='close' and provider(state)=='researchguard' and state.report=='research_stale':
            return tuple(replace(row,output='passed',new_state=replace(row.new_state,copied='passed',broad=state.independent,named=False)) for row in rows)
        return rows

class StaleWorldReportPasses(Step):
    def apply(self,event,state):
        rows=super().apply(event,state)
        if event.kind=='close' and provider(state)=='worldguard' and state.report=='world_stale':
            return tuple(replace(row,output='passed',new_state=replace(row.new_state,copied='PASS',broad=state.independent,named=False)) for row in rows)
        return rows

def wording_within_license(state, trace):
    if state.license_case and state.license_result != LICENSE_EXPECTED[state.license_case]:
        return InvariantResult.fail('only required units citing support for the withheld or qualified root need a limit; other claims and rebuttals stay outside that license')
    return InvariantResult.pass_()


class WithheldClaimStatedPlainly(Step):
    def license_result(self, case):
        return 'passed+risk' if case == 'withhold' else super().license_result(case)


def world_scope_limits_are_preserved(state, trace):
    if state.world_case in {'mesh_bound', 'contract_scope'} and not state.world_scope_preserved:
        return InvariantResult.fail('actual WorldGuard scope limits must remain visible, with owner and report path, without blocking PASS')
    return InvariantResult.pass_()


class DropsWorldScope(Step):
    def apply(self, event, state):
        rows = super().apply(event, state)
        if event.kind == 'world':
            return tuple(replace(row, new_state=replace(row.new_state, world_scope_preserved=False)) for row in rows)
        return rows


INVARIANTS = (
    Invariant('world_scope_limits_are_preserved', 'actual provider scope limits remain nonblocking, attributed risks and a summary count', world_scope_limits_are_preserved),
    Invariant('research_report_is_current','research inputs match the saved report',research_report_is_current),
    Invariant('world_report_is_current','world inputs match the saved report',world_report_is_current),
    Invariant('research_report_belongs_to_the_folder', 'a research report counts only for its own research folder', research_report_belongs_to_the_folder),
    Invariant('world_report_belongs_to_the_contract', 'a world report counts only for its own world contract', world_report_belongs_to_the_contract),
    Invariant('research_verdict_risks_are_preserved', 'disagreement and wording boundaries remain honest', research_verdict_risks_are_preserved),
    Invariant("travel_world_failure_limits_claim", "travel reads saved world status", travel_world_failure_limits_claim),
    Invariant('broad_claim_needs_every_required_provider', 'every required report passes', broad_needs_reports),
    Invariant('provider_status_is_copied_unchanged', 'native status remains unchanged', status_copied),
    Invariant('missing_or_failed_provider_is_named', 'all missing or failing providers are named', failure_named),
    Invariant('wording_within_license',
              'when the saved report withholds or qualifies the root claim, a required unit citing an anchor that supports it also carries a limit',
              wording_within_license),
)
EVENTS = (tuple(Event('report', status) for status in (*sorted(RESEARCH_PASS | RESEARCH_FAIL), 'research_foreign', 'PASS', 'FAIL', 'world_foreign', 'unreadable', 'research_stale', 'research_digest_omitted', 'world_stale')) + (Event('close'),)
          + tuple(Event('license', case) for case in LICENSE_EXPECTED)
          + tuple(Event('world', case) for case in WORLD_EXPECTED))


def terminal(event, state, trace):
    if state.license_case or state.world_case:
        return True
    return (event.kind in {'license', 'world'} and
            (state.owner != 'investigation' or state.independent or state.report != 'not_run' or state.closed))


def explorer(step):
    return Explorer(workflow=Workflow((step,)),
                    initial_states=tuple(State(owner, independent) for owner in ('investigation', 'travel-guide')
                                         for independent in (True, False)),
                    external_inputs=EVENTS, invariants=INVARIANTS, max_sequence_length=2,
                    terminal_predicate=terminal, progress_steps=0)


def build_explorer():
    return explorer(Step())


def broken_variants():
    return {'world_scope_limits_disappear': explorer(DropsWorldScope()),
            'stale_research_report_passes':explorer(StaleResearchReportPasses()),
            'stale_world_report_passes':explorer(StaleWorldReportPasses()),
            'drops_research_risks': explorer(DropsResearchRisks()),
            'closure_reads_member_reports': explorer(ReadsMemberReports()),
            'travel_reads_handwritten_world_status': explorer(TravelReadsHandwrittenWorldStatus()),
            'closure_ignores_provider_reports': explorer(IgnoreReports()),
            'failed_report_read_as_pass': explorer(RewriteFailure()),
            'missing_provider_not_named': explorer(OmitRisk()),
            'foreign_research_report_passes': explorer(ForeignResearchReportPasses()),
            'foreign_world_report_passes': explorer(ForeignWorldReportPasses()),
            'withheld_claim_stated_plainly': explorer(WithheldClaimStatedPlainly())}


class Native:
    """Replay current closure and trip validators; reuse immutable protocol fixtures."""
    def _world_probe(self, case):
        from derive_closure import provider_checks
        from show_plan import _summary
        with tempfile.TemporaryDirectory(prefix='lw-world-mesh-model-') as temporary:
            folder = Path(temporary)
            if case == 'contract_scope':
                path = EXAMPLES / 'fiction/worldguard-check.json'
                route = {'world_contract': str(EXAMPLES / 'fiction/world.yaml'), 'world_check_required': True}
                document = json.loads(path.read_text())
            else:
                source = ROOT / 'tests/fixtures/consumers/worldguard_tree'
                for name in ('mesh_fixed.yaml', 'ch1_fixed.yaml', 'ch2_fixed.yaml'):
                    shutil.copyfile(source / name, folder / name)
                path = folder / 'mesh-report.json'
                document = json.loads((source / 'mesh-report.json').read_text())
                route = {'world_mesh': str(folder / 'mesh_fixed.yaml'), 'world_check_required': True}
                if case == 'mesh_foreign':
                    document['mesh_id'] = 'another-tree'
                elif case == 'mesh_old':
                    document.pop('mesh_id')
                elif case == 'mesh_digest_omitted':
                    document['input_digests'] = [row for row in document['input_digests'] if row['path'] != 'ch2_fixed.yaml']
                elif case in {'mesh_node_stale', 'mesh_embedded_stale'}:
                    changed = folder / ('ch2_fixed.yaml' if case == 'mesh_node_stale' else 'mesh_fixed.yaml')
                    raw = changed.read_bytes()
                    changed.write_bytes(raw + b'\n' if case == 'mesh_node_stale' else raw.replace(b'door_unlocked', b'door_locked', 1))
                path.write_text(json.dumps(document))
            rows, risks, passed = provider_checks('fiction-writing', {}, route, [{'provider': 'worldguard', 'path': str(path)}])
            reason = rows[0]['reason']
            result = 'passed' if passed and rows[0]['passed'] and rows[0]['status'] == 'PASS' else reason.split(' (', 1)[0]
            if case == 'mesh_old' and result == 'world_report_unbound:world_mesh' and 'worldguard mesh-check --mesh' in reason:
                result += '+regenerate'
            scope_rows = [row for row in risks if row['defect_id'].startswith('world:scope_limit:')]
            scopes = document.get('scope_limits', [])
            preserved = (passed and len(scope_rows) == len(scopes) and bool(scopes)
                         and all(row['owner'] == 'fiction-writing' and row['reason'] == f'WorldGuard report {path}: {scope}'
                                 for row, scope in zip(scope_rows, scopes)))
            summary = _summary({'planned_units': []}, {'audit': {'status': 'passed'}, 'review': {'status': 'passed'},
                                                     'closure': {'status': 'passed', 'residual_risk': risks}})
            return result, preserved and f'WorldGuard scope limits: {len(scopes)}' in summary

    def _license_probe(self, case):
        from run_chain import run_chain
        with tempfile.TemporaryDirectory(prefix='lw-license-model-') as temporary:
            folder = Path(temporary) / 'investigation'
            shutil.copytree(EXAMPLES / 'investigation', folder)
            report_path = folder / 'research-status.json'
            report = json.loads(report_path.read_text())
            if case != 'source_only':
                license = 'assert' if case == 'assert' else 'qualify' if case in ('qualify', 'qualify_limitation') else 'withhold'
                report['verdict']['root_claim'] = {'id': 'h-main-answer', 'wording_license': license,
                                                   'reason': 'The root claim remains bounded by its counterevidence.'}
                anchor = next(row for row in report['evidence'] if row['anchor'] == 'anc-314-supported')
                anchor['directions'] = [{'route': 'logic', 'hypothesis': 'h-other' if case == 'unrelated' else 'h-main-answer',
                                         'direction': 'oppose' if case == 'counter' else 'support', 'node': 'E_supported'}]
            report_path.write_text(json.dumps(report))
            path = folder / 'brief-request.json'
            request = json.loads(path.read_text())
            boundaries = request['content_boundaries']
            unit = next(row for row in boundaries['content_units'] if row['content_unit_id'] == 'cu-status-314')
            if case == 'withhold_limit':
                unit['evidence_anchor_ids'].append('anc-314-phase3-undecided')
            elif case == 'qualify_limitation':
                unit['limitation_ids'] = ['lim-scope']
            elif case == 'optional':
                unit['required'] = False
            elif case == 'counter':
                next(row for row in boundaries['evidence_anchors'] if row['anchor_id'] == 'anc-314-supported')['relation'] = 'counter'
                unit['evidence_anchor_ids'].append('anc-313-experimental')
                unit['safe_meaning'] = 'The evidence does not support the claim that free-threading is already the default.'
            path.write_text(json.dumps(request))
            result = run_chain(folder)
            if result['exit_code']:
                return result['first_failure']['code']
            closure = result['results']['closure']['closure']
            if case in ('source_only', 'assert'):
                return closure['status']
            risk = any(row.get('defect_id') == 'research:wording_boundary'
                       and row.get('owner') == 'investigation' for row in closure['residual_risk'])
            return 'passed+risk' if closure['status'] == 'passed' and risk else 'missing-risk'

    def reset(self, state):
        self.state = state
        self._fixture([])

    def _fixture(self, alternatives):
        from copy import deepcopy
        from unittest.mock import patch
        for path in (ROOT, ROOT / 'skills/logic-writing/scripts'):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        from tests import v2_support as fixtures
        from derive_closure import derive_closure
        from _common import fingerprint
        state = self.state
        key = (state.owner, state.independent, bool(alternatives))
        if not hasattr(self, 'cache'):
            self.cache = {}
        if key not in self.cache:
            root = Path(tempfile.mkdtemp(prefix='lw-provider-model-'))
            native_build = fixtures.build_reader_brief
            def build_with_inputs(**kwargs):
                # Change the input before native fingerprinting; no production check is mocked.
                kwargs['content_boundaries'] = deepcopy(kwargs['content_boundaries'])
                kwargs['content_boundaries']['alternatives'] = deepcopy(alternatives)
                return native_build(**kwargs)
            with patch.object(fixtures, 'build_reader_brief', build_with_inputs):
                request = fixtures.closure_input(fixtures.complete_chain(root, state.owner))
            request['provider_reports'] = []
            if not state.independent:
                judgment = request['judgment']
                judgment['judge_kind'] = 'self_review'
                judgment.pop('judgment_fingerprint')
                judgment['judgment_fingerprint'] = fingerprint(judgment)
            self.cache[key] = (root, request)
        self.root, request = self.cache[key]
        self.request = deepcopy(request)
        self.derive = derive_closure
        if state.owner == 'travel-guide':
            travel = ROOT / 'skills/logic-writing/routes/travel'
            if str(travel / 'scripts') not in sys.path:
                sys.path.insert(0, str(travel / 'scripts'))
            from fixture_mutation import apply_mutations
            from travel_contract import review_plan
            self.trip_path = travel / 'examples/good_city_couple_trip/plan.json'
            base = json.loads(self.trip_path.read_text(encoding="utf-8"))
            current = json.loads((travel / 'examples/positive_cases/near_future_bookable.json').read_text(encoding="utf-8"))
            self.trip = apply_mutations(base, current['mutations'])
            self.trip['world_feasibility']['checks'][0]['worldguard_report'] = str(self.root / 'unavailable-world.json')
            self.review_trip = review_plan

    def apply_step(self, step):
        event, state = step.function_input, self.state
        if event.kind == 'world':
            result, preserved = self._world_probe(event.status)
            self.state = replace(state, world_case=event.status, world_result=result,
                                 world_scope_preserved=preserved if event.status in {'mesh_bound', 'contract_scope'} else False)
            return ReplayObservation(function_name=step.function_name, observed_output=result, observed_state=self.state)
        if event.kind == 'license':
            result = self._license_probe(event.status)
            state = replace(state, license_case=event.status, license_result=result)
            self.state = state
            return ReplayObservation(function_name=step.function_name, observed_output=result, observed_state=state)
        if event.kind == 'report':
            document, alternatives = report_input(state.owner, event.status)
            self._fixture(alternatives)
            path = self.root / 'native.json'
            path.write_text('{}' if event.status == 'unreadable' else json.dumps(document), encoding='utf-8')
            self.request['provider_reports'] = [{'provider': provider(state), 'path': str(path)}]
            if state.owner == 'travel-guide' and event.status != 'world_foreign':
                # A trip plan citing another world's report is rejected when the brief is built.
                self.trip['world_feasibility']['checks'][0]['worldguard_report'] = str(path)
            state = replace(state, report=event.status, closed=False, copied='', broad=False,
                            named=False, travel_claim_level='initial_plan', research_risks=())
            output = 'saved'
        else:
            closure = self.derive(self.request)['closure']
            row = closure['provider_checks'][0]
            state = replace(state, closed=True, copied=row['status'], broad=closure['broad_claim_allowed'],
                named=any(r['defect_id'] == f'provider:{provider(state)}' for r in closure['residual_risk']),
                research_risks=tuple(sorted(r['defect_id'] for r in closure['residual_risk'] if r['defect_id'].startswith('research:'))),
                travel_claim_level=self.review_trip(self.trip, plan_path=self.trip_path)['allowed_claim_level'] if state.owner == 'travel-guide' else 'initial_plan')
            output = closure['status']
        self.state = state
        return ReplayObservation(function_name=step.function_name, observed_output=output, observed_state=state)

    def observe_state(self):
        return self.state

    def observe_output(self):
        return None

    def close(self):
        for root, _ in getattr(self, 'cache', {}).values():
            shutil.rmtree(root, ignore_errors=True)


def conformance():
    result, adapter = None, Native()
    try:
        traces = build_explorer().explore().traces
        old = [trace for trace in traces if not any(event.kind in {'license', 'world'} for event in trace.external_inputs)]
        probes = [trace for trace in traces if len(trace.external_inputs) == len(trace.steps) == 1
                  and trace.steps[0].function_input.kind in {'license', 'world'}]
        for trace in (*select_covering_traces(old), *probes):
            result = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                  rules=(projected_state_matches(), projected_output_matches()))
            if not result.ok:
                return result
        facts = CodeFacts(ROOT)
        facts.unreferenced("skills/logic-writing/scripts/researchguard_handoff.py:build_researchguard_handoff")
        facts.check("native provider replay conforms", result.ok, result.format_text())
        return facts.report()
    finally:
        adapter.close()

USES = {
    'WorldScopeSummary': 'skills/logic-writing/scripts/show_plan.py:_summary',
    'LicenseProbe': 'skills/logic-writing/scripts/run_chain.py:run_chain',
    'Close': 'skills/logic-writing/scripts/derive_closure.py:derive_closure',
    'WorldIdentity': 'skills/logic-writing/scripts/_common.py:worldguard_report_identity_problems',
    'InputDigests': 'skills/logic-writing/scripts/_common.py:input_digest_problems',
    'TravelClaims': 'skills/logic-writing/routes/travel/scripts/travel_contract.py:review_plan',
    'ApplyMutations': 'skills/logic-writing/routes/travel/scripts/fixture_mutation.py:apply_mutations',
}

NOT_MODELED = {'skills/logic-writing/scripts/derive_closure.py:main': 'Command wrapper: reads the closure request file, calls derive_closure (bound as Close in USES) and writes the closure JSON.'}
