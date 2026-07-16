#!/usr/bin/env python3
"""Exercise positive and same-family negative Storyline project meshes."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from storyline_project_mesh_check import validate_manifest


Mutation = Callable[[Path], None]


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def mutate_project_id(root: Path) -> None:
    path = root / "chapter-interfaces.json"
    payload = read(path)
    payload["project_id"] = "other-project"
    write(path, payload)


def mutate_parent(root: Path) -> None:
    path = root / "novel-ledger.json"
    payload = read(path)
    payload["hierarchy"]["chapters"][0]["parent_id"] = "missing-volume"
    write(path, payload)


def mutate_revision(root: Path) -> None:
    path = root / "voice-style-report.json"
    payload = read(path)
    payload["model_revision"] = "stale-revision"
    write(path, payload)


def mutate_artifact(root: Path) -> None:
    path = root / "semantic-review.json"
    payload = read(path)
    payload["artifact_sha256"] = "sha256:" + "0" * 64
    write(path, payload)


def mutate_native_child(root: Path) -> None:
    path = root / "promise-payoff.json"
    payload = read(path)
    payload["promises"][0]["status"] = "unsupported"
    write(path, payload)


def case_result(
    source: Path,
    mutation: Mutation | None,
    expected_codes: set[str],
    repository_root: Path,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=".storyline-mesh-", dir=repository_root) as temp:
        target = Path(temp) / "project"
        shutil.copytree(source, target)
        if mutation is not None:
            mutation(target)
        manifest_path = target / "project-mesh.json"
        report = validate_manifest(
            read(manifest_path),
            manifest_path,
            repository_root=repository_root,
        )
        codes = {row["code"] for row in report["issues"]}
        expected_pass = mutation is None
        passed = report["passed"] is expected_pass and (expected_pass or bool(codes & expected_codes))
        return {
            "passed": passed,
            "mesh_passed": report["passed"],
            "observed_codes": sorted(codes),
            "expected_codes": sorted(expected_codes),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Storyline model-mesh regression cases.")
    parser.add_argument("--project-root", default="skills/logic-writing/routes/fiction/examples/longform_novel_project")
    parser.add_argument("--repo-root")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    source = Path(args.project_root).resolve()
    repository_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[3]
    cases = {
        "positive": (None, set()),
        "cross-project": (mutate_project_id, {"project_identity_mismatch"}),
        "dangling-parent": (mutate_parent, {"dangling_mesh_edge"}),
        "stale-model": (mutate_revision, {"model_revision_mismatch"}),
        "mixed-artifact": (mutate_artifact, {"artifact_identity_mismatch", "native_owner_failed"}),
        "native-invalid-child": (mutate_native_child, {"native_owner_failed"}),
    }
    results = []
    for case_id, (mutation, expected) in cases.items():
        result = case_result(source, mutation, expected, repository_root)
        result["case_id"] = case_id
        results.append(result)
    report = {
        "schema_version": "storyline-design.project_mesh_regression.report.v1",
        "passed": all(row["passed"] for row in results),
        "summary": {"case_count": len(results), "failed_count": sum(not row["passed"] for row in results)},
        "results": results,
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Project mesh regression: {'passed' if report['passed'] else 'failed'}")
        for row in results:
            print(f"- {'ok' if row['passed'] else 'failed'}: {row['case_id']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
