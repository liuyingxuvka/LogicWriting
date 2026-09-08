from __future__ import annotations

import sys
from pathlib import Path

FLOWGUARD_ROOT = Path(__file__).resolve().parents[3]
if str(FLOWGUARD_ROOT) not in sys.path:
    sys.path.insert(0, str(FLOWGUARD_ROOT))

"""Consume reader leaf receipts and run the reader parent model once."""

from models.owners._mesh_support import emit_runner, run_reader_artifact_parent


if __name__ == "__main__":
    raise SystemExit(emit_runner("reader_artifact_model", run_reader_artifact_parent()))
