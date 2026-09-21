from __future__ import annotations

import subprocess
import sys
import os
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def _author_environment() -> dict[str, str]:
    """Expose a local provider source only to author-side checks."""
    environment = os.environ.copy()
    candidates = []
    configured = os.environ.get("RESEARCHGUARD_SOURCE_ROOT")
    if configured:
        candidates.append(Path(configured))
    candidates.extend(
        [
            REPO.parent / "ResearchGuard",
            Path(r"D:\Documents_Archive_20260824\workflow-state-projects\ResearchGuard"),
        ]
    )
    source_paths = [
        str(entry / "src")
        for entry in candidates
        if (entry / "src" / "researchguard").is_dir()
    ]
    if source_paths:
        existing = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = os.pathsep.join(source_paths + ([existing] if existing else []))
    return environment

CHECKS = {
    "routing": ["-m", "pytest", "tests/unit/test_routing.py", "-q"],
    "specialist-authority": ["scripts/check_researchguard_topology.py", "--root", str(REPO), "--json"],
    "investigation": ["-m", "pytest", "tests/unit/test_investigation.py", "-q"],
    "academic": ["-m", "pytest", "tests/unit/test_academic.py", "-q"],
    "fiction": ["-m", "pytest", "tests/unit/test_fiction.py", "-q"],
    "travel": ["-m", "pytest", "tests/unit/test_travel.py", "-q"],
    "shared-writing": ["-m", "pytest", "tests/unit/test_shared_writing.py", "-q"],
    "reader-artifact": ["-m", "pytest", "tests/unit/test_reader.py", "tests/unit/test_reader_spine_projection.py", "tests/contract/test_reader_projection_owner.py", "-q"],
    "final-closure": ["-m", "pytest", "tests/unit/test_freshness_closure.py", "tests/unit/test_review_obligations.py", "-q"],
    "contract-calibration": ["scripts/author/evaluate_contract_calibration.py", "--positive", "skills/logic-writing/.skillguard/fixtures/contract-depth-positive.json", "--shallow", "skills/logic-writing/.skillguard/fixtures/contract-depth-shallow.json"],
    "release-integrity": ["scripts/check_release_surface.py", "--root", str(REPO), "--mode", "source", "--json"],
    "model-depth": ["scripts/author/check_logic_writing_model_depth.py", "--root", str(REPO), "--json"],
}

name = sys.argv[1] if len(sys.argv) == 2 else ""
if name not in CHECKS:
    raise SystemExit(f"unknown check: {name}")
args = CHECKS[name]
if name == "specialist-authority":
    # Calling the topology function in-process avoids the Windows launcher
    # indirection that can leave a detached child alive until the outer
    # timeout.  The same target-owned checker and report are used.
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from scripts.check_researchguard_topology import check as topology_check

    report = topology_check(REPO)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    raise SystemExit(0 if report.get("ok") else 1)
if args[:2] == ["-m", "pytest"]:
    command = [sys.executable, "-B", *args]
else:
    command = [sys.executable, "-B", *args]
completed = subprocess.run(command, cwd=REPO, check=False, env=_author_environment())
raise SystemExit(completed.returncode)
