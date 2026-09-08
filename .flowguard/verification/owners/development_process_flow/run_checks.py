from __future__ import annotations

import sys
from pathlib import Path

FLOWGUARD_ROOT = Path(__file__).resolve().parents[3]
if str(FLOWGUARD_ROOT) not in sys.path:
    sys.path.insert(0, str(FLOWGUARD_ROOT))

"""Run the process parent over the current retirement child receipt."""

from models.owners._mesh_support import emit_runner, run_development_parent


def main() -> int:
    return emit_runner("development_process_flow", run_development_parent())


if __name__ == "__main__":
    raise SystemExit(main())
