from __future__ import annotations

import copy
from typing import Any


class MutationError(ValueError):
    pass


def _resolve(root: Any, path: list[Any]) -> Any:
    current = root
    for part in path:
        if isinstance(part, int):
            if not isinstance(current, list) or part < 0 or part >= len(current):
                raise MutationError(f"invalid list path segment {part!r}")
            current = current[part]
        else:
            if not isinstance(current, dict) or part not in current:
                raise MutationError(f"invalid object path segment {part!r}")
            current = current[part]
    return current


def _parent(root: Any, path: list[Any]) -> tuple[Any, Any]:
    if not path:
        raise MutationError("mutation path cannot be empty")
    return _resolve(root, path[:-1]), path[-1]


def apply_mutations(payload: dict[str, Any], mutations: list[Any]) -> dict[str, Any]:
    result = copy.deepcopy(payload)
    for position, raw in enumerate(mutations):
        if not isinstance(raw, dict):
            raise MutationError(f"mutation {position} must be an object")
        operation = raw.get("op")
        path = raw.get("path")
        if not isinstance(path, list):
            raise MutationError(f"mutation {position} path must be a list")
        if operation == "set":
            parent, key = _parent(result, path)
            if isinstance(key, int):
                if not isinstance(parent, list) or key < 0 or key >= len(parent):
                    raise MutationError(f"mutation {position} set index is invalid")
                parent[key] = copy.deepcopy(raw.get("value"))
            else:
                if not isinstance(parent, dict):
                    raise MutationError(f"mutation {position} set parent is not an object")
                parent[key] = copy.deepcopy(raw.get("value"))
        elif operation == "delete":
            parent, key = _parent(result, path)
            if isinstance(key, int):
                if not isinstance(parent, list) or key < 0 or key >= len(parent):
                    raise MutationError(f"mutation {position} delete index is invalid")
                del parent[key]
            else:
                if not isinstance(parent, dict) or key not in parent:
                    raise MutationError(f"mutation {position} delete key is invalid")
                del parent[key]
        elif operation == "append":
            target = _resolve(result, path)
            if not isinstance(target, list):
                raise MutationError(f"mutation {position} append target is not a list")
            target.append(copy.deepcopy(raw.get("value")))
        elif operation == "set_each":
            target = _resolve(result, path)
            field = raw.get("field")
            if not isinstance(target, list) or not isinstance(field, str):
                raise MutationError(f"mutation {position} set_each shape is invalid")
            for row in target:
                if not isinstance(row, dict):
                    raise MutationError(f"mutation {position} set_each target contains non-object")
                row[field] = copy.deepcopy(raw.get("value"))
        elif operation == "set_where":
            target = _resolve(result, path)
            match_field = raw.get("match_field")
            set_field = raw.get("set_field")
            if not isinstance(target, list) or not isinstance(match_field, str) or not isinstance(set_field, str):
                raise MutationError(f"mutation {position} set_where shape is invalid")
            matches = [row for row in target if isinstance(row, dict) and row.get(match_field) == raw.get("match_value")]
            if len(matches) != 1:
                raise MutationError(f"mutation {position} set_where expected one match, found {len(matches)}")
            matches[0][set_field] = copy.deepcopy(raw.get("value"))
        else:
            raise MutationError(f"mutation {position} uses unsupported op {operation!r}")
    return result


__all__ = ["MutationError", "apply_mutations"]
