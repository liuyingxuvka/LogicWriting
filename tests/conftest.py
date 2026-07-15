from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "skills" / "logic-writing"
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def receipt_root(tmp_path: Path) -> Path:
    return tmp_path / "receipts"


@pytest.fixture
def current_packet(receipt_root: Path):
    from tests.support import make_current_packet

    return make_current_packet(receipt_root)


@pytest.fixture
def reader_chain(tmp_path: Path, receipt_root: Path):
    from tests.support import make_reader_chain

    return make_reader_chain(receipt_root, tmp_path)


@pytest.fixture
def revision_chain(tmp_path: Path, receipt_root: Path):
    from tests.support import make_revision_chain

    return make_revision_chain(receipt_root, tmp_path)
