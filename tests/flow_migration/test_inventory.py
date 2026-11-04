"""Transfer inventory and the original generated system's static ownership links."""
import ast
import json
from pathlib import Path

import pytest

from .contract_cases import TOPICS, contract

ROOT = Path(__file__).resolve().parents[2]
COVERAGE = json.loads(Path(__file__).with_name("coverage.json").read_text())


def defined(anchor):
    path, _, symbol = anchor.partition(":")
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    names = {node.name for node in ast.walk(tree)
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    assert symbol.split(".")[-1] in names, anchor


def test_original_contract_destinations_and_production_links():
    rows = COVERAGE["models"]
    assert {row["topic"] for row in rows} == set(TOPICS)
    assert len(rows) == 19
    assert sum(len(row["rules"]) for row in rows) == 61
    assert sum(len(row["bad_variants"]) for row in rows) == 69
    assert sum(len(rule["production_tests"]) for row in rows for rule in row["rules"]) == 112
    for row in rows:
        module = contract(row["topic"])
        assert [rule["id"] for rule in row["rules"]] == list(module.RULES)
        assert [bad["id"] for bad in row["bad_variants"]] == list(module.BAD_EXPECTATIONS)
        for rule in row["rules"]:
            for binding in rule["production_tests"]:
                defined(binding)
        for binding in row["production_bindings"]:
            defined(binding["target"])
        for anchor in row["uses"].values():
            defined(anchor)


@pytest.mark.parametrize("route", COVERAGE["system_routes"], ids=lambda row: row["id"])
def test_system_route_anchors(route):
    # The old generated system checked map-declared existence and ownership.
    # Runtime reader order is exercised by the actual reader-chain contracts.
    assert route["source_anchors"]
    for anchor in route["source_anchors"]:
        defined(anchor)


def test_unused_researchguard_handoff_has_no_production_caller():
    """Retain the old closure contract's one static unreferenced assertion."""
    target = "build_researchguard_handoff"
    for folder in (ROOT / "skills/logic-writing/scripts", ROOT / "skills/logic-writing/routes"):
        for path in folder.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                    assert name != target, str(path)
                if isinstance(node, ast.ImportFrom):
                    assert target not in {alias.name for alias in node.names}, str(path)
