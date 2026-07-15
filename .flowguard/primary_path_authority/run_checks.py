"""Run Logic Writing Primary Path Authority design and known-bad checks."""

from flowguard import review_primary_path_authority

from model import (
    broken_alias_unknown_disposition,
    broken_manual_recovery_auto_invoked,
    broken_old_skill_masks_primary_failure,
    design_plan,
)


def assert_codes(report, *codes):
    actual = {finding.code for finding in report.findings}
    missing = set(codes) - actual
    if missing:
        raise AssertionError(f"missing findings {sorted(missing)} in {sorted(actual)}\n{report.format_text()}")


def main():
    design = review_primary_path_authority(design_plan())
    print(design.format_text())
    if not design.ok:
        raise SystemExit("Logic Writing design-phase Primary Path Authority failed")

    masked = review_primary_path_authority(broken_old_skill_masks_primary_failure())
    assert_codes(masked, "primary_failure_masked_by_fallback_success")

    alias = review_primary_path_authority(broken_alias_unknown_disposition())
    assert_codes(alias, "fallback_candidate_unknown_disposition")

    manual = review_primary_path_authority(broken_manual_recovery_auto_invoked())
    assert_codes(manual, "manual_recovery_auto_invoked")

    print("Logic Writing Primary Path Authority design checks passed")


if __name__ == "__main__":
    main()
