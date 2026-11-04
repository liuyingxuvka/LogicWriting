"""Use the installed FlowGuard command boundary, preserving Python module identity."""
import json
from pathlib import Path
import subprocess
import sys


def test_real_exact_record_identity_native_contract():
    result = subprocess.run([sys.executable, "-m", "flowguard", "check", "record_identity", "--full", "--json"],
                            cwd=Path(__file__).resolve().parents[2], capture_output=True,
                            text=True, timeout=60)
    assert result.returncode == 0, (result.stdout, result.stderr)
    evidence = json.loads(result.stdout)
    assert evidence["complete"] is True
    assert evidence["conflicts"] == []
    assert evidence["errors"] == []
