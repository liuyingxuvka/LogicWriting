from __future__ import annotations

import sys
from pathlib import Path

FLOWGUARD_ROOT = Path(__file__).resolve().parents[3]
if str(FLOWGUARD_ROOT) not in sys.path:
    sys.path.insert(0, str(FLOWGUARD_ROOT))

from models.owners._mesh_support import emit_runner, run_root_owner


def main():
    return emit_runner("behavior_commitment_ledger", run_root_owner("behavior_commitment_ledger"))


if __name__ == "__main__":
    raise SystemExit(main())
