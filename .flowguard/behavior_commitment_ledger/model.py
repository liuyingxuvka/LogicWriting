"""Thin adapter for the canonical FlowGuard behavior commitment ledger.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Load the full external behavior promise set before broad work claims.
Guards against: duplicate authorities, mixed execution planes, stale evidence,
and Python-embedded inventory drifting from the machine-readable ledger.
Use before editing: non-trivial product behavior, UI/API/CLI changes, release,
archive, publish, or any broad external-behavior coverage claim.
Run: python run_checks.py
"""

from pathlib import Path

from flowguard import load_behavior_commitment_ledger


LEDGER_PATH = Path(__file__).with_name("ledger.json")


def build_behavior_commitment_ledger():
    return load_behavior_commitment_ledger(LEDGER_PATH)
