"""Audit LogicWriting's current model authority through its root contract.

The generic ``python -m flowguard model-system-audit`` command cannot infer a
target-owned root contract and therefore falls back to its lexical root.  This
project command binds the declared ``logic_writing_models`` root before running
the unchanged native FlowGuard audit.  It proves current model authority only
within LogicWriting's declared finite boundary.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_AUTHOR_ROOT = Path(__file__).resolve().parent
if str(_AUTHOR_ROOT) not in sys.path:
    sys.path.insert(0, str(_AUTHOR_ROOT))

from logic_writing_model_authority import (  # noqa: E402
    audit_current_logic_writing_model_authority,
)


def run_check(root: Path) -> dict[str, object]:
    report = audit_current_logic_writing_model_authority(root.resolve())
    payload = report.to_dict()
    payload["check"] = "logic-writing-model-authority"
    payload["root_contract_adapter"] = "scripts/author/logic_writing_model_authority.py"
    payload["claim_boundary"] = (
        "Current authority is audited against LogicWriting's declared root "
        "contract and finite model boundary; this does not prove future prose "
        "quality, external providers, installation, or publication."
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run_check(args.root)
    except Exception as exc:
        report = {
            "check": "logic-writing-model-authority",
            "status": "blocked",
            "ok": False,
            "findings": [
                {
                    "severity": "blocked",
                    "code": "target_authority_audit_error",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            ],
        }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
