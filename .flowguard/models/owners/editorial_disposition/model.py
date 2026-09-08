"""Native model declaration for editorial disposition."""

from models.owners._mesh_support import MODEL_PATHS, PARENTS, TEST_PATHS

MODEL_ID = "editorial_disposition"
PARENT_MODEL_ID = PARENTS[MODEL_ID]


def declaration() -> dict[str, object]:
    return {
        "model_id": MODEL_ID,
        "parent_model_id": PARENT_MODEL_ID,
        "model_path": MODEL_PATHS[MODEL_ID],
        "tests": list(TEST_PATHS[MODEL_ID]),
        "obligations": ["A07:editorial_disposition", "A07:internal_material_hidden", "A07:limitation_materiality"],
    }
