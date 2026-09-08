from __future__ import annotations

import sys
from pathlib import Path

FLOWGUARD_ROOT = Path(__file__).resolve().parents[3]
if str(FLOWGUARD_ROOT) not in sys.path:
    sys.path.insert(0, str(FLOWGUARD_ROOT))

"""Run the LogicWriting parent over current direct-child receipts."""

from models.owners._mesh_support import emit_runner, run_logic_writing_parent


def main() -> int:
    return emit_runner("logic_writing_models", run_logic_writing_parent())


if __name__ == "__main__":
    raise SystemExit(main())
