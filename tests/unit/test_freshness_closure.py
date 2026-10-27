from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from _common import ValidationError, fingerprint
from tests.v2_support import derive_protocol_closure as derive_closure
from tests.v2_support import closure_input, complete_chain






def test_cli_exits_nonzero_unless_closure_passed(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path
    script = Path(__file__).resolve().parents[2] / "skills" / "logic-writing" / "scripts" / "derive_closure.py"
    for pass_quality, expected in ((True, 0), (False, 1)):
        workdir = tmp_path / ("pass" if pass_quality else "fail")
        workdir.mkdir()
        request = workdir / "closure-input.json"
        request.write_text(json.dumps(closure_input(complete_chain(workdir, pass_quality=pass_quality))), encoding="utf-8")
        run = subprocess.run([sys.executable, str(script), "--input", str(request)], capture_output=True, text=True)
        assert run.returncode == expected, run.stdout + run.stderr
        payload = json.loads(run.stdout)
        assert payload["status"] == payload["closure"]["status"]
        assert payload["errors"] == payload["warnings"] == []
    output = tmp_path / "blocked.json"
    request.write_text(json.dumps({"artifact_map": "missing-map.json"}))
    run = subprocess.run([sys.executable, str(script), "--input", str(request), "--output", str(output)], capture_output=True, text=True)
    assert run.returncode == 2
    payload = json.loads(output.read_text())
    assert payload["status"] == "blocked" and len(payload["errors"]) == 1 and payload["warnings"] == []


def test_repeating_closure_does_not_count_as_repair(tmp_path):
    request = closure_input(complete_chain(tmp_path, pass_quality=False))
    first = derive_closure(request)
    second = derive_closure(request)
    assert first["closure"]["status"] == second["closure"]["status"] == "needs_repair"


def test_foreign_reader_intent_is_rejected(tmp_path):
    request = closure_input(complete_chain(tmp_path))
    request["reader_brief"] = copy.deepcopy(request["reader_brief"])
    request["reader_brief"]["reader_intent_fingerprint"] = fingerprint({"foreign": True})
    with pytest.raises(ValidationError):
        derive_closure(request)


def test_closure_command_fills_judgment_and_provenance_fingerprints(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    from _common import fingerprint_without

    request = closure_input(complete_chain(tmp_path))
    judgment = request["judgment"]
    for field in [key for key in judgment if key.endswith("_fingerprint")]:
        del judgment[field]
    for row in [*judgment["reverse_outline"], *judgment["defects"], *judgment["strengths"]]:
        row["evidence"].pop("locator", None)
        row["evidence"].pop("excerpt_fingerprint", None)
    provenance = request["revision_provenance"]
    for field in ("reader_intent_fingerprint", "target_artifact_fingerprint", "provenance_fingerprint"):
        del provenance[field]
    path = tmp_path / "closure-input.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    script = Path(__file__).resolve().parents[2] / "skills" / "logic-writing" / "scripts" / "derive_closure.py"
    run = subprocess.run([sys.executable, str(script), "--input", str(path)], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    closure = json.loads(run.stdout)["closure"]
    assert closure["status"] == "passed"
    assert closure["revision_provenance_fingerprint"].startswith("sha256:")

    from reader_fill import fill_closure_fingerprints

    filled = fill_closure_fingerprints(json.loads(path.read_text(encoding="utf-8")))
    assert filled["judgment"]["judgment_fingerprint"] == fingerprint_without(filled["judgment"], "judgment_fingerprint")
    assert closure["judgment_fingerprint"] == filled["judgment"]["judgment_fingerprint"]












def test_required_providers_follow_live_alternatives_and_fiction_opt_in():
    from derive_closure import required_providers
    live = {'content_boundaries': {'alternatives': [{'status': 'live'}]}}
    assert required_providers('investigation', live, {}) == {'researchguard'}
    assert required_providers('academic-writing', live, {}) == {'researchguard'}
    assert not required_providers('academic-writing', {}, {})
    assert required_providers('academic-writing', {'research_folder': 'native-question'}, {}) == {'researchguard'}
    assert required_providers('fiction-writing', {}, {'world_check_required': True}) == {'worldguard'}
    assert not required_providers('fiction-writing', {}, {})
    assert required_providers('travel-guide', {}, {}) == {'worldguard'}




