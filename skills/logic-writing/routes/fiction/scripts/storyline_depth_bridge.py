#!/usr/bin/env python3
"""Emit current SkillGuard v2 depth evidence from Storyline native owner receipts.

The target owns the Storyline universe specifications and source checks.  This
thin entrypoint only connects those target-owned declarations to the installed
SkillGuard protocol implementation; it does not add a second story route.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
_candidates = [SKILL_ROOT.parent / "skillguard"]
_codex_home = os.environ.get("CODEX_HOME", "").strip()
if _codex_home:
    _candidates.append(Path(_codex_home) / "skills" / "skillguard")
_candidates.append(Path.home() / ".codex" / "skills" / "skillguard")
SKILLGUARD_SCRIPTS = next(
    (candidate / "scripts" for candidate in _candidates if (candidate / "scripts").is_dir()),
    None,
)
if SKILLGUARD_SCRIPTS is None:
    raise SystemExit("current SkillGuard scripts are unavailable")
if str(SKILLGUARD_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILLGUARD_SCRIPTS))

from skillguard_native_depth_bridge import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
