"""Native model declaration for exact artifact audit."""

from models.owners._mesh_support import MODEL_PATHS, PARENTS, TEST_PATHS

MODEL_ID = "artifact_audit"
PARENT_MODEL_ID = PARENTS[MODEL_ID]


def declaration() -> dict[str, object]:
    return {
        "model_id": MODEL_ID,
        "parent_model_id": PARENT_MODEL_ID,
        "model_path": MODEL_PATHS[MODEL_ID],
        "tests": list(TEST_PATHS[MODEL_ID]),
        "obligations": ["A09:actual_artifact_bytes", "A09:complete_mapping", "A09:current_audit"],
    }
