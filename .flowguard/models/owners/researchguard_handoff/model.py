"""Native model declaration for the ResearchGuard to reader handoff."""

from models.owners._mesh_support import MODEL_PATHS, PARENTS, TEST_PATHS

MODEL_ID = "researchguard_handoff"
PARENT_MODEL_ID = PARENTS[MODEL_ID]


def declaration() -> dict[str, object]:
    return {
        "model_id": MODEL_ID,
        "parent_model_id": PARENT_MODEL_ID,
        "model_path": MODEL_PATHS[MODEL_ID],
        "tests": list(TEST_PATHS[MODEL_ID]),
        "obligations": ["A13:native_schema_binding", "A13:claim_boundary", "A13:gap_preservation"],
    }
