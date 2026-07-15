"""Run the plan-detailing template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    detail_reports, intake, process, contracts = run_checks()
    print("=== flowguard plan-detailing template ===")
    for report in detail_reports:
        print(report.format_text(max_findings=4))
        print()
    print(intake.format_text(max_findings=4))
    print()
    print(process.format_text(max_findings=4))
    print(f"contracts: {len(contracts)}")
    good_ok = detail_reports[0].ok and intake.ok and process.ok and contracts
    broken_blocked = all(not report.ok for report in detail_reports[1:])
    return 0 if good_ok and broken_blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
