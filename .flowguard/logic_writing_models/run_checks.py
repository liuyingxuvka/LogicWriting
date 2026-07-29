"""Run the full Logic Writing FlowGuard model mesh in an isolated output root."""

from __future__ import annotations

import json
import os
from pathlib import Path

from model import build_logic_writing_model_report


def main() -> int:
    payload = build_logic_writing_model_report()
    output_root = Path(
        os.environ.get(
            "FLOWGUARD_OUTPUT_DIR",
            Path(__file__).resolve().parents[1] / "evidence" / "models",
        )
    )
    output_root.mkdir(parents=True, exist_ok=True)
    output_path = output_root / "model-report.json"
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] in {"pass", "pass_with_gaps"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
