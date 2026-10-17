"""Direct native check for primary_path_authority."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from flowguard.map.runner import run_owner
from models.owners._native_checks import check_optional

def main():
    return check_optional('primary_path_authority')

if __name__ == "__main__":
    raise SystemExit(run_owner(main))
