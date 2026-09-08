"""Update the LogicWriting author contract with its native model-depth check.

The existing contract remains the source of all route and check declarations;
this tool makes the one additional obligation and its reverse inventory
declaration reproducible.  The SkillGuard compiler still owns the compiled
contract and check-manifest projections.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any


CHECK_ID = "check:logic-writing:model-depth"
OWNER_ID = "owner:logic-writing:model-depth"
OBLIGATION_ID = "obligation:logic-writing:model-depth"


def _write(path: Path, payload: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def update(root: Path) -> dict[str, Any]:
    path = root / "skills" / "logic-writing" / ".skillguard" / "contract-source.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    checks = list(payload.get("checks", ()))
    checks = [row for row in checks if row.get("check_id") != CHECK_ID]
    checks.append({
        "args": ["scripts/author/check_logic_writing_model_depth.py", "--root", ".", "--json"],
        "check_id": CHECK_ID,
        "command": "python",
        "coverage_rationale": "The target-owned native check verifies the exact 22-owner model hierarchy, every runner/test binding, and current immutable owner receipts.",
        "coverage_scope": "declared_obligations",
        "covers_obligation_ids": [OBLIGATION_ID],
        "cwd_token": "repository_root",
        "depends_on_check_ids": [],
        "evidence_class": "hard",
        "evidence_domain_id": "evidence-domain:logic-writing:model-depth",
        "evidence_subject_id": "subject:logic-writing:model-depth",
        "execution_owner_id": OWNER_ID,
        "expected": {"exit_code": 0},
        "input_selectors": [
            {"kind": "subtree", "path": "skills/logic-writing/.skillguard"},
            {"kind": "path", "path": "skills/logic-writing/SKILL.md"},
            {"kind": "subtree", "path": "tests"},
            {"kind": "role", "role": "runtime_source"},
            {"kind": "role", "role": "documentation_model"},
        ],
        "kind": "command",
        "maintenance_unit_id": "unit:logic-writing",
        "member_skill_id": "logic-writing",
        "native_route_id": "route:logic-writing:router",
        "semantic_check_id": "semantic:logic-writing:model-depth",
        "timeout_seconds": 900,
    })
    payload["checks"] = checks
    payload["model_path"] = "scripts/author/skillguard_contract_model.py"
    paths = list(payload.get("implementation_paths", ()))
    for item in (
        "scripts/author",
        ".flowguard/models/owners",
        ".flowguard/verification/owners",
        ".flowguard/models/regression-manifest.json",
        ".flowguard/structure/owner-bindings.json",
        "tests/flowguard",
        "tests/unit",
        "tests/adversarial",
    ):
        if item not in paths:
            paths.append(item)
    payload["implementation_paths"] = paths
    closure = payload.get("closure_profiles", payload.get("closure", ()))
    for profile in closure:
        required = list(profile.get("required_obligation_ids", ()))
        if OBLIGATION_ID not in required:
            required.append(OBLIGATION_ID)
        profile["required_obligation_ids"] = required
    if "closure_profiles" in payload:
        payload["closure_profiles"] = closure
    depth = payload["depth_profile"]
    native_ids = list(depth.get("native_check_ids", ()))
    if CHECK_ID not in native_ids:
        native_ids.append(CHECK_ID)
    depth["native_check_ids"] = native_ids
    depth["model_deepening_check_id"] = CHECK_ID
    depth["surface_inventory"] = {
        "path": ".skillguard/surface-inventory.json",
        "adequacy_check_ids": native_ids,
        "model_deepening_check_id": CHECK_ID,
    }
    provider = depth.get("provider_runtime")
    if isinstance(provider, dict):
        ready = list(provider.get("readiness_check_ids", ()))
        if CHECK_ID not in ready:
            ready.append(CHECK_ID)
        provider["readiness_check_ids"] = ready
    bindings = list(payload.get("native_check_bindings", ()))
    bindings = [row for row in bindings if row.get("check_id") != CHECK_ID]
    bindings.append({"authority": "target-native", "check_id": CHECK_ID, "owner_id": OWNER_ID})
    payload["native_check_bindings"] = bindings
    for step in payload.get("step_bindings", ()):
        if step.get("step_id") == "step:logic-writing:maintenance":
            ids = list(step.get("check_ids", ()))
            if CHECK_ID not in ids:
                ids.insert(0, CHECK_ID)
            step["check_ids"] = ids
    payload["claim_boundary"] = (
        "LogicWriting owns the current route-native writing contract and its "
        "22-owner FlowGuard model mesh. SkillGuard supervises declared checks "
        "and source closure; it does not claim provider quality or future prose quality."
    )
    _write(path, payload)
    return {"check_id": CHECK_ID, "obligation_id": OBLIGATION_ID, "model_path": payload["model_path"], "check_count": len(checks)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    print(json.dumps(update(args.root.resolve()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
