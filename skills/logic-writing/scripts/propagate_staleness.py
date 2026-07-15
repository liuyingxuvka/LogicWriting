"""Propagate evidence staleness through explicit receipt dependencies only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping

from _common import (
    ALL_STATUSES,
    ValidationError,
    dump_json,
    fingerprint,
    load_json,
    require_list,
    require_mapping,
    require_string,
    reject_unknown_keys,
    validation_result,
)
from receipt_authority import resolve_current_receipt


PLANES = {"agent_operation", "development_process"}
REQUEST_FIELDS = {"schema_version", "current_inputs", "nodes"}
NODE_FIELDS = {
    "receipt_fingerprint",
    "plane",
    "status",
    "input_fingerprints",
    "dependency_receipt_fingerprints",
}


def _fingerprint_map(value, label):
    value = require_mapping(value, label)
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValidationError(f"{label} keys must be non-empty strings")
        if not isinstance(item, str) or not item.startswith("sha256:") or len(item) != 71:
            raise ValidationError(f"{label}.{key} must be a sha256 fingerprint")
    return value


def _cycles(dependencies):
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []
    found: list[list[str]] = []

    def visit(node):
        if node in visiting:
            start = stack.index(node)
            cycle = stack[start:] + [node]
            if cycle not in found:
                found.append(cycle)
            return
        if node in visited:
            return
        visiting.add(node)
        stack.append(node)
        for dependency in dependencies[node]:
            visit(dependency)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in sorted(dependencies):
        visit(node)
    return found


def propagate_staleness(
    value,
    *,
    receipt_root: str | Path | None = None,
):
    value = require_mapping(value, "staleness request")
    reject_unknown_keys(value, REQUEST_FIELDS, "staleness request")
    if require_string(value, "schema_version") != "1.0":
        raise ValidationError("schema_version must be 1.0")
    current_inputs = _fingerprint_map(value.get("current_inputs"), "current_inputs")
    rows = require_list(value.get("nodes"), "nodes")
    if not rows:
        raise ValidationError("nodes must contain at least one receipt node")

    nodes: dict[str, dict] = {}
    for index, item in enumerate(rows):
        node = require_mapping(item, f"node {index}")
        reject_unknown_keys(node, NODE_FIELDS, f"node {index}")
        receipt_fingerprint = require_string(node, "receipt_fingerprint")
        if not receipt_fingerprint.startswith("sha256:") or len(receipt_fingerprint) != 71:
            raise ValidationError("receipt_fingerprint must be a sha256 fingerprint")
        if receipt_fingerprint in nodes:
            raise ValidationError(f"duplicate receipt_fingerprint: {receipt_fingerprint}")
        plane = require_string(node, "plane")
        if plane not in PLANES:
            raise ValidationError(f"unsupported plane: {plane}")
        status = require_string(node, "status")
        if status not in ALL_STATUSES:
            raise ValidationError(f"unsupported node status: {status}")
        inputs = _fingerprint_map(
            node.get("input_fingerprints"),
            f"node {receipt_fingerprint}.input_fingerprints",
        )
        dependencies = require_list(
            node.get("dependency_receipt_fingerprints"),
            "dependency_receipt_fingerprints",
        )
        if not all(
            isinstance(dep, str) and dep.startswith("sha256:") and len(dep) == 71
            for dep in dependencies
        ):
            raise ValidationError(
                "dependency_receipt_fingerprints must contain sha256 fingerprints"
            )
        nodes[receipt_fingerprint] = {
            "receipt_fingerprint": receipt_fingerprint,
            "plane": plane,
            "status": status,
            "input_fingerprints": inputs,
            "dependency_receipt_fingerprints": list(dict.fromkeys(dependencies)),
        }

    dependencies = {
        receipt_fingerprint: node["dependency_receipt_fingerprints"]
        for receipt_fingerprint, node in nodes.items()
    }
    unknown_dependencies = sorted(
        {dependency for items in dependencies.values() for dependency in items if dependency not in nodes}
    )
    if unknown_dependencies:
        raise ValidationError(
            "unknown dependency receipt fingerprints: " + ", ".join(unknown_dependencies)
        )
    cycles = _cycles(dependencies)
    if cycles:
        return validation_result(
            status="blocked",
            stale_receipt_fingerprints=[],
            current_receipt_fingerprints=[],
            reasons={},
            cross_plane_stale_edges=[],
            cycles=cycles,
            graph_fingerprint=fingerprint(value),
        )

    stale: set[str] = set()
    reasons: dict[str, list[str]] = {}
    authority_projection_fingerprints: dict[str, str] = {}
    for receipt_fingerprint, node in nodes.items():
        node_reasons: list[str] = []
        if receipt_root is not None:
            projection = resolve_current_receipt(
                receipt_fingerprint,
                root=receipt_root,
                expected={
                    "status": node["status"],
                    "input_fingerprints": node["input_fingerprints"],
                },
            )
            receipt = projection["receipt"]
            if receipt["dependency_receipt_fingerprints"] != node[
                "dependency_receipt_fingerprints"
            ]:
                raise ValidationError(
                    "staleness node dependencies do not match authoritative original"
                )
            authority_projection_fingerprints[receipt_fingerprint] = projection[
                "projection_fingerprint"
            ]
            if not projection["current"]:
                node_reasons.extend(
                    f"authority:{reason}" for reason in projection["reasons"]
                )
        if node["status"] == "stale":
            node_reasons.append("declared_stale")
        for input_id, consumed in node["input_fingerprints"].items():
            current = current_inputs.get(input_id)
            if current is None:
                node_reasons.append(f"current_input_missing:{input_id}")
            elif current != consumed:
                node_reasons.append(f"input_changed:{input_id}")
        if node_reasons:
            stale.add(receipt_fingerprint)
            reasons[receipt_fingerprint] = node_reasons

    changed = True
    while changed:
        changed = False
        for receipt_fingerprint, node in nodes.items():
            stale_dependencies = [
                dep for dep in node["dependency_receipt_fingerprints"] if dep in stale
            ]
            if stale_dependencies and receipt_fingerprint not in stale:
                stale.add(receipt_fingerprint)
                reasons[receipt_fingerprint] = [
                    f"dependency_stale:{dep}" for dep in stale_dependencies
                ]
                changed = True

    cross_plane = []
    for receipt_fingerprint in sorted(stale):
        node = nodes[receipt_fingerprint]
        for dependency in node["dependency_receipt_fingerprints"]:
            if dependency in stale and nodes[dependency]["plane"] != node["plane"]:
                cross_plane.append(
                    {
                        "dependency_receipt_fingerprint": dependency,
                        "dependent_receipt_fingerprint": receipt_fingerprint,
                        "from_plane": nodes[dependency]["plane"],
                        "to_plane": node["plane"],
                    }
                )

    return validation_result(
        status="current_pass",
        stale_receipt_fingerprints=sorted(stale),
        current_receipt_fingerprints=sorted(set(nodes) - stale),
        reasons={key: reasons[key] for key in sorted(reasons)},
        cross_plane_stale_edges=cross_plane,
        cycles=[],
        authority_projection_fingerprints={
            key: authority_projection_fingerprints[key]
            for key in sorted(authority_projection_fingerprints)
        },
        graph_fingerprint=fingerprint(value),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--receipt-root")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = propagate_staleness(
            load_json(args.input),
            receipt_root=args.receipt_root,
        )
        dump_json(result, args.output)
        return 0 if result["status"] == "current_pass" else 1
    except (ValidationError, OSError, json.JSONDecodeError) as exc:
        dump_json(validation_result(status="blocked", errors=(str(exc),)), args.output)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
