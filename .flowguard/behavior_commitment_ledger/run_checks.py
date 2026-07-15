from model import build_behavior_commitment_ledger
from flowguard import review_behavior_commitment_ledger


def main():
    report = review_behavior_commitment_ledger(build_behavior_commitment_ledger())
    print("flowguard behavior commitment ledger")
    print(report.format_text())
    print("full_inventory_registered:", "yes" if report.ok else "no")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
