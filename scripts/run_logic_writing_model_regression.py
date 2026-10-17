"""Explicit entry for the same single native model owner used by release."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] / ".flowguard/verification/run_models.py"), run_name="__main__")
