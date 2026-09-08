from __future__ import annotations

import sys
from pathlib import Path

FLOWGUARD_ROOT = Path(__file__).resolve().parents[3]
if str(FLOWGUARD_ROOT) not in sys.path:
    sys.path.insert(0, str(FLOWGUARD_ROOT))

"""Run the research packet model as an independent child owner."""

from models.owners._mesh_support import emit_runner, run_owner


if __name__ == "__main__":
    raise SystemExit(emit_runner("research_packet_model", run_owner("research_packet_model")))
