from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint
from tests.v2_support import derive_protocol_closure as derive_closure
from tests.v2_support import closure_input, complete_chain


@pytest.mark.parametrize(
    "owner",
    ["investigation", "academic-writing", "fiction-writing", "travel-guide"],
)
def test_complete_current_chain_closes(owner, tmp_path, monkeypatch):
    import derive_closure as closure_module
    import reader_pipeline
    from pathlib import Path
    chain = complete_chain(tmp_path, owner)
    request = closure_input(chain)
    original_map = reader_pipeline.validate_artifact_map
    original_audit = reader_pipeline._build_reader_audit_from_current
    calls = {"map": 0, "audit": 0}
    def mapped(value):
        calls["map"] += 1
        return original_map(value)
    def audited(**kwargs):
        calls["audit"] += 1
        return original_audit(**kwargs)
    monkeypatch.setattr(closure_module, "validate_artifact_map", mapped)
    monkeypatch.setattr(reader_pipeline, "validate_artifact_map", mapped)
    monkeypatch.setattr(closure_module, "_build_reader_audit_from_current", audited)
    monkeypatch.setattr(reader_pipeline, "_build_reader_audit_from_current", audited)
    result = derive_closure(request)
    assert calls == {"map": 1, "audit": 1}
    def changed_during_audit(**kwargs):
        report = original_audit(**kwargs)
        artifact = Path(chain["artifact_map"]["artifact_path"])
        artifact.write_bytes(artifact.read_bytes() + b"changed")
        return report
    monkeypatch.setattr(closure_module, "_build_reader_audit_from_current", changed_during_audit)
    with pytest.raises(ValidationError, match="stale during closure"):
        derive_closure(request)
    assert result["closure"]["status"] == "passed"
    assert result["closure"]["broad_claim_allowed"] is True


def test_quality_failure_needs_repair(tmp_path):
    result = derive_closure(closure_input(complete_chain(tmp_path, pass_quality=False)))
    assert result["closure"]["status"] == "needs_repair"
    assert result["closure"]["next_actions"] == [{"owner": "investigation", "action": "repair_and_rerun"}]


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

    from reader_pipeline import fill_closure_fingerprints

    filled = fill_closure_fingerprints(json.loads(path.read_text(encoding="utf-8")))
    assert filled["judgment"]["judgment_fingerprint"] == fingerprint_without(filled["judgment"], "judgment_fingerprint")
    assert closure["judgment_fingerprint"] == filled["judgment"]["judgment_fingerprint"]
