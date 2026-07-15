from pathlib import Path


def test_contract_depth_pair_detects_one_important_gap():
    from importlib.util import module_from_spec, spec_from_file_location

    root = Path(__file__).resolve().parents[2]
    script = root / "skills" / "logic-writing" / ".skillguard" / "checks" / "evaluate_contract_calibration.py"
    spec = spec_from_file_location("logic_writing_calibration", script)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    fixtures = script.parent.parent / "fixtures"
    result = module.validate_pair(
        fixtures / "contract-depth-positive.json",
        fixtures / "contract-depth-shallow.json",
    )
    assert result["ok"] is True
    assert result["positive"]["status"] == "CONTRACT_DEPTH_PASS"
    assert result["shallow"]["missing_obligation_ids"] == [
        "obligation:logic-writing:reader-actual-artifact"
    ]
