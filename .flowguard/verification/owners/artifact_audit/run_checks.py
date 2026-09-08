from __future__ import annotations

import sys
from pathlib import Path

FLOWGUARD_ROOT = Path(__file__).resolve().parents[3]
if str(FLOWGUARD_ROOT) not in sys.path:
    sys.path.insert(0, str(FLOWGUARD_ROOT))

"""Execute artifact audit tests and publish a child receipt."""

from models.owners._mesh_support import emit_runner, run_owner


if __name__ == "__main__":
    raise SystemExit(emit_runner("artifact_audit", run_owner("artifact_audit")))
