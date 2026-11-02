from __future__ import annotations

import sys
from pathlib import Path



REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "skills" / "logic-writing"
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# A test that ends skipped fails the run (tests/no_skips.py).
from tests.no_skips import pytest_runtest_makereport  # noqa: E402,F401
