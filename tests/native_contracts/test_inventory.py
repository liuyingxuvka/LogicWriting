"""Transfer inventory and the original generated system's static ownership links."""
from contextlib import closing
from flowguard.structure import build
import json
from pathlib import Path

import pytest

from .contract_cases import TOPICS, contract

ROOT = Path(__file__).resolve().parents[2]
COVERAGE = json.loads(Path(__file__).with_name("coverage.json").read_text())


@pytest.fixture(scope="module")
def graph():
    with closing(build(ROOT)) as result:
        yield result


def defined(graph, anchor):
    path, _, symbol = anchor.partition(":")
    names = {node["qual"] for node in graph.nodes(file=path)
             if node["kind"] in {"function", "class", "test", "method"}}
    assert symbol in names, anchor


def test_original_contract_destinations_and_production_links(graph):
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
                defined(graph, binding)
        for binding in row["production_bindings"]:
            defined(graph, binding["target"])
        for anchor in row["uses"].values():
            defined(graph, anchor)


@pytest.mark.parametrize("route", COVERAGE["system_routes"], ids=lambda row: row["id"])
def test_system_route_anchors(route, graph):
    # The old generated system checked map-declared existence and ownership.
    # Runtime reader order is exercised by the actual reader-chain contracts.
    assert route["source_anchors"]
    for anchor in route["source_anchors"]:
        defined(graph, anchor)


def test_unused_researchguard_handoff_has_no_production_caller(graph):
    """Retain the old closure contract's one static unreferenced assertion."""
    target = "build_researchguard_handoff"
    folders = ("skills/logic-writing/scripts/", "skills/logic-writing/routes/")
    for node in graph.calls():
        if node["file"].startswith(folders):
            assert node["text"].rsplit(".", 1)[-1] != target, node["file"]
    for node in graph.imports(declarations=True):
        if node["file"].startswith(folders):
            assert node["name"] != target, node["file"]
