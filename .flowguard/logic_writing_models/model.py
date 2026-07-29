"""Thin executable owner for the Logic Writing FlowGuard model mesh."""

from __future__ import annotations

import sys
from pathlib import Path


FLOWGUARD_ROOT = Path(__file__).resolve().parents[1]
if str(FLOWGUARD_ROOT) not in sys.path:
    sys.path.insert(0, str(FLOWGUARD_ROOT))

from run_models import run  # noqa: E402


def build_logic_writing_model_report() -> dict[str, object]:
    """Execute the full Logic Writing model mesh without persisting evidence."""

    return run("full")
