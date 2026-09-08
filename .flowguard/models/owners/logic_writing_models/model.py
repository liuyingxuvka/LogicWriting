"""Current LogicWriting parent model.

The parent consumes the direct child model-mesh receipts.  It deliberately
does not call the old aggregate runner, because doing so would rerun every
child inside the parent and would make the hierarchy evidence ambiguous.
"""

from __future__ import annotations

from models.owners._mesh_support import run_logic_writing_parent


def build_logic_writing_model_report() -> dict[str, object]:
    """Consume current direct-child receipts and review the parent boundary."""

    return run_logic_writing_parent()
