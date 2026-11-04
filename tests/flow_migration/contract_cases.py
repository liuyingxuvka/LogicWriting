"""Finite input tables for the transferred functional contracts.

These are the original input domains and a few explicit lifecycle sequences;
there is no state explorer, trace cache, or replacement FlowGuard engine here.
"""
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

TOPICS = (
    "anchor_import", "closure_claim", "fiction_tree", "known_bad_generator",
    "plan_order", "plan_readback", "provider_preflight", "reader_artifact",
    "reader_evidence", "reader_review", "route_review", "route_selection",
    "shared_contracts", "shared_writing_binding", "skill_install",
    "trip_feasibility", "wording_license", "world_references", "world_report",
)


def contract(topic):
    return import_module(f"tests.flow_migration.{topic}")


def cases(topic, *, functional=False):
    """Current inputs plus the original review/report/route lifecycle boundaries."""
    module = contract(topic)
    for initial in module.INITIAL_CASES:
        for event in module.INPUT_CASES:
            if topic == "reader_artifact" and event.kind == "order":
                continue  # The separate plan-order handoff uses its actual audit receipt.
            yield initial, (event,)
        if topic in {"closure_claim", "world_report"}:
            close = next(e for e in module.INPUT_CASES if e.kind == "close")
            for event in module.INPUT_CASES:
                if event.kind == "report":
                    yield initial, (event, close)
        if topic == "route_selection":
            repeated = module.INPUT_CASES[0]
            for event in module.INPUT_CASES:
                yield initial, (event, repeated)
        if topic == "reader_artifact":
            E = module.Event
            for events in (
                (E("review", "pass"), E("close")),
                (E("review", "repair"), E("close")),
                (E("self_review", "pass"), E("close")),
                (E("review", "pass"), E("edit"), E("close")),
                (E("review", "pass"), E("close"), E("edit")),
            ):
                yield initial, events
            if not functional:
                # The order audit is a separate production call, whose result is
                # supplied to closure. Its native handoff is tested separately.
                yield initial, (E("review", "pass"), E("order", "plan_order_mismatch"), E("close"))


@contextmanager
def actual(topic):
    """The original fixture calls the shipped production functions directly."""
    module = contract(topic)
    reader = {"anchor_import", "plan_order", "plan_readback", "reader_artifact",
              "reader_evidence", "reader_review"}
    if topic == "shared_writing_binding":
        with TemporaryDirectory(prefix="lw-binding-contract-") as folder:
            yield module.Native(Path(folder))
        return
    consoles = module._PathConsoles() if topic == "provider_preflight" else None
    if topic in reader:
        instance = module._RealReaderChain()
    elif topic == "provider_preflight":
        instance = module._RealRouting(consoles)
    else:
        classes = {"fiction_tree": "_RealFiction", "known_bad_generator": "_RealGenerator",
                   "trip_feasibility": "_RealTripPlan", "world_references": "_RealWorldRefs",
                   "route_selection": "_RealRouting"}
        instance = getattr(module, classes[topic] if topic in classes else "Native")()
    try:
        yield instance
    finally:
        if hasattr(instance, "close"):
            instance.close()
        if consoles is not None:
            consoles.close()
