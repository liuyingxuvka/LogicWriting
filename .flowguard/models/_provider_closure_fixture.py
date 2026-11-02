"""Saved provider report cases and the native closure request shared by the provider closure models.

closure_claim_model judges research reports and the copied provider status; world_report_model judges
WorldGuard reports and the travel claim. Both replay derive_closure over these finite report cases.
No model state, rule or verdict lives here.
"""
from dataclasses import dataclass
from pathlib import Path
import json
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / 'skills/logic-writing/assets/examples'
WORLD_ID = 'old-market-day'  # contract_id of the travel example's world.yaml
PASSING = {'researchguard': 'passed', 'worldguard': 'PASS'}
RESEARCH_PASS = {'research_ready', 'research_contested', 'research_source_only'}
RESEARCH_FAIL = {'research_search_open', 'research_errors', 'research_live_withhold', 'research_alternative_conflict'}
REPORT_CASES = (*sorted(RESEARCH_PASS | RESEARCH_FAIL), 'research_foreign', 'PASS', 'FAIL', 'world_foreign',
                'unreadable', 'research_stale', 'research_digest_omitted', 'world_stale')


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


def foreign_identity(state):
    """A readable report of another research question or world: closure needs repair."""
    return state.report == {'researchguard': 'research_foreign', 'worldguard': 'world_foreign'}[provider(state)]


def close_label(state):
    case = ('foreign_report' if (state.owner == 'travel-guide' and state.report in RESEARCH_PASS | RESEARCH_FAIL | {'research_foreign'})
            or (state.owner == 'investigation' and state.report in {'PASS', 'FAIL', 'world_foreign'}) else state.report)
    return f'closed:{state.owner}:{case}'


def close_output(state):
    return 'needs_repair' if foreign_identity(state) or stale_report(state) else 'passed'


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


def plain_json(value):
    """The JSON text of a fixture that is plain JSON; each replay step reads a fresh copy of it."""
    text = json.dumps(value)
    if json.loads(text) != value:
        raise ValueError('a replay fixture is not plain JSON, so its text is not an exact copy')
    return text


class NativeClosure:
    """The native closure request per owner and independence, built once through the tests' protocol builders."""

    def __init__(self):
        self.cache = {}

    def request(self, owner, independent, alternatives):
        from copy import deepcopy
        from unittest.mock import patch
        for path in (ROOT, ROOT / 'skills/logic-writing/scripts'):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        from tests import v2_support as fixtures
        from _common import fill_fingerprint
        key = (owner, independent, bool(alternatives))
        if key not in self.cache:
            root = Path(tempfile.mkdtemp(prefix='lw-provider-model-'))
            native_build = fixtures.build_reader_brief
            def build_with_inputs(**kwargs):
                # Change the input before native fingerprinting; no production check is mocked.
                kwargs['content_boundaries'] = deepcopy(kwargs['content_boundaries'])
                kwargs['content_boundaries']['alternatives'] = deepcopy(alternatives)
                return native_build(**kwargs)
            with patch.object(fixtures, 'build_reader_brief', build_with_inputs):
                request = fixtures.closure_input(fixtures.complete_chain(root, owner))
            request['provider_reports'] = []
            if not independent:
                judgment = request['judgment']
                judgment['judge_kind'] = 'self_review'
                judgment.pop('judgment_fingerprint')
                fill_fingerprint(judgment, 'judgment_fingerprint')
            self.cache[key] = (root, plain_json(request))
        root, text = self.cache[key]
        return root, json.loads(text)

    def save(self, state, case):
        """Write one report case as the only saved provider report of a fresh request."""
        document, alternatives = report_input(state.owner, case)
        root, request = self.request(state.owner, state.independent, alternatives)
        path = root / 'native.json'
        path.write_text('{}' if case == 'unreadable' else json.dumps(document), encoding='utf-8')
        request['provider_reports'] = [{'provider': provider(state), 'path': str(path)}]
        return root, request, path

    def derive(self, request):
        from derive_closure import derive_closure
        return derive_closure(request)['closure']

    def close(self):
        for root, _ in self.cache.values():
            shutil.rmtree(root, ignore_errors=True)
