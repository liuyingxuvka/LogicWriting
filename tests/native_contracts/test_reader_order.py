"""Actual audit receipt to closure handoff retained from reader_artifact."""
from .contract_cases import actual, contract


def test_plan_order_audit_to_actual_closure():
    module = contract("reader_artifact")
    with actual("reader_artifact") as native:
        initial = module.State(module.OWNERS[0])
        native.reset(initial)
        chain = native.complete_chain(native._workdir(), pass_quality=True)
        assert chain["deterministic_audit"]["quality_dimensions"]["plan_order"] == "passed"
        observed = native.derive_closure(native.closure_input(chain))["closure"]["status"]
        reviewed = module.State(module.OWNERS[0], reviewed=True, current=True,
                                quality="pass", independent=True)
        _, received = module.CALCULATE(module.Event("order", "passed"), reviewed)
        expected, _ = module.CALCULATE(module.Event("close"), received)
        assert observed == expected == "passed"
        assert native._order("swapped") == "plan_order_mismatch"
        _, received = module.CALCULATE(module.Event("order", "plan_order_mismatch"), reviewed)
        expected, _ = module.CALCULATE(module.Event("close"), received)
        assert expected == "needs_repair"
