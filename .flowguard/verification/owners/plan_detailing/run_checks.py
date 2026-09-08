from __future__ import annotations

import sys
from pathlib import Path

FLOWGUARD_ROOT = Path(__file__).resolve().parents[3]
if str(FLOWGUARD_ROOT) not in sys.path:
    sys.path.insert(0, str(FLOWGUARD_ROOT))

"""Run plan-detailing as one registered FlowGuard owner."""

from models.owners._mesh_support import emit_runner, run_root_owner


def main() -> int:
    return emit_runner("plan_detailing", run_root_owner("plan_detailing"))


if __name__ == "__main__":
    raise SystemExit(main())
