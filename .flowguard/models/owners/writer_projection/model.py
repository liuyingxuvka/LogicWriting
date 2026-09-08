"""Native model declaration for the writer projection boundary."""

from models.owners._mesh_support import MODEL_PATHS, PARENTS, TEST_PATHS

MODEL_ID = "writer_projection"
PARENT_MODEL_ID = PARENTS[MODEL_ID]


def declaration() -> dict[str, object]:
    return {
        "model_id": MODEL_ID,
        "parent_model_id": PARENT_MODEL_ID,
        "model_path": MODEL_PATHS[MODEL_ID],
        "tests": list(TEST_PATHS[MODEL_ID]),
        "obligations": ["A06:writer_input_whitelist", "A06:route_semantics_preserved", "A06:composition_identity"],
    }
