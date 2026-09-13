"""Focused tests for the isolated reader-projection owner runner.

The command under test is executed against an explicitly supplied formal
checkout and the isolated adapter candidate.  The environment variables keep
those locations outside the portable source file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest


RUNNER = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "run_reader_projection_conformance.py"
)


def _paths() -> tuple[Path, Path]:
    checkout = Path(__file__).resolve().parents[2]
    if (
        (checkout / "skills" / "logic-writing" / "scripts").is_dir()
        and (checkout / "scripts" / "run_reader_projection_conformance.py").is_file()
    ):
        formal = checkout
        candidate = formal / "skills" / "logic-writing" / "scripts"
    else:
        formal_value = os.environ.get("LW_FORMAL_CHECKOUT")
        candidate_value = os.environ.get("LW_ADAPTER_CANDIDATE")
        if not formal_value or not candidate_value:
            pytest.fail(
                "set LW_FORMAL_CHECKOUT and LW_ADAPTER_CANDIDATE "
                "for isolated draft owner tests"
            )
        formal = Path(formal_value).resolve()
        candidate = Path(candidate_value).resolve()
    assert (formal / "skills" / "logic-writing" / "scripts").is_dir()
    assert (candidate / "reader_projection_conformance.py").is_file()
    return formal, candidate


def _run() -> tuple[subprocess.CompletedProcess[str], dict]:
    formal, candidate = _paths()
    environment = os.environ.copy()
    scripts = formal / "skills" / "logic-writing" / "scripts"
    environment["PYTHONPATH"] = ";".join((str(candidate), str(formal), str(scripts)))
    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--root",
            str(formal),
            "--json",
        ],
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=environment,
        check=False,
    )
    return completed, json.loads(completed.stdout)


def test_owner_round_trip_is_a_bounded_reader_projection_result():
    completed, payload = _run()
    assert completed.returncode == 0, completed.stderr
    assert payload["status"] == "passed"
    assert payload["ok"] is True
    assert payload["production_conformance"] is True
    assert payload["claim"] == "production_reader_conformance"
    assert payload["claim_boundary"] == "reader-projection.v1"
    assert payload["observation_boundary_id"] == "reader-projection.v1"
    assert payload["owner_id"] == "logic-writing.reader-projection.v1"
    assert payload["evidence_mode"] == "protocol_only"
    assert payload["provider_status"] == "not_run"
    assert payload["quality_claim_status"] == "not_claimed"
    assert payload["quality_evidence"] is False
    assert payload["real_provider_executed"] is False
    assert payload["expected_trace"] is None
    assert payload["source_identity"]


def test_owner_output_contains_no_private_trace_or_machine_path():
    completed, payload = _run()
    assert completed.returncode == 0, completed.stderr
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert payload["expected_trace"] is None
    assert not re.search(r"[A-Za-z]:[\\/]", serialized)
    assert "LOGIC_WRITING_" + "ROOT" not in serialized
    assert "FlowGuard_" + "20260427" not in serialized
