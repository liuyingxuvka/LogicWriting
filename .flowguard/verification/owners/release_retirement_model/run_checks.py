"""Direct native check for release_retirement_model."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from flowguard.map.runner import run_owner
from models.owners._native_checks import check_plan

def main():
    return check_plan('release_retirement_model')

if __name__ == "__main__":
    raise SystemExit(run_owner(main))
