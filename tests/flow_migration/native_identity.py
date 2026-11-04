"""Native adapter for the actual exact-object fingerprint validator."""
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[2] / "skills/logic-writing/scripts"
sys.path.insert(0, str(SCRIPTS))
from _common import own_fingerprint, require_exact_fingerprint


class RecordWorld:
    def __init__(self):
        self.version = 0
        self.accepted = False
        self.record = {"version": 0}
        self.record["record_fingerprint"] = own_fingerprint(self.record, "record_fingerprint")

    def edit(self):
        self.version = self.record["version"] = 1
        self.accepted = False

    def restore(self):
        self.version = self.record["version"] = 0
        self.accepted = False

    def check(self):
        require_exact_fingerprint(self.record, "record_fingerprint")
        self.accepted = True
